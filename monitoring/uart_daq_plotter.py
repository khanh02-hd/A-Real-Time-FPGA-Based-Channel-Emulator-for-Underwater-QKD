import serial
import struct
import glob
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ============================================================
# 1. UART CONFIG
# ============================================================

SERIAL_PORT = "COM16"       # Đổi lại đúng cổng COM của DE2-115
BAUD_RATE = 115200
SERIAL_TIMEOUT = 2.0

# Must match MAX_BYTES in qkd_sifted_key_extractor.v
MAX_KEY_PAYLOAD_BYTES = 512


# ============================================================
# 2. AUTO-SWEEP CONFIG
#
# FPGA:
#   auto_sw = 0  -> 1.0 m
#   auto_sw = 1  -> 1.1 m
#   ...
#   auto_sw = 60 -> 7.0 m
#
# Verilog đang giữ mỗi khoảng cách 5 frame.
# Python bỏ frame đầu sau khi đổi mốc, lấy trung bình 4 frame còn lại.
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
# 3. BYTE HELPERS
# ============================================================

def read_exact(ser: serial.Serial, n: int) -> bytes:
    """
    Read exactly n bytes from serial.
    pyserial may return partial data, so keep reading until enough bytes arrive.
    """
    data = bytearray()

    while len(data) < n:
        chunk = ser.read(n - len(data))

        if not chunk:
            raise TimeoutError(f"Timeout while reading {n} bytes")

        data.extend(chunk)

    return bytes(data)


def bytes_to_u32_be(b: bytes) -> int:
    """
    Convert 4 bytes big-endian to unsigned 32-bit integer.
    """
    return struct.unpack(">I", b)[0]


# ============================================================
# 4. NEW FRAME PARSER
#
# New FPGA frame format:
#
#   0xAA
#   14 bytes metric:
#       final_skr       : 4 bytes, big endian
#       sw/qber         : 2 bytes
#       n_sifted        : 4 bytes, big endian
#       n_error         : 4 bytes, big endian
#   0xBB
#   key_payload_length  : 2 bytes, little endian, in bytes
#   key_payload         : key_payload_length bytes
#   0x55
#
# This plotting script uses only metric data.
# It still reads/discards key payload to keep UART synchronization.
# ============================================================

def wait_for_frame_start(ser: serial.Serial) -> bool:
    """
    Wait until 0xAA is found.
    """
    while True:
        b = ser.read(1)

        if not b:
            return False

        if b[0] == 0xAA:
            return True


def parse_metric_payload(payload: bytes):
    """
    Parse 14-byte metric payload after 0xAA.
    """
    if len(payload) != 14:
        raise ValueError("Metric payload must be exactly 14 bytes")

    final_skr = bytes_to_u32_be(payload[0:4])

    # payload[4] = [SW5 SW4 SW3 SW2 SW1 SW0 QBER9 QBER8]
    sw_state = (payload[4] >> 2) & 0x3F

    qber_high = payload[4] & 0x03
    qber_low = payload[5]
    qber_idx = (qber_high << 8) | qber_low

    n_sifted = bytes_to_u32_be(payload[6:10])
    n_error = bytes_to_u32_be(payload[10:14])

    return final_skr, qber_idx, n_sifted, n_error, sw_state


def read_one_frame(ser: serial.Serial):
    """
    Read one complete new-format FPGA frame.

    Return:
        final_skr, qber_idx, n_sifted, n_error, sw_state, key_byte_count

    If frame is corrupted, return None and resync on next call.
    """
    try:
        ok = wait_for_frame_start(ser)

        if not ok:
            return None

        # 1. Metric payload
        metric_payload = read_exact(ser, 14)
        final_skr, qber_idx, n_sifted, n_error, sw_state = parse_metric_payload(metric_payload)

        # 2. Key header
        key_header = read_exact(ser, 1)[0]

        if key_header != 0xBB:
            print(f"[WARN] Expected key header 0xBB, got 0x{key_header:02X}. Resyncing...")
            return None

        # 3. Key payload length, little endian
        length_bytes = read_exact(ser, 2)
        key_byte_count = length_bytes[0] | (length_bytes[1] << 8)

        # 4. Sanity check
        if key_byte_count > MAX_KEY_PAYLOAD_BYTES:
            print(
                f"[WARN] Invalid key payload length: "
                f"{key_byte_count} bytes > {MAX_KEY_PAYLOAD_BYTES}. Resyncing..."
            )
            return None

        # 5. Read and discard key payload
        _ = read_exact(ser, key_byte_count)

        # 6. Footer
        footer = read_exact(ser, 1)[0]

        if footer != 0x55:
            print(f"[WARN] Expected footer 0x55, got 0x{footer:02X}. Resyncing...")
            return None

        return final_skr, qber_idx, n_sifted, n_error, sw_state, key_byte_count

    except TimeoutError as e:
        print(f"[WARN] {e}. Resyncing...")
        return None

    except ValueError as e:
        print(f"[WARN] {e}. Resyncing...")
        return None


def get_status(final_skr: int, n_sifted: int, n_error: int):
    """
    Return SAFE / ALERT / OUTAGE status.
    """
    qber_pc = (n_error / n_sifted) if n_sifted > 0 else 0.0

    if n_sifted < MIN_SIFTED_SAFE:
        return "OUTAGE"
    elif final_skr == 0 or qber_pc >= QBER_LIMIT:
        return "ALERT"
    else:
        return "SAFE"


# ============================================================
# 5. SAVE ONE DISTANCE POINT
# ============================================================

def save_current_point(
    env_name,
    current_sw,
    valid_samples,
    sum_qber,
    sum_skr,
    sum_sifted,
    sum_error,
    sum_key_bytes,
    qber_results,
    skr_results,
    sifted_results,
    error_results,
    key_bytes_results,
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
    avg_key_bytes = sum_key_bytes / valid_samples

    qber_results.append(avg_qber)
    skr_results.append(avg_skr)
    sifted_results.append(avg_sifted)
    error_results.append(avg_error)
    key_bytes_results.append(avg_key_bytes)
    collected_distances.append(round(1.0 + current_sw * 0.1, 1))

    sample_note = ""

    if valid_samples != SAMPLES_PER_DISTANCE:
        sample_note = f"  [cảnh báo: chỉ có {valid_samples}/{SAMPLES_PER_DISTANCE} mẫu]"

    print(
        f"[+] ĐÃ LƯU MỐC {SCENARIO_MAP[current_sw]}: "
        f"QBER={avg_qber:.2f}%, "
        f"SKR={avg_skr:.0f} bps, "
        f"SIFTED={avg_sifted:.0f}, "
        f"ERROR={avg_error:.0f}, "
        f"KEY_PAYLOAD={avg_key_bytes:.1f} bytes"
        f"{sample_note}"
    )


# ============================================================
# 6. WAIT FOR SWEEP START
# ============================================================

def wait_for_sweep_start(ser: serial.Serial):
    """
    Wait until FPGA returns to sw_state = 0.
    """
    print("[*] Xóa buffer UART cũ...")
    ser.reset_input_buffer()

    print("[*] Đang chờ frame đầu tiên có sw_state = 0 tương ứng 1.0m...")

    while True:
        res = read_one_frame(ser)

        if res is None:
            continue

        _, _, _, _, sw_state, _ = res

        if sw_state == 0:
            print("[+] Đã bắt được mốc 1.0m. Bắt đầu thu thập dữ liệu.\n")
            return res

        if 0 <= sw_state <= 60:
            print(f"    Đang thấy FPGA ở mốc {SCENARIO_MAP[sw_state]}, chờ reset về 1.0m...")
        else:
            print(f"    Bỏ qua frame lỗi: sw_state={sw_state}")


# ============================================================
# 7. DRAW COMPARATIVE PLOTS FROM CSV
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
        label = env_name.replace("_", " ")

        ax1.plot(
            df["Distance(m)"],
            df["QBER(%)"],
            marker=marker,
            markevery=markevery_val,
            linestyle="-",
            linewidth=2,
            markersize=6,
            label=label,
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
            label=label,
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


def draw_single_environment_plot(csv_filename: str):
    """
    Draw plots for one environment after collecting data.
    """
    df = pd.read_csv(csv_filename)

    env_name = df["Environment"].iloc[0] if "Environment" in df.columns else csv_filename

    plt.figure(figsize=(8, 5))
    plt.plot(
        df["Distance(m)"],
        df["QBER(%)"],
        marker="o",
        linestyle="-",
        linewidth=2,
        markersize=5,
        label=env_name.replace("_", " "),
    )

    plt.axhline(
        y=11.0,
        color="black",
        linestyle="--",
        label="BB84 limit 11%",
    )

    plt.xlabel("Link Distance (m)", fontsize=12, fontweight="bold")
    plt.ylabel("Quantum Bit Error Rate (%)", fontsize=12, fontweight="bold")
    plt.title(f"QBER vs Distance - {env_name.replace('_', ' ')}", fontsize=14)
    plt.grid(True, which="both", linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()

    qber_fig = f"{env_name}_QBER_vs_Distance.png"
    plt.savefig(qber_fig, dpi=300, bbox_inches="tight")
    print(f"[*] Đã lưu đồ thị: {qber_fig}")
    plt.show()

    plt.figure(figsize=(8, 5))

    skr_plot = df["SKR(bps)"].replace(0, np.nan)

    plt.semilogy(
        df["Distance(m)"],
        skr_plot,
        marker="s",
        linestyle="-",
        linewidth=2,
        markersize=5,
        label=env_name.replace("_", " "),
    )

    plt.xlabel("Link Distance (m)", fontsize=12, fontweight="bold")
    plt.ylabel("Secret Key Rate (bps)", fontsize=12, fontweight="bold")
    plt.title(f"SKR vs Distance - {env_name.replace('_', ' ')}", fontsize=14)
    plt.grid(True, which="both", linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()

    skr_fig = f"{env_name}_SKR_vs_Distance.png"
    plt.savefig(skr_fig, dpi=300, bbox_inches="tight")
    print(f"[*] Đã lưu đồ thị: {skr_fig}")
    plt.show()


# ============================================================
# 8. MAIN DATA ACQUISITION
# ============================================================

def main():
    print("=== UART DAQ PLOTTER FOR UWOC-QKD FPGA ===")
    print("Frame format: 0xAA + metric + 0xBB + key payload + 0x55")
    print("Auto-sweep: 1.0m -> 7.0m, step 0.1m, total 61 points.")
    print("Available environments:", ", ".join(VALID_ENV_NAMES))
    print()

    port_input = input(f"Nhập cổng COM [{SERIAL_PORT}]: ").strip()
    serial_port = port_input if port_input else SERIAL_PORT

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
    key_bytes_results = []
    collected_distances = []

    ser = None

    try:
        ser = serial.Serial(
            port=serial_port,
            baudrate=BAUD_RATE,
            timeout=SERIAL_TIMEOUT,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

        print(f"\n[*] Kết nối {serial_port} @ {BAUD_RATE} bps thành công.")
        print("[*] Hãy bấm RESET trên DE2-115 để FPGA chạy lại từ 1.0m.")
        input("[*] Sau khi bấm RESET, nhấn Enter để bắt đầu chờ dữ liệu...")

        pending_frame = wait_for_sweep_start(ser)

        current_sw = -1

        sum_qber = 0.0
        sum_skr = 0.0
        sum_sifted = 0.0
        sum_error = 0.0
        sum_key_bytes = 0.0

        valid_samples = 0
        is_first_packet = True

        while True:
            if pending_frame is not None:
                res = pending_frame
                pending_frame = None
            else:
                res = read_one_frame(ser)

            if res is None:
                continue

            final_skr, qber_idx, n_sifted, n_error, sw_state, key_byte_count = res

            if sw_state >= NUM_SWEEP_POINTS:
                print(f"[!] Bỏ qua frame lỗi: sw_state={sw_state}")
                continue

            # ----------------------------------------------------
            # FPGA switched to new distance
            # ----------------------------------------------------
            if sw_state != current_sw:
                save_current_point(
                    env_name=env_name,
                    current_sw=current_sw,
                    valid_samples=valid_samples,
                    sum_qber=sum_qber,
                    sum_skr=sum_skr,
                    sum_sifted=sum_sifted,
                    sum_error=sum_error,
                    sum_key_bytes=sum_key_bytes,
                    qber_results=qber_results,
                    skr_results=skr_results,
                    sifted_results=sifted_results,
                    error_results=error_results,
                    key_bytes_results=key_bytes_results,
                    collected_distances=collected_distances,
                )

                current_sw = sw_state

                sum_qber = 0.0
                sum_skr = 0.0
                sum_sifted = 0.0
                sum_error = 0.0
                sum_key_bytes = 0.0

                valid_samples = 0
                is_first_packet = True

                print(f"\n🔄 Đang thu thập dữ liệu tại: {SCENARIO_MAP[current_sw]}")

            # ----------------------------------------------------
            # Skip first frame after distance switch
            # ----------------------------------------------------
            if SKIP_FIRST_PACKET_AFTER_SWITCH and is_first_packet:
                is_first_packet = False
                print("   [~] Bỏ qua frame đầu của mốc này để tránh dữ liệu chuyển trạng thái.")
                continue

            is_first_packet = False

            # ----------------------------------------------------
            # Accumulate valid frame
            # ----------------------------------------------------
            qber_pc_val = (n_error / n_sifted) if n_sifted > 0 else 0.0
            qber_pc_pct = qber_pc_val * 100.0
            qber_fpga_pct = (qber_idx / 1024.0) * 100.0

            sum_qber += qber_pc_val
            sum_skr += final_skr
            sum_sifted += n_sifted
            sum_error += n_error
            sum_key_bytes += key_byte_count

            valid_samples += 1

            status = get_status(final_skr, n_sifted, n_error)

            print(
                f"   => Mẫu {valid_samples}/{SAMPLES_PER_DISTANCE}: "
                f"SIFTED={n_sifted:<10d} | "
                f"ERROR={n_error:<8d} | "
                f"QBER_FPGA={qber_fpga_pct:>6.2f}% | "
                f"QBER_PC={qber_pc_pct:>6.2f}% | "
                f"SKR={final_skr:<10d} | "
                f"KEY_BYTES={key_byte_count:<4d} | "
                f"STATUS={status}"
            )

            # ----------------------------------------------------
            # Stop condition: 7.0m and enough samples
            # ----------------------------------------------------
            if current_sw == 60 and valid_samples >= SAMPLES_PER_DISTANCE:
                save_current_point(
                    env_name=env_name,
                    current_sw=current_sw,
                    valid_samples=valid_samples,
                    sum_qber=sum_qber,
                    sum_skr=sum_skr,
                    sum_sifted=sum_sifted,
                    sum_error=sum_error,
                    sum_key_bytes=sum_key_bytes,
                    qber_results=qber_results,
                    skr_results=skr_results,
                    sifted_results=sifted_results,
                    error_results=error_results,
                    key_bytes_results=key_bytes_results,
                    collected_distances=collected_distances,
                )

                print("\n✅ FPGA đã quét xong 61 mốc từ 1.0m đến 7.0m.")
                break

        # --------------------------------------------------------
        # Save CSV
        # --------------------------------------------------------
        df = pd.DataFrame(
            {
                "Environment": [env_name] * len(collected_distances),
                "Distance(m)": collected_distances,
                "QBER(%)": qber_results,
                "SKR(bps)": skr_results,
                "Avg_Sifted": sifted_results,
                "Avg_Error": error_results,
                "Avg_Key_Payload_Bytes": key_bytes_results,
            }
        )

        csv_filename = f"{env_name}_qkd_data.csv"
        df.to_csv(csv_filename, index=False)

        print(f"\n[*] Đã lưu toàn bộ dữ liệu vào file: {csv_filename}")
        print(f"[*] Số mốc đã lưu: {len(collected_distances)}/61")

        draw_single_environment_plot(csv_filename)
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
                    "Avg_Key_Payload_Bytes": key_bytes_results,
                }
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"{env_name}_partial_qkd_data_{timestamp}.csv"
            df.to_csv(csv_filename, index=False)

            print(f"[*] Đã lưu dữ liệu đo dở vào file: {csv_filename}")

    except Exception as e:
        print(f"\n[!] Lỗi: {e}")

    finally:
        if ser is not None and ser.is_open:
            ser.close()
            print("[*] Đã đóng cổng UART.")


if __name__ == "__main__":
    main()