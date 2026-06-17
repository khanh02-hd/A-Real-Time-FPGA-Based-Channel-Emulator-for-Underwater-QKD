import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# 1. THÔNG SỐ HỆ THỐNG
# ============================================================
D_RX = 0.1                         # Receiver aperture diameter, 10 cm
THETA_DIV_DEG = 6.0                # Beam divergence angle in degree
THETA_DIV = np.deg2rad(THETA_DIV_DEG)

F_SCATTER = 1.0                    # Attenuation/scattering scaling factor

# ============================================================
# 2. THÔNG SỐ QKD / DETECTOR
# ============================================================
N_S_ALICE = 1.0                    # Mean photon number per pulse
ETA_BOB = 0.5                      # Bob detector quantum efficiency

# Chỉ dùng để minh họa công suất quang cổ điển.
# Không dùng trực tiếp trong FPGA QKD.
P_TX_MW = 6.0

# Fixed-point scale Q0.32
Q0_32 = 2**32

# Dải khoảng cách khớp với FPGA auto-sweep
D_MIN = 1.0
D_MAX = 7.0
D_STEP_FPGA = 0.1


# ============================================================
# 3. HỆ SỐ SUY HAO NƯỚC
# ============================================================
WATER_TYPES = {
    "Clear_Water": {
        "label": "Clear Water (c=0.151)",
        "c": 0.151,
    },
    "Coastal_Water": {
        "label": "Coastal Water (c=0.398)",
        "c": 0.398,
    },
    "Turbid_Harbor": {
        "label": "Turbid Harbor (c=2.195)",
        "c": 2.195,
    },
}


# ============================================================
# 4. HÀM TÍNH TOÁN
# ============================================================
def mw_to_dbm(p_mw: float) -> float:
    """Convert power from mW to dBm."""
    if p_mw <= 0:
        return -np.inf
    return 10.0 * np.log10(p_mw)


def to_q0_32(x: float) -> int:
    """
    Convert a coefficient in [0, 1] to unsigned Q0.32.

    Q0.32 max value is 2^32 - 1.
    """
    x_clip = float(np.clip(x, 0.0, 1.0))

    if x_clip >= 1.0:
        return Q0_32 - 1

    return int(np.floor(x_clip * Q0_32))


def calculate_path_loss(d_m: float, c_coeff: float) -> float:
    """
    Underwater optical path loss:

        L_s(d) = geometric_loss(d) * attenuation_loss(d)

    where:

        geometric_loss = D_rx^2 / [pi * (d * tan(theta_div))^2]
        attenuation_loss = exp(-F_scatter * c * d)

    L_s is clipped to [0, 1].
    """
    if d_m <= 0:
        return 1.0

    beam_radius_term = d_m * np.tan(THETA_DIV)

    geometric_loss = (D_RX ** 2) / (np.pi * (beam_radius_term ** 2))
    attenuation_loss = np.exp(-F_SCATTER * c_coeff * d_m)

    L_s = geometric_loss * attenuation_loss

    return float(np.clip(L_s, 0.0, 1.0))


def calculate_link_values(d_m: float, c_coeff: float):
    """
    Return:

        L_s      : physical path loss coefficient
        L_eff    : effective QKD coefficient used in FPGA
        P_rx_mW  : illustrative received optical power
        P_det_mW : illustrative detected optical power

    FPGA should use:

        L_eff = N_S_ALICE * ETA_BOB * L_s

    Note:
    In Verilog, your variable is named L_s_const, but its value should
    be L_eff_const in Q0.32.
    """
    L_s = calculate_path_loss(d_m, c_coeff)

    L_eff = N_S_ALICE * ETA_BOB * L_s
    L_eff = float(np.clip(L_eff, 0.0, 1.0))

    P_rx_mW = P_TX_MW * L_s
    P_det_mW = ETA_BOB * P_rx_mW

    return L_s, L_eff, P_rx_mW, P_det_mW


# ============================================================
# 5. VẼ 3 ĐỒ THỊ: L_s, L_eff, P_rx
# ============================================================
def plot_channel_curves():
    distances = np.linspace(D_MIN, D_MAX, 300)

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(21, 6),
        constrained_layout=True
    )

    ax1, ax2, ax3 = axes

    for _, env in WATER_TYPES.items():
        label = env["label"]
        c = env["c"]

        L_s_values = []
        L_eff_values = []
        P_rx_values = []

        for d in distances:
            L_s, L_eff, P_rx_mW, _ = calculate_link_values(d, c)
            L_s_values.append(L_s)
            L_eff_values.append(L_eff)
            P_rx_values.append(P_rx_mW)

        ax1.plot(distances, L_s_values, linewidth=2, label=label)
        ax2.plot(distances, L_eff_values, linewidth=2, label=label)
        ax3.plot(distances, P_rx_values, linewidth=2, label=label)

    ax1.set_title(r"Underwater Optical Path Loss $L_s(d)$", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Link distance d (m)", fontsize=11)
    ax1.set_ylabel(r"$L_s$", fontsize=12)
    ax1.set_yscale("log")
    ax1.grid(True, which="both", linestyle="--", alpha=0.5)
    ax1.legend(fontsize=9)

    ax2.set_title(r"Effective QKD Coefficient $L_{\mathrm{eff}}(d)$", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Link distance d (m)", fontsize=11)
    ax2.set_ylabel(r"$L_{\mathrm{eff}} = \mu_A \eta_B L_s$", fontsize=12)
    ax2.set_yscale("log")
    ax2.grid(True, which="both", linestyle="--", alpha=0.5)
    ax2.legend(fontsize=9)

    ax3.set_title(r"Illustrative Received Power $P_{rx}$", fontsize=13, fontweight="bold")
    ax3.set_xlabel("Link distance d (m)", fontsize=11)
    ax3.set_ylabel(r"$P_{rx}$ (mW)", fontsize=12)
    ax3.set_yscale("log")
    ax3.grid(True, which="both", linestyle="--", alpha=0.5)
    ax3.legend(fontsize=9)

    fig.suptitle(
        f"Underwater Optical Link Parameters, P_tx = {P_TX_MW} mW",
        fontsize=15,
        fontweight="bold"
    )

    plt.savefig("Underwater_Channel_Loss_Leff_Prx.png", dpi=300, bbox_inches="tight")
    plt.show()


# ============================================================
# 6. VẼ RIÊNG L_eff CHO BÁO CÁO
# ============================================================
def plot_leff_only():
    distances = np.linspace(D_MIN, D_MAX, 300)

    plt.figure(figsize=(8, 6))

    for _, env in WATER_TYPES.items():
        label = env["label"]
        c = env["c"]

        L_eff_values = []

        for d in distances:
            _, L_eff, _, _ = calculate_link_values(d, c)
            L_eff_values.append(L_eff)

        plt.plot(distances, L_eff_values, linewidth=2.5, label=label)

    plt.title(r"Effective QKD Link Coefficient $L_{\mathrm{eff}}(d)$", fontsize=14, fontweight="bold")
    plt.xlabel("Link distance d (m)", fontsize=12)
    plt.ylabel(r"$L_{\mathrm{eff}} = \mu_A \eta_B L_s$", fontsize=12)
    plt.yscale("log")
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()
    plt.savefig("Effective_QKD_Link_Coefficient.png", dpi=300, bbox_inches="tight")
    plt.show()


# ============================================================
# 7. IN BẢNG 4 MỐC KIỂM TRA
# ============================================================
def print_test_points():
    print("=== KIỂM TRA MỘT SỐ MỐC ĐẠI DIỆN ===")
    print(f"D_rx        = {D_RX} m")
    print(f"theta_div   = {THETA_DIV_DEG} deg")
    print(f"F_scatter   = {F_SCATTER}")
    print(f"P_tx        = {P_TX_MW} mW  # chỉ minh họa công suất")
    print(f"nS_alice    = {N_S_ALICE}")
    print(f"eta_bob     = {ETA_BOB}")
    print()
    print("Ghi chú:")
    print("    L_s       = geometric_loss * exp(-c*d)")
    print("    L_eff     = nS_alice * eta_bob * L_s")
    print("    FPGA dùng L_eff_const Q0.32")
    print("    Trong Verilog biến tên L_s_const nhưng giá trị là L_eff_const")
    print()

    test_distances = [1.0, 3.0, 5.0, 7.0]

    for _, env in WATER_TYPES.items():
        print(f"\n--- {env['label']} ---")
        c = env["c"]

        for d in test_distances:
            L_s, L_eff, P_rx_mW, P_det_mW = calculate_link_values(d, c)

            L_s_const = to_q0_32(L_s)
            L_eff_const = to_q0_32(L_eff)

            print(f"d = {d:>4.1f} m | c = {c:.3f}")
            print(f"    L_s                  = {L_s:.6e}")
            print(f"    L_s_const Q0.32      = 32'd{L_s_const}")
            print(f"    L_eff                = {L_eff:.6e}")
            print(f"    L_eff_const FPGA     = 32'd{L_eff_const}")
            print(f"    P_rx                 = {P_rx_mW:.6e} mW = {mw_to_dbm(P_rx_mW):.2f} dBm")
            print(f"    P_det = eta * P_rx   = {P_det_mW:.6e} mW = {mw_to_dbm(P_det_mW):.2f} dBm")
            print()


# ============================================================
# 8. SINH VERILOG CASE CHO AUTO-SWEEP 61 MỐC
#
# auto_sw:
#   0  -> 1.0 m
#   1  -> 1.1 m
#   ...
#   60 -> 7.0 m
#
# Trong top_qkd_receiver.v, biến vẫn tên là L_s_const.
# Nhưng giá trị copy vào phải là L_eff_const.
# ============================================================
def print_verilog_case_for_env(env_key: str):
    if env_key not in WATER_TYPES:
        raise ValueError(f"Unknown env_key: {env_key}")

    env = WATER_TYPES[env_key]
    c = env["c"]

    print()
    print("============================================================")
    print(f"VERILOG CASE FOR {env_key}")
    print(f"{env['label']}")
    print("auto_sw = 0 -> 1.0 m, ..., auto_sw = 60 -> 7.0 m")
    print("NOTE: L_s_const variable stores L_eff_const = nS_alice * eta_bob * L_s in Q0.32")
    print("============================================================")
    print()

    print("always @(*) begin")
    print("    case (auto_sw)")

    for idx in range(61):
        d = D_MIN + D_STEP_FPGA * idx

        L_s, L_eff, _, _ = calculate_link_values(d, c)
        L_eff_const = to_q0_32(L_eff)

        sw_bin = format(idx, "06b")

        print(
            f"        6'b{sw_bin}: L_s_const = 32'd{L_eff_const}; "
            f"// d={d:.1f}m, L_eff={L_eff:.6e}"
        )

    print("        default:   L_s_const = 32'd0;")
    print("    endcase")
    print("end")


# ============================================================
# 9. MAIN
# ============================================================
if __name__ == "__main__":
    plot_channel_curves()

    plot_leff_only()

    print_test_points()

    # Chọn môi trường muốn sinh bảng Verilog:
    #   "Clear_Water"
    #   "Coastal_Water"
    #   "Turbid_Harbor"
    TARGET_ENV = "Clear_Water"

    print_verilog_case_for_env(TARGET_ENV)