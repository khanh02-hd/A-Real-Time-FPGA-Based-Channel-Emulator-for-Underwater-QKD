import serial
from datetime import datetime


# ============================================================
# USER CONFIG
# ============================================================

DEFAULT_PORT = "COM16"
BAUD_RATE = 115200
TIMEOUT = 2.0

# Must match MAX_BYTES in qkd_sifted_key_extractor.v
MAX_KEY_PAYLOAD_BYTES = 512


# ============================================================
# BASIC BYTE HELPERS
# ============================================================

def bytes_to_u32_be(b):
    """
    Convert 4 bytes big-endian to unsigned 32-bit integer.
    """
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def read_exact(ser, n):
    """
    Read exactly n bytes from serial.

    pyserial may return partial data, so this function keeps reading
    until enough bytes are received or timeout occurs.
    """
    data = bytearray()

    while len(data) < n:
        chunk = ser.read(n - len(data))

        if not chunk:
            raise TimeoutError(f"Timeout while reading {n} bytes")

        data.extend(chunk)

    return bytes(data)


# ============================================================
# METRIC PARSER
# ============================================================

def parse_metric_payload(payload):
    """
    Metric payload after 0xAA, exactly 14 bytes.

    Frame metric format:

        0xAA
        payload[0:4]    final_skr, big endian
        payload[4]      {sw_latched[5:0], qber_latched[9:8]}
        payload[5]      qber_latched[7:0]
        payload[6:10]   n_sifted, big endian
        payload[10:14]  n_error, big endian
        0xBB
        ...
    """
    if len(payload) != 14:
        raise ValueError("Metric payload must be exactly 14 bytes")

    final_skr = bytes_to_u32_be(payload[0:4])

    sw = (payload[4] >> 2) & 0x3F
    qber_index = ((payload[4] & 0x03) << 8) | payload[5]
    qber_percent = qber_index * 100.0 / 1024.0

    n_sifted = bytes_to_u32_be(payload[6:10])
    n_error = bytes_to_u32_be(payload[10:14])

    distance_m = 1.0 + 0.1 * sw

    return {
        "final_skr": final_skr,
        "sw": sw,
        "distance_m": distance_m,
        "qber_index": qber_index,
        "qber_percent": qber_percent,
        "n_sifted": n_sifted,
        "n_error": n_error,
    }


# ============================================================
# KEY PARSER
# ============================================================

def key_bytes_to_bit_string(key_bytes, bit_count):
    """
    Convert key payload bytes to bit string.

    Verilog stores bits LSB-first inside each byte:

        bit 0 -> byte[0]
        bit 1 -> byte[1]
        ...
        bit 7 -> byte[7]

    Therefore Python must also read LSB-first.
    """
    bit_count = min(bit_count, len(key_bytes) * 8)

    bits = []

    for i in range(bit_count):
        byte_index = i // 8
        bit_index = i % 8

        bit = (key_bytes[byte_index] >> bit_index) & 0x01
        bits.append("1" if bit else "0")

    return "".join(bits)


def format_bits(bit_string, bits_per_group=8, groups_per_line=8):
    """
    Format bit string for readable terminal display.
    """
    if not bit_string:
        return "(empty key)"

    lines = []
    bits_per_line = bits_per_group * groups_per_line

    for line_start in range(0, len(bit_string), bits_per_line):
        line = bit_string[line_start:line_start + bits_per_line]

        groups = [
            line[i:i + bits_per_group]
            for i in range(0, len(line), bits_per_group)
        ]

        lines.append(f"[{line_start:06d}] " + " ".join(groups))

    return "\n".join(lines)


# ============================================================
# FRAME READER
# ============================================================

def wait_for_frame_start(ser):
    """
    Wait until 0xAA is found.

    0xAA marks the beginning of one complete 1-second FPGA frame.
    """
    while True:
        b = ser.read(1)

        if not b:
            return False

        if b[0] == 0xAA:
            return True


def read_one_frame(ser):
    """
    Complete FPGA frame format:

        0xAA
        14 bytes metric payload
        0xBB
        2 bytes key payload length, little endian, in bytes
        key payload
        0x55

    Meaning:

        0xAA: metric header
        0xBB: key payload header
        0x55: frame footer
    """
    try:
        ok = wait_for_frame_start(ser)

        if not ok:
            return None

        # --------------------------------------------------------
        # 1. Read metric payload
        # --------------------------------------------------------
        metric_payload = read_exact(ser, 14)
        metric = parse_metric_payload(metric_payload)

        # --------------------------------------------------------
        # 2. Check key header
        # --------------------------------------------------------
        key_header = read_exact(ser, 1)[0]

        if key_header != 0xBB:
            print(
                f"[WARN] Expected key header 0xBB, "
                f"got 0x{key_header:02X}. Resyncing..."
            )
            return None

        # --------------------------------------------------------
        # 3. Read key payload length
        # --------------------------------------------------------
        length_bytes = read_exact(ser, 2)
        key_byte_count = length_bytes[0] | (length_bytes[1] << 8)

        # --------------------------------------------------------
        # 4. Sanity check against corrupted length bytes
        # --------------------------------------------------------
        if key_byte_count > MAX_KEY_PAYLOAD_BYTES:
            print(
                f"[WARN] Invalid key payload length: "
                f"{key_byte_count} bytes > {MAX_KEY_PAYLOAD_BYTES} bytes. "
                f"Resyncing..."
            )
            return None

        # Optional consistency check using n_sifted from metric.
        expected_bytes_from_metric = (metric["n_sifted"] + 7) // 8

        if expected_bytes_from_metric <= MAX_KEY_PAYLOAD_BYTES:
            if key_byte_count > expected_bytes_from_metric:
                print(
                    f"[WARN] Payload length {key_byte_count} bytes is larger "
                    f"than expected from n_sifted: "
                    f"{expected_bytes_from_metric} bytes."
                )

        # --------------------------------------------------------
        # 5. Read key payload
        # --------------------------------------------------------
        key_payload = read_exact(ser, key_byte_count)

        # --------------------------------------------------------
        # 6. Check footer
        # --------------------------------------------------------
        footer = read_exact(ser, 1)[0]

        if footer != 0x55:
            print(
                f"[WARN] Expected footer 0x55, "
                f"got 0x{footer:02X}. Frame skipped."
            )
            return None

        # --------------------------------------------------------
        # 7. Convert payload bytes to bit string
        # --------------------------------------------------------
        expected_key_bits = metric["n_sifted"]
        available_key_bits = key_byte_count * 8
        actual_key_bits = min(expected_key_bits, available_key_bits)

        bit_string = key_bytes_to_bit_string(
            key_bytes=key_payload,
            bit_count=actual_key_bits
        )

        key = {
            "key_byte_count": key_byte_count,
            "expected_key_bits_from_metric": expected_key_bits,
            "available_key_bits": available_key_bits,
            "actual_key_bits_used": actual_key_bits,
            "raw_bytes": key_payload,
            "bit_string": bit_string,
        }

        return metric, key

    except TimeoutError as e:
        print(f"[WARN] {e}. Resyncing...")
        return None

    except ValueError as e:
        print(f"[WARN] {e}. Resyncing...")
        return None


# ============================================================
# PRINT FUNCTIONS
# ============================================================

def print_metric(metric):
    print("\n" + "=" * 72)
    print("METRIC")
    print("=" * 72)
    print(f"Distance index : {metric['sw']}")
    print(f"Distance       : {metric['distance_m']:.1f} m")
    print(f"QBER index     : {metric['qber_index']}")
    print(f"QBER           : {metric['qber_percent']:.3f} %")
    print(f"n_sifted       : {metric['n_sifted']}")
    print(f"n_error        : {metric['n_error']}")
    print(f"final_skr      : {metric['final_skr']}")


def print_key(key, max_print_bits=512):
    bit_string = key["bit_string"]

    print("\n" + "=" * 72)
    print("RAW SIFTED KEY PAYLOAD")
    print("=" * 72)

    print(f"Payload bytes              : {key['key_byte_count']}")
    print(f"Expected bits from metric  : {key['expected_key_bits_from_metric']}")
    print(f"Available bits in payload  : {key['available_key_bits']}")
    print(f"Actual bits used           : {key['actual_key_bits_used']}")

    if key["expected_key_bits_from_metric"] > key["available_key_bits"]:
        print(
            "[WARN] n_sifted is larger than payload capacity. "
            "Key buffer may have overflowed."
        )

    show_bits = bit_string[:max_print_bits]

    print(f"\nShowing first {len(show_bits)} bits:")
    print(format_bits(show_bits))

    if len(bit_string) > max_print_bits:
        print(f"... truncated on screen, total = {len(bit_string)} bits")

    zeros = bit_string.count("0")
    ones = bit_string.count("1")
    total = len(bit_string)

    print("\nKey statistics:")
    print(f"Zeros      : {zeros}")
    print(f"Ones       : {ones}")

    if total > 0:
        print(f"Zero ratio : {zeros / total:.4f}")
        print(f"One ratio  : {ones / total:.4f}")


# ============================================================
# SAVE FUNCTIONS
# ============================================================

def save_key_files(bit_string, raw_bytes, prefix="fpga_sifted_key"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    txt_path = f"{prefix}.txt"
    hex_path = f"{prefix}.hex"
    bin_path = f"{prefix}.bin"
    meta_path = f"{prefix}_metadata.txt"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(format_bits(bit_string))
        f.write("\n")

    with open(hex_path, "w", encoding="utf-8") as f:
        f.write(raw_bytes.hex().upper())
        f.write("\n")

    with open(bin_path, "wb") as f:
        f.write(raw_bytes)

    zeros = bit_string.count("0")
    ones = bit_string.count("1")
    total = len(bit_string)

    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("FPGA QKD RAW SIFTED KEY METADATA\n")
        f.write("================================\n")
        f.write(f"Timestamp   : {timestamp}\n")
        f.write(f"Total bits  : {total}\n")
        f.write(f"Total bytes : {len(raw_bytes)}\n")
        f.write(f"Zeros       : {zeros}\n")
        f.write(f"Ones        : {ones}\n")

        if total > 0:
            f.write(f"Zero ratio  : {zeros / total:.6f}\n")
            f.write(f"One ratio   : {ones / total:.6f}\n")

        f.write("\nNOTE:\n")
        f.write("This is Bob-side raw sifted key, not final secret key.\n")
        f.write("Error correction and privacy amplification are still required.\n")

    print(f"[SAVE] {txt_path}")
    print(f"[SAVE] {hex_path}")
    print(f"[SAVE] {bin_path}")
    print(f"[SAVE] {meta_path}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 72)
    print("FPGA QKD METRIC + RAW SIFTED KEY FRAME READER")
    print("=" * 72)

    port = input(f"Enter COM port [{DEFAULT_PORT}]: ").strip()

    if not port:
        port = DEFAULT_PORT

    target_str = input("Number of frames to read [5]: ").strip()

    if not target_str:
        frame_target = 5
    else:
        frame_target = int(target_str)

    print(f"\nOpening serial port {port} @ {BAUD_RATE} bps...")

    try:
        ser = serial.Serial(
            port=port,
            baudrate=BAUD_RATE,
            timeout=TIMEOUT,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open serial port {port}: {e}")
        return

    frames_read = 0
    last_key = None

    try:
        while frames_read < frame_target:
            result = read_one_frame(ser)

            if result is None:
                print("[INFO] Waiting/resyncing...")
                continue

            metric, key = result

            frames_read += 1
            last_key = key

            print_metric(metric)
            print_key(key)

            print(f"\n[INFO] Frames received: {frames_read}/{frame_target}")

        if last_key is not None:
            save = input("\nSave last key payload to files? [y/N]: ").strip().lower()

            if save == "y":
                save_key_files(
                    bit_string=last_key["bit_string"],
                    raw_bytes=last_key["raw_bytes"],
                    prefix="fpga_sifted_key"
                )

    except KeyboardInterrupt:
        print("\nStopped by user.")

    finally:
        ser.close()
        print("Serial port closed.")


if __name__ == "__main__":
    main() 