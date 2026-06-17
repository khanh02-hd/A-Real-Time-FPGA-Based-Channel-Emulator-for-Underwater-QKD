import numpy as np
import scipy.integrate as integrate
import scipy.stats as stats

# ============================================================
# FILE: lut_env1_clear_ocean.py
# ENV 1: CLEAR WATER / CLEAR OCEAN (AUTO-SWEEP 61 MỐC)
# ============================================================

# 1. THÔNG SỐ THIẾT BỊ
mu_alice = 1.0       # nS = 1 photon trung bình/xung
eta_bob = 0.5        # eta = 0.5

# 2. THÔNG SỐ MÔI TRƯỜNG
env_name = "Clear_Water"
c_fixed = 0.151      # 1/m

bubbles_enabled = False
sigma_s2_fixed = 0.0001
# Turbulence theo UnderwaterQKD
chi_T = 2e-7
epsilon = 2e-5
w_ratio = -2.2

# 3. THÔNG SỐ QUANG HỌC / FIXED-POINT
lamda = 530e-9       # 530 nm
n_water = 1.333
D_rx = 0.1           # 10 cm
theta_div = 6 * np.pi / 180
F_scatter = 1.0      

k_wave = (2 * np.pi * n_water) / lamda
eta_K = 1e-3

SCALE_FACTOR = 1 << 12
MAX_UINT16 = (1 << 16) - 1
Q0_32 = 2**32
BANK_SAMPLES = 1024

# 4. KỊCH BẢN KHOẢNG CÁCH (1.0m -> 7.0m)
distances = np.round(np.arange(1.0, 7.1, 0.1), 1)

scenarios = []
for i, d in enumerate(distances):
    sw_bin = format(i, '06b') # 6-bit auto_sw
    scenarios.append({
        "sw": sw_bin, "d": d, "bubbles": bubbles_enabled,
        "sigma_s2": sigma_s2_fixed, "c": c_fixed
    })

# 5. KHỞI TẠO BỘ NHỚ 65536
TOTAL_SCENARIOS = len(scenarios)
BANK_DEPTH = 65536

# Khởi tạo mặc định bằng 1.0 (SCALE_FACTOR) cho vùng nhớ dư
bank_ho = np.ones(BANK_DEPTH, dtype=np.uint16) * SCALE_FACTOR
bank_hs = np.ones(BANK_DEPTH, dtype=np.uint16) * SCALE_FACTOR

# 6. HÀM TÍNH TOÁN
def calculate_path_loss(d_distance, c_coeff):
    if d_distance <= 0: return 1.0
    geometric_loss = (D_rx**2) / (np.pi * (d_distance * np.tan(theta_div))**2)
    attenuation_loss = np.exp(-F_scatter * c_coeff * d_distance)
    return float(np.clip(geometric_loss * attenuation_loss, 0.0, 1.0))

def nikishov_spectrum(kappa):
    safe_k = np.where(kappa == 0, np.finfo(float).tiny, kappa)
    delta = 8.284 * (safe_k * eta_K)**(4/3) + 12.978 * (safe_k * eta_K)**2
    Phi_n = 0.388e-8 * (epsilon**(-1/3)) * (safe_k**(-11/3)) * (1 + 2.35 * (safe_k * eta_K)**(2/3)) * (chi_T / (w_ratio**2)) * (np.exp(-1.863e-2 * delta) + np.exp(-1.9e-4 * delta) - 2 * w_ratio * np.exp(-9.41e-3 * delta))
    return np.where(kappa == 0, 0.0, Phi_n)

def calculate_sigma_i2(d_distance):
    res, _ = integrate.dblquad(lambda k, xi: k * nikishov_spectrum(k) * (1 - np.cos((d_distance * (k**2) * xi) / k_wave)), 0, 1, lambda xi: 1e-4, lambda xi: 1.0 / eta_K)
    return 8 * np.pi * (k_wave**2) * d_distance * res

def export_mif(filename, data_array, depth):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"DEPTH = {depth};\nWIDTH = 16;\nADDRESS_RADIX = DEC;\nDATA_RADIX = BIN;\nCONTENT\nBEGIN\n")
        for i in range(depth):
            f.write(f"{i:4d} : {format(int(data_array[i]), '016b')};\n")
        f.write("END;\n")

# 7. SINH LUT
print(f"[*] Đang tạo LUT cho môi trường: {env_name}")
ls_verilog = ""
q_prob = np.linspace(0.5 / BANK_SAMPLES, 1 - 0.5 / BANK_SAMPLES, BANK_SAMPLES)

for idx, sc in enumerate(scenarios):
    d = sc["d"]
    channel_loss = calculate_path_loss(d, sc["c"])
    L_s_effective = mu_alice * eta_bob * channel_loss
    L_s_const = int(L_s_effective * Q0_32)

    ls_verilog += (
        f"            6'b{sc['sw']}: L_s_const = 32'd{L_s_const}; "
        f"// d={d}m, L_eff={L_s_effective:.6e}\n"
    )

    sigma_I2 = calculate_sigma_i2(d)
    sigma_X = np.sqrt(0.25 * np.log(1 + sigma_I2))
    ho_samples = stats.lognorm.ppf(q_prob, s=2 * sigma_X, scale=np.exp(2 * -sigma_X**2))
    bank_ho[idx * BANK_SAMPLES : (idx + 1) * BANK_SAMPLES] = np.clip(np.round(ho_samples * SCALE_FACTOR), 0, MAX_UINT16).astype(np.uint16)

    if sc["bubbles"]:
        shape = 1.0 / sc["sigma_s2"]
        scale = sc["sigma_s2"]
        hs_samples = stats.gamma.ppf(q_prob, a=shape, scale=scale)
        bank_hs[idx * BANK_SAMPLES : (idx + 1) * BANK_SAMPLES] = np.clip(np.round(hs_samples * SCALE_FACTOR), 0, MAX_UINT16).astype(np.uint16)
    else:
        bank_hs[idx * BANK_SAMPLES : (idx + 1) * BANK_SAMPLES] = np.ones(BANK_SAMPLES, dtype=np.uint16) * SCALE_FACTOR

export_mif("lut_ho_bank_65536.mif", bank_ho, BANK_DEPTH)
export_mif("lut_hs_bank_65536.mif", bank_hs, BANK_DEPTH)

print(f"\n=== COPY KHỐI SAU VÀO case (auto_sw) DÀNH CHO {env_name} ===")
print(ls_verilog)
# ============================================================
# 8. TẠO FILE SKR PENALTY LUT (Dùng chung cho mọi môi trường)
# ============================================================
skr_penalty = np.zeros(1024)

for i in range(1024):
    qber = i / 1024.0

    if qber <= 0:
        skr_penalty[i] = 1.0
    elif qber < 0.11:
        hq = -qber * np.log2(qber) - (1 - qber) * np.log2(1 - qber)
        skr_penalty[i] = max(0.0, 1.0 - 2.0 * hq)
    else:
        skr_penalty[i] = 0.0

skr_penalty_fixed = np.clip(
    np.round(skr_penalty * SCALE_FACTOR),
    0,
    MAX_UINT16
).astype(np.uint16)

export_mif("lut_skr_penalty.mif", skr_penalty_fixed, 1024)
print("[+] Đã tạo file lut_skr_penalty.mif (DEPTH = 1024)")