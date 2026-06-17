import serial
import struct
import time
import glob

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ============================================================
# 1. CẤU HÌNH UART
# ============================================================
SERIAL_PORT = "COM16"       # Đổi lại đúng cổng COM của DE2-115
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0

# ============================================================
# 2. CẤU HÌNH AUTO-SWEEP 61 MỐC
# FPGA:
#   auto_sw = 0  -> 1.0 m
#   auto_sw = 1  -> 1.1 m
#   ...
#   auto_sw = 60 -> 7.0 m
#
# Verilog đang giữ mỗi mốc 5 packet.
# Python bỏ packet đầu sau khi đổi mốc, lấy trung bình 4 packet còn lại.
# ============================================================
NUM_SWEEP_POINTS = 61
SAMPLES_PER_DISTANCE = 4
SKIP_FIRST_PACKET_AFTER_SWITCH = True

SCENARIO_MAP = {
    i: f"{1.0 + i * 0.1:.1f}m"
    for i in range(NUM_SWEEP_POINTS)
}

VALID_ENV_NAMES = [
    "Clear_Water",
    "Coastal_Water",
    "Turbid_Harbor",
]

MIN_SIFTED_SAFE = 1000
QBER_LIMIT = 0.11


# ============================================================
# 3. ĐỌC GÓI UART 16 BYTE TỪ FPGA
#
# Packet format:
#
# byte 0  : 0xAA
# byte 1  : final_skr[31:24]
# byte 2  : final_skr[23:16]
# byte 3  : final_skr[15:8]
# byte 4  : final_skr[7:0]
# byte 5  : {SW[5:0], QBER[9:8]}
# byte 6  : QBER[7:0]
# byte 7  : n_sifted[31:24]
# byte 8  : n_sifted[23:16]
# byte 9  : n_sifted[15:8]
# byte 10 : n_sifted[7:0]
# byte 11 : n_error[31:24]
# byte 12 : n_error[23:16]
# byte 13 : n_error[15:8]
# byte 14 : n_error[7:0]
# byte 15 : 0x55
# ============================================================
def read_one_packet(ser: serial.Serial):
    b = ser.read(1)

    if len(b) != 1 or b[0] != 0xAA:
        return None

    rest = ser.read(15)

    if len(rest) != 15:
        return None

    if rest[14] != 0x55:
        return None

    final_skr = struct.unpack(">I", rest[0:4])[0]

    # rest[4] = [SW5 SW4 SW3 SW2 SW1 SW0 QBER9 QBER8]
    sw_state = (rest[4] >> 2) & 0x3F

    qber_high = rest[4] & 0x03
    qber_low = rest[5]
    qber_idx = (qber_high << 8) | qber_low

    n_sifted = struct.unpack(">I", rest[6:10])[0]
    n_error = struct.unpack(">I", rest[10:14])[0]

    return final_skr, qber_idx, n_sifted, n_error, sw_state


def get_status(final_skr: int, n_sifted: int, n_error: int):
    qber_pc = (n_error / n_sifted) if n_sifted > 0 else 0.0

    if n_sifted < MIN_SIFTED_SAFE:
        return "OUTAGE"
    elif final_skr == 0 or qber_pc >= QBER_LIMIT:
        return "ALERT"
    else:
        return "SAFE"


# ============================================================
# 4. VẼ ĐỒ THỊ GỘP TỪ CÁC FILE CSV
# ============================================================
def draw_comparative_plots():
    csv_files = sorted(glob.glob("*_qkd_data.csv"))

    if not csv_files:
        print("[!] Không tìm thấy file *_qkd_data.csv để vẽ đồ thị.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    markers = ["o", "s", "^", "D", "v", "x", "*"]
    markevery_val = 2

    for idx, filename in enumerate(csv_files):
        env_name = filename.replace("_qkd_data.csv", "")
        df = pd.read_csv(filename)

        marker = markers[idx % len(markers)]

        ax1.plot(
            df["Distance(m)"],
            df["QBER(%)"],
            marker=marker,
            markevery=markevery_val,
            linestyle="-",
            linewidth=2,
            markersize=6,
            label=env_name.replace("_", " "),
        )

        skr_plot = df["SKR(bps)"].replace(0, np.nan)

        ax2.semilogy(
            df["Distance(m)"],
            skr_plot,
            marker=marker,
            markevery=markevery_val,
            linestyle="-",
            linewidth=2,
            markersize=6,
            label=env_name.replace("_", " "),
        )

    ax1.axhline(
        y=11.0,
        color="black",
        linestyle="--",
        label="BB84 limit 11%",
    )

    ax1.set_xlabel("Link Distance (m)", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Quantum Bit Error Rate (%)", fontsize=12, fontweight="bold")
    ax1.set_title("Comparative QBER Performance", fontsize=14)
    ax1.grid(True, which="both", linestyle="--", alpha=0.6)
    ax1.legend()

    ax2.set_xlabel("Link Distance (m)", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Secret Key Rate (bps)", fontsize=12, fontweight="bold")
    ax2.set_title("Comparative SKR Performance", fontsize=14)
    ax2.grid(True, which="both", linestyle="--", alpha=0.6)
    ax2.legend()

    plt.tight_layout()
    plt.savefig("Comparative_QKD_Results.png", dpi=300, bbox_inches="tight")
    print("\n[*] Đã lưu đồ thị so sánh gộp: Comparative_QKD_Results.png")
    plt.show()


# ============================================================
# 5. CHỜ FPGA RESET VỀ MỐC 1.0m
# ============================================================
def wait_for_sweep_start(ser: serial.Serial):
    print("[*] Xóa buffer UART cũ...")
    ser.reset_input_buffer()

    print("[*] Đang chờ packet đầu tiên có sw_state = 0 tương ứng 1.0m...")

    while True:
        res = read_one_packet(ser)

        if res is None:
            continue

        _, _, _, _, sw_state = res

        if sw_state == 0:
            print("[+] Đã bắt được mốc 1.0m. Bắt đầu thu thập dữ liệu.\n")
            return res

        if sw_state <= 60:
            print(f"    Đang thấy FPGA ở mốc {SCENARIO_MAP[sw_state]}, chờ reset về 1.0m...")
        else:
            print(f"    Bỏ qua packet lỗi: sw_state={sw_state}")


# ============================================================
# 6. LƯU MỘT MỐC ĐO VÀO MẢNG KẾT QUẢ
# ============================================================
def save_current_point(
    env_name,
    current_sw,
    valid_samples,
    sum_qber,
    sum_skr,
    sum_sifted,
    sum_error,
    qber_results,
    skr_results,
    sifted_results,
    error_results,
    collected_distances,
):
    if current_sw < 0 or current_sw >= NUM_SWEEP_POINTS:
        return

    if valid_samples <= 0:
        print(f"[!] Mốc {SCENARIO_MAP[current_sw]} không có mẫu hợp lệ, bỏ qua.")
        return

    avg_qber = (sum_qber / valid_samples) * 100.0
    avg_skr = sum_skr / valid_samples
    avg_sifted = sum_sifted / valid_samples
    avg_error = sum_error / valid_samples

    qber_results.append(avg_qber)
    skr_results.append(avg_skr)
    sifted_results.append(avg_sifted)
    error_results.append(avg_error)
    collected_distances.append(round(1.0 + current_sw * 0.1, 1))

    sample_note = ""
    if valid_samples != SAMPLES_PER_DISTANCE:
        sample_note = f"  [cảnh báo: chỉ có {valid_samples}/{SAMPLES_PER_DISTANCE} mẫu]"

    print(
        f"[+] ĐÃ LƯU MỐC {SCENARIO_MAP[current_sw]}: "
        f"QBER={avg_qber:.2f}%, "
        f"SKR={avg_skr:.0f} bps, "
        f"SIFTED={avg_sifted:.0f}, "
        f"ERROR={avg_error:.0f}"
        f"{sample_note}"
    )


# ============================================================
# 7. CHƯƠNG TRÌNH ĐO ĐẠC CHÍNH
# ============================================================
def main():
    print("=== CÔNG CỤ THU THẬP DỮ LIỆU TỰ ĐỘNG UWOC-QKD ===")
    print("Môi trường khả dụng:", ", ".join(VALID_ENV_NAMES))
    print("Auto-sweep: 1.0m -> 7.0m, bước 0.1m, tổng 61 mốc.")
    print()

    env_name = input("Nhập tên môi trường đang đo: ").strip()

    if env_name not in VALID_ENV_NAMES:
        print(f"[!] Cảnh báo: '{env_name}' không nằm trong danh sách chuẩn.")
        print("    Nên dùng: Clear_Water, Coastal_Water, Turbid_Harbor")
        confirm = input("Vẫn tiếp tục? (y/n): ").strip().lower()

        if confirm != "y":
            print("[*] Đã hủy.")
            return

    qber_results = []
    skr_results = []
    sifted_results = []
    error_results = []
    collected_distances = []

    ser = None

    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            timeout=SERIAL_TIMEOUT,
        )

        print(f"\n[*] Kết nối {SERIAL_PORT} @ {BAUD_RATE} bps thành công.")
        print("[*] Hãy bấm RESET KEY0 trên DE2-115 để FPGA chạy lại từ 1.0m.")
        input("[*] Sau khi bấm RESET, nhấn Enter để bắt đầu chờ dữ liệu...")

        pending_packet = wait_for_sweep_start(ser)

        current_sw = -1

        sum_qber = 0.0
        sum_skr = 0.0
        sum_sifted = 0.0
        sum_error = 0.0

        valid_samples = 0
        is_first_packet = True

        while True:
            if pending_packet is not None:
                res = pending_packet
                pending_packet = None
            else:
                res = read_one_packet(ser)

            if res is None:
                continue

            final_skr, qber_idx, n_sifted, n_error, sw_state = res

            if sw_state >= NUM_SWEEP_POINTS:
                print(f"[!] Bỏ qua packet lỗi: sw_state={sw_state}")
                continue

            # ----------------------------------------------------
            # FPGA chuyển sang mốc mới
            # ----------------------------------------------------
            if sw_state != current_sw:
                save_current_point(
                    env_name,
                    current_sw,
                    valid_samples,
                    sum_qber,
                    sum_skr,
                    sum_sifted,
                    sum_error,
                    qber_results,
                    skr_results,
                    sifted_results,
                    error_results,
                    collected_distances,
                )

                current_sw = sw_state

                sum_qber = 0.0
                sum_skr = 0.0
                sum_sifted = 0.0
                sum_error = 0.0

                valid_samples = 0
                is_first_packet = True

                print(f"\n🔄 Đang thu thập dữ liệu tại: {SCENARIO_MAP[current_sw]}")

            # ----------------------------------------------------
            # Bỏ packet đầu mỗi mốc để tránh dữ liệu chuyển trạng thái
            # ----------------------------------------------------
            if SKIP_FIRST_PACKET_AFTER_SWITCH and is_first_packet:
                is_first_packet = False
                print("   [~] Bỏ qua packet đầu của mốc này.")
                continue

            is_first_packet = False

            # ----------------------------------------------------
            # Cộng dồn packet hợp lệ
            # ----------------------------------------------------
            qber_pc_val = (n_error / n_sifted) if n_sifted > 0 else 0.0
            qber_pc_pct = qber_pc_val * 100.0
            qber_fpga_pct = (qber_idx / 1024.0) * 100.0

            sum_qber += qber_pc_val
            sum_skr += final_skr
            sum_sifted += n_sifted
            sum_error += n_error

            valid_samples += 1

            status = get_status(final_skr, n_sifted, n_error)

            print(
                f"   => Mẫu {valid_samples}/{SAMPLES_PER_DISTANCE}: "
                f"SIFTED={n_sifted:<10d} | "
                f"ERROR={n_error:<8d} | "
                f"QBER_FPGA={qber_fpga_pct:>6.2f}% | "
                f"QBER_PC={qber_pc_pct:>6.2f}% | "
                f"SKR={final_skr:<10d} | "
                f"STATUS={status}"
            )

            # ----------------------------------------------------
            # Điểm dừng: đã ở 7.0m và lấy đủ 4 mẫu
            # ----------------------------------------------------
            if current_sw == 60 and valid_samples >= SAMPLES_PER_DISTANCE:
                save_current_point(
                    env_name,
                    current_sw,
                    valid_samples,
                    sum_qber,
                    sum_skr,
                    sum_sifted,
                    sum_error,
                    qber_results,
                    skr_results,
                    sifted_results,
                    error_results,
                    collected_distances,
                )

                print("\n✅ FPGA đã quét xong 61 mốc từ 1.0m đến 7.0m.")
                break

        # --------------------------------------------------------
        # Lưu CSV
        # --------------------------------------------------------
        df = pd.DataFrame(
            {
                "Environment": [env_name] * len(collected_distances),
                "Distance(m)": collected_distances,
                "QBER(%)": qber_results,
                "SKR(bps)": skr_results,
                "Avg_Sifted": sifted_results,
                "Avg_Error": error_results,
            }
        )

        csv_filename = f"{env_name}_qkd_data.csv"
        df.to_csv(csv_filename, index=False)

        print(f"\n[*] Đã lưu toàn bộ dữ liệu vào file: {csv_filename}")
        print(f"[*] Số mốc đã lưu: {len(collected_distances)}/61")

        draw_comparative_plots()

    except serial.SerialException as e:
        print(f"\n[!] Lỗi cổng UART: {e}")

    except KeyboardInterrupt:
        print("\n[*] Dừng sớm bằng Ctrl+C.")

        if len(collected_distances) > 0:
            df = pd.DataFrame(
                {
                    "Environment": [env_name] * len(collected_distances),
                    "Distance(m)": collected_distances,
                    "QBER(%)": qber_results,
                    "SKR(bps)": skr_results,
                    "Avg_Sifted": sifted_results,
                    "Avg_Error": error_results,
                }
            )

            csv_filename = f"{env_name}_partial_qkd_data.csv"
            df.to_csv(csv_filename, index=False)
            print(f"[*] Đã lưu dữ liệu đo dở vào file: {csv_filename}")

    except Exception as e:
        print(f"\n[!] Lỗi: {e}")

    finally:
        if ser is not None and ser.is_open:
            ser.close()


if __name__ == "__main__":
    main()