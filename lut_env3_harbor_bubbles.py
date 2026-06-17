import numpy as np
import scipy.integrate as integrate
import scipy.stats as stats
from scipy.special import gamma

# ============================================================
# FILE: lut_env3_harbor_bubbles.py
# ENV 3: TURBID HARBOR / HARBOR WATER
#
# Mô hình kênh:
#   h(s,t) = L(s) · h_o(s,t) · h_s(s,t)
#
# Trong file này:
#   L(s)      : path loss theo Beer-Lambert + geometric loss
#   h_o(s,t) : Weibull oceanic turbulence
#   h_s(s,t) : Gamma scattering / bubbles fading
# ============================================================

# ============================================================
# 1. THÔNG SỐ QKD / THIẾT BỊ
# ============================================================

mu_alice = 1.0       # nS = số photon trung bình mỗi xung
eta_bob  = 0.5       # hiệu suất đầu dò Bob

# Nếu muốn in công suất tương đương của laser QKD
f_rep = 50e6         # tốc độ pulse giả định = 50 MHz

# ============================================================
# 2. THÔNG SỐ MÔI TRƯỜNG TURBID HARBOR
# ============================================================

env_name = "Turbid_Harbor"

# Hệ số suy hao nước đục / harbor
c_fixed = 2.195      # 1/m

# Bật scattering/bubbles
bubbles_enabled = True

# Variance của scattering-induced fading
# Lớn hơn Coastal để mô phỏng harbor/turbid nhiều bọt và hạt tán xạ.
sigma_s2_fixed = 0.05

# Thông số turbulence theo mô hình Nikishov
chi_T   = 1e-5
epsilon = 1e-5
w_ratio = -2.2

# Weibull shape cho strong/turbid turbulence
# beta nhỏ hơn -> fading mạnh hơn, nhiều deep fade hơn.
# Gợi ý:
#   beta = 2.5 ~ nhẹ
#   beta = 2.0 ~ vừa
#   beta = 1.5 ~ mạnh
#   beta = 1.2 ~ rất mạnh
WEIBULL_BETA = 1.5

# ============================================================
# 3. THÔNG SỐ QUANG HỌC / FIXED-POINT
# ============================================================

lamda = 530e-9       # 530 nm
n_water = 1.333

D_rx = 0.1           # đường kính aperture thu = 10 cm
theta_div = 6 * np.pi / 180
F_scatter = 1.0

k_wave = (2 * np.pi * n_water) / lamda
eta_K = 1e-3

SCALE_FACTOR = 1 << 12      # UQ4.12: 1.0 = 4096
MAX_UINT16 = (1 << 16) - 1
Q0_32 = 2**32

BANK_SAMPLES = 1024
BANK_DEPTH = 65536

# 61 mốc: 1.0 m -> 7.0 m, bước 0.1 m
distances = np.round(np.arange(1.0, 7.1, 0.1), 1)

# ============================================================
# 4. KHỞI TẠO SCENARIO / BANK
# ============================================================

scenarios = []
for i, d in enumerate(distances):
    scenarios.append({
        "sw": format(i, "06b"),
        "d": float(d),
        "bubbles": bubbles_enabled,
        "sigma_s2": sigma_s2_fixed,
        "c": c_fixed
    })

TOTAL_SCENARIOS = len(scenarios)

bank_ho = np.ones(BANK_DEPTH, dtype=np.uint16) * SCALE_FACTOR
bank_hs = np.ones(BANK_DEPTH, dtype=np.uint16) * SCALE_FACTOR

# Quantile probability tránh 0 và 1 tuyệt đối
q_prob = np.linspace(
    0.5 / BANK_SAMPLES,
    1.0 - 0.5 / BANK_SAMPLES,
    BANK_SAMPLES
)

# ============================================================
# 5. HÀM TÍNH TOÁN VẬT LÝ
# ============================================================

def calculate_path_loss(d_distance, c_coeff):
    """
    L(s) = geometric_loss · attenuation_loss

    geometric_loss = D_rx^2 / [pi · (d · tan(theta_div))^2]
    attenuation_loss = exp(-F_scatter · c · d)
    """
    if d_distance <= 0:
        return 1.0

    beam_radius_term = d_distance * np.tan(theta_div)

    geometric_loss = (D_rx ** 2) / (np.pi * (beam_radius_term ** 2))
    attenuation_loss = np.exp(-F_scatter * c_coeff * d_distance)

    total_loss = geometric_loss * attenuation_loss

    return float(np.clip(total_loss, 0.0, 1.0))


def nikishov_spectrum(kappa):
    """
    Nikishov spectrum cho underwater optical turbulence.
    Dùng để ước lượng sigma_I2, phục vụ báo cáo/kiểm tra mức turbulence.
    Trong bản Turbid này, LUT h_o dùng Weibull thay vì log-normal.
    """
    safe_k = np.where(kappa == 0, np.finfo(float).tiny, kappa)

    delta = (
        8.284 * (safe_k * eta_K) ** (4 / 3)
        + 12.978 * (safe_k * eta_K) ** 2
    )

    Phi_n = (
        0.388e-8
        * (epsilon ** (-1 / 3))
        * (safe_k ** (-11 / 3))
        * (1 + 2.35 * (safe_k * eta_K) ** (2 / 3))
        * (chi_T / (w_ratio ** 2))
        * (
            np.exp(-1.863e-2 * delta)
            + np.exp(-1.9e-4 * delta)
            - 2 * w_ratio * np.exp(-9.41e-3 * delta)
        )
    )

    return np.where(kappa == 0, 0.0, Phi_n)


def calculate_sigma_i2(d_distance):
    """
    Tính scintillation index sigma_I2 từ Nikishov spectrum.
    Giá trị này dùng để log/đánh giá mức turbulence.
    """
    def integrand(k, xi):
        return (
            k
            * nikishov_spectrum(k)
            * (1 - np.cos((d_distance * (k ** 2) * xi) / k_wave))
        )

    res, _ = integrate.dblquad(
        integrand,
        0, 1,
        lambda xi: 1e-4,
        lambda xi: 1.0 / eta_K
    )

    return float(8 * np.pi * (k_wave ** 2) * d_distance * res)


def generate_weibull_ho_samples(q_array, beta):
    """
    Sinh h_o theo Weibull turbulence.

    Weibull mean:
        E[X] = scale · Gamma(1 + 1/beta)

    Chọn:
        scale = 1 / Gamma(1 + 1/beta)

    để E[h_o] ≈ 1.
    Như vậy fading chỉ làm dao động quanh 1,
    không tự ý tăng/giảm công suất trung bình.
    """
    weibull_scale = 1.0 / gamma(1.0 + 1.0 / beta)

    samples = stats.weibull_min.ppf(
        q_array,
        c=beta,
        scale=weibull_scale
    )

    return samples


def generate_gamma_hs_samples(q_array, sigma_s2):
    """
    Sinh h_s theo Gamma scattering/bubbles fading.

    Với shape = 1/sigma_s2, scale = sigma_s2:
        mean = shape · scale = 1
        var  = shape · scale^2 = sigma_s2
    """
    shape = 1.0 / sigma_s2
    scale = sigma_s2

    samples = stats.gamma.ppf(
        q_array,
        a=shape,
        scale=scale
    )

    return samples


def to_uq4_12(samples):
    """
    Đổi mẫu floating-point sang UQ4.12 uint16.
    """
    fixed = np.round(samples * SCALE_FACTOR)
    fixed = np.clip(fixed, 0, MAX_UINT16)

    return fixed.astype(np.uint16)


def export_mif(filename, data_array, depth):
    """
    Xuất file .mif cho Quartus ROM.
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"DEPTH = {depth};\n")
        f.write("WIDTH = 16;\n")
        f.write("ADDRESS_RADIX = DEC;\n")
        f.write("DATA_RADIX = BIN;\n")
        f.write("CONTENT\n")
        f.write("BEGIN\n")

        for i in range(depth):
            f.write(f"{i:5d} : {format(int(data_array[i]), '016b')};\n")

        f.write("END;\n")


# ============================================================
# 6. IN CÔNG SUẤT LASER QKD TƯƠNG ĐƯƠNG
# ============================================================

h_planck = 6.62607015e-34
c_light = 299792458.0

E_photon = h_planck * c_light / lamda
P_tx_equiv_W = mu_alice * f_rep * E_photon
P_tx_equiv_dBm = 10 * np.log10(P_tx_equiv_W / 1e-3)

print("============================================================")
print(f"ENVIRONMENT: {env_name}")
print("============================================================")
print(f"mu_alice                 = {mu_alice}")
print(f"eta_bob                  = {eta_bob}")
print(f"lambda                   = {lamda * 1e9:.1f} nm")
print(f"Equivalent QKD P_tx      = {P_tx_equiv_W:.3e} W")
print(f"Equivalent QKD P_tx      = {P_tx_equiv_dBm:.2f} dBm")
print(f"Water attenuation c      = {c_fixed} 1/m")
print(f"Weibull beta for h_o     = {WEIBULL_BETA}")
print(f"Gamma sigma_s2 for h_s   = {sigma_s2_fixed}")
print("============================================================\n")

# ============================================================
# 7. SINH LUT
# ============================================================

print(f"[*] Đang tạo LUT cho môi trường: {env_name}")

ls_verilog = ""
summary_lines = []

for idx, sc in enumerate(scenarios):
    d = sc["d"]

    # --------------------------------------------------------
    # 7.1 Path loss L(s)
    # --------------------------------------------------------
    channel_loss = calculate_path_loss(d, sc["c"])

    # L_eff = mu_alice · eta_bob · L(s)
    L_s_effective = mu_alice * eta_bob * channel_loss

    # Q0.32 fixed-point
    L_s_const = int(np.clip(L_s_effective, 0.0, 1.0) * Q0_32)

    ls_verilog += (
        f"            6'b{sc['sw']}: L_s_const = 32'd{L_s_const}; "
        f"// d={d:.1f}m, L_eff={L_s_effective:.6e}\n"
    )

    # --------------------------------------------------------
    # 7.2 Turbulence h_o: Weibull
    # --------------------------------------------------------
    sigma_I2 = calculate_sigma_i2(d)

    ho_samples = generate_weibull_ho_samples(
        q_array=q_prob,
        beta=WEIBULL_BETA
    )

    bank_ho[
        idx * BANK_SAMPLES : (idx + 1) * BANK_SAMPLES
    ] = to_uq4_12(ho_samples)

    # --------------------------------------------------------
    # 7.3 Scattering/bubbles h_s: Gamma
    # --------------------------------------------------------
    if sc["bubbles"]:
        hs_samples = generate_gamma_hs_samples(
            q_array=q_prob,
            sigma_s2=sc["sigma_s2"]
        )
    else:
        hs_samples = np.ones(BANK_SAMPLES)

    bank_hs[
        idx * BANK_SAMPLES : (idx + 1) * BANK_SAMPLES
    ] = to_uq4_12(hs_samples)

    # --------------------------------------------------------
    # 7.4 Summary
    # --------------------------------------------------------
    summary_lines.append(
        f"d={d:.1f}m | "
        f"L_eff={L_s_effective:.3e} | "
        f"sigma_I2={sigma_I2:.3e} | "
        f"ho_mean={np.mean(ho_samples):.3f} | "
        f"ho_std={np.std(ho_samples):.3f} | "
        f"hs_mean={np.mean(hs_samples):.3f} | "
        f"hs_std={np.std(hs_samples):.3f}"
    )

    print(
        f"[{idx+1:02d}/{TOTAL_SCENARIOS}] "
        f"d={d:.1f}m | "
        f"L_eff={L_s_effective:.3e} | "
        f"sigma_I2={sigma_I2:.3e}"
    )

# ============================================================
# 8. XUẤT FILE MIF
# ============================================================

export_mif("lut_ho_bank_65536.mif", bank_ho, BANK_DEPTH)
export_mif("lut_hs_bank_65536.mif", bank_hs, BANK_DEPTH)

# Xuất thêm summary để kiểm tra
with open(f"summary_{env_name}.txt", "w", encoding="utf-8") as f:
    f.write(f"ENVIRONMENT: {env_name}\n")
    f.write(f"mu_alice = {mu_alice}\n")
    f.write(f"eta_bob = {eta_bob}\n")
    f.write(f"lambda = {lamda}\n")
    f.write(f"Equivalent P_tx = {P_tx_equiv_W:.6e} W = {P_tx_equiv_dBm:.2f} dBm\n")
    f.write(f"c_fixed = {c_fixed}\n")
    f.write(f"Weibull beta = {WEIBULL_BETA}\n")
    f.write(f"sigma_s2 = {sigma_s2_fixed}\n\n")

    for line in summary_lines:
        f.write(line + "\n")

print("\n[OK] Đã xuất:")
print("     lut_ho_bank_65536.mif")
print("     lut_hs_bank_65536.mif")
print(f"     summary_{env_name}.txt")

print(f"\n=== COPY KHỐI SAU VÀO case (auto_sw) DÀNH CHO {env_name} ===")
print(ls_verilog)