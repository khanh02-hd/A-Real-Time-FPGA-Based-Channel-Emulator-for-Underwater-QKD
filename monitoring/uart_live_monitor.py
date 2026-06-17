import serial
import struct
import time

# ============================================================
# 1. CẤU HÌNH UART & KỊCH BẢN ĐO (AUTO-SWEEP 61 MỐC)
# ============================================================
SERIAL_PORT = "COM16"       # Cổng COM của DE2-115
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0

# Sinh tự động dictionary map từ 0 đến 60 tương ứng 1.0m đến 7.0m
SCENARIO_MAP = {i: f"{1.0 + i * 0.1:.1f}m" for i in range(61)}

MIN_SIFTED_SAFE = 1000
QBER_LIMIT = 0.11

# ============================================================
# 2. ĐỌC UART 16 BYTE TỪ FPGA
# ============================================================
def read_one_packet(ser: serial.Serial):
    b = ser.read(1)
    if len(b) != 1 or b[0] != 0xAA:
        return None

    rest = ser.read(15)
    if len(rest) != 15 or rest[14] != 0x55:
        return None

    final_skr = struct.unpack(">I", rest[0:4])[0]

    # Lấy 6 bit cao cho SW (mask 0x3F)
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
        return "🚨 OUTAGE"
    elif final_skr == 0 or qber_pc >= QBER_LIMIT:
        return "🚨 ALERT"
    else:
        return "✅ SAFE"

# ============================================================
# 3. MAIN MONITOR
# ============================================================
def main():
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            timeout=SERIAL_TIMEOUT,
        )

        print(f"[*] Đã kết nối thành công tới {SERIAL_PORT} @ {BAUD_RATE} bps.")
        print("[*] LIVE MONITOR HỆ THỐNG AUTO-SWEEP SẴN SÀNG.")
        print("[*] Khoảng cách tự động chạy từ 1.0m đến 7.0m (bước 0.1m).\n")

        header = (
            f"{'TIME':<10} | "
            f"{'PKT':<5} | "
            f"{'SCENARIO':<8} | "
            f"{'SIFTED':<10} | "
            f"{'ERROR':<8} | "
            f"{'QBER_FPGA':<10} | "
            f"{'QBER_PC':<9} | "
            f"{'SKR':<10} | "
            f"{'STATUS'}"
        )

        print("-" * 130)
        print(header)
        print("-" * 130)

        packet_count = 0
        last_sw_state = -1

        while True:
            result = read_one_packet(ser)
            if result is None:
                continue

            final_skr, qber_idx, n_sifted, n_error, sw_state = result
            packet_count += 1

            # Báo khi FPGA tự động nhảy sang mốc khoảng cách mới
            if sw_state != last_sw_state and last_sw_state != -1:
                print("\n" + "=" * 130)
                print(f"🔄 AUTO-SWEEP: FPGA tự động chuyển sang mốc {SCENARIO_MAP.get(sw_state, 'Unknown / Hoàn thành')}")
                print("=" * 130 + "\n")

            last_sw_state = sw_state

            # Tính QBER
            qber_fpga_pct = (qber_idx / 1024.0) * 100.0
            qber_pc_val = (n_error / n_sifted) if n_sifted > 0 else 0.0
            qber_pc_pct = qber_pc_val * 100.0

            status = get_status(final_skr, n_sifted, n_error)
            scenario_str = SCENARIO_MAP.get(sw_state, f"SW:{sw_state}")
            current_time = time.strftime("%H:%M:%S")

            print(
                f"[{current_time}] | "
                f"#{packet_count:<4d} | "
                f"{scenario_str:<8s} | "
                f"{n_sifted:<10d} | "
                f"{n_error:<8d} | "
                f"{qber_fpga_pct:>6.2f}%   | "
                f"{qber_pc_pct:>6.2f}%  | "
                f"{final_skr:<10d} | "
                f"{status}"
            )

    except serial.SerialException as e: print(f"\n[!] Lỗi cổng UART: {e}")
    except KeyboardInterrupt: print("\n[*] Đã dừng chương trình bằng Ctrl+C.")
    except Exception as e: print(f"\n[!] Lỗi không xác định: {e}")

if __name__ == "__main__":
    main()