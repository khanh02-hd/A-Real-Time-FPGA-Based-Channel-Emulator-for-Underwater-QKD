import serial
import struct
import time
import sys

# ============================================================
# FPGA KEY READER - Đọc actual sifted keys từ FPGA
# ============================================================

def read_fpga_keys(ser: serial.Serial, timeout=10.0):
    """
    Đọc packet chứa actual sifted keys từ FPGA
    
    Packet format:
    Byte 0    : 0xDD (start marker - key data)
    Byte 1    : key_bits_count[7:0]
    Byte 2    : key_bits_count[15:8]
    Byte 3... : key_buffer[] (actual sifted bits)
    Last byte : 0x55 (end marker)
    
    Returns:
        dict with:
        - 'keys': bit string (actual quantum keys)
        - 'key_count': number of sifted bits
        - 'bytes': raw key bytes
    """
    start_time = time.time()
    
    # Find start marker 0xDD (key data marker)
    while time.time() - start_time < timeout:
        b = ser.read(1)
        if len(b) == 0:
            time.sleep(0.01)
            continue
        if b[0] == 0xDD:
            break
    else:
        print(f"[!] Timeout waiting for key packet (0xDD)")
        return None
    
    # Read key count (2 bytes, little-endian)
    count_bytes = ser.read(2)
    if len(count_bytes) != 2:
        print(f"[!] Failed to read key count")
        return None
    
    key_bits_count = count_bytes[0] | (count_bytes[1] << 8)
    key_bytes_count = (key_bits_count + 7) // 8
    
    print(f"[*] Receiving {key_bits_count} key bits ({key_bytes_count} bytes)...", end='', flush=True)
    
    # Read key bytes
    key_bytes = ser.read(key_bytes_count)
    if len(key_bytes) != key_bytes_count:
        print(f"\n[!] Failed to read key bytes: got {len(key_bytes)}, expected {key_bytes_count}")
        return None
    
    # Read end marker
    end_marker = ser.read(1)
    if len(end_marker) != 1 or end_marker[0] != 0x55:
        print(f"\n[!] Invalid end marker: 0x{end_marker[0]:02x}")
        return None
    
    print(f" ✓ Done!")
    
    # Convert bytes to bit string
    bit_string = ''.join(format(byte, '08b') for byte in key_bytes)
    # Trim to exact bit count (last byte might have padding)
    bit_string = bit_string[:key_bits_count]
    
    return {
        'keys': bit_string,
        'key_count': key_bits_count,
        'bytes': key_bytes,
        'timestamp': time.time()
    }


def read_multiple_keys(ser: serial.Serial, num_packets=5, timeout=60.0):
    """
    Đọc multiple key packets từ FPGA
    """
    packets = []
    start_time = time.time()
    
    print(f"\n" + "="*80)
    print(f"READING ACTUAL QUANTUM KEYS FROM FPGA")
    print(f"="*80)
    print(f"[*] Reading {num_packets} key packets...")
    print(f"[*] Timeout: {timeout} seconds\n")
    
    for i in range(num_packets):
        if time.time() - start_time > timeout:
            print(f"\n[!] Timeout after {i} packets")
            break
        
        print(f"[{i+1}/{num_packets}] ", end='', flush=True)
        
        packet = read_fpga_keys(ser, timeout=timeout-10)
        if packet is None:
            print("FAILED")
            continue
        
        print(f"  → {packet['key_count']} bits")
        packets.append(packet)
    
    return packets


def print_keys(bit_string, max_display=512):
    """
    In quantum keys dưới dạng readable format
    """
    display_len = min(max_display, len(bit_string))
    
    print("\n" + "="*80)
    print(f"QUANTUM KEYS FROM FPGA (showing {display_len}/{len(bit_string)} bits)")
    print("="*80)
    
    # In từng byte
    for offset in range(0, display_len, 64):
        end = min(offset + 64, display_len)
        line = bit_string[offset:end]
        
        # Format: groups of 8 bits
        groups = [line[i:i+8] for i in range(0, len(line), 8)]
        groups_str = " ".join(groups)
        
        print(f"[{offset:06d}] {groups_str}")
    
    if len(bit_string) > display_len:
        print(f"[...] ({len(bit_string) - display_len} more bits)")
    
    print("="*80 + "\n")


def print_keys_hex(bit_string, max_display=256):
    """
    In keys dưới dạng hex
    """
    display_len = min(max_display, len(bit_string))
    display_bits = bit_string[:display_len]
    
    # Pad to byte boundary
    padding = (8 - len(display_bits) % 8) % 8
    padded = display_bits + '0' * padding
    
    print("\n" + "="*80)
    print(f"KEYS IN HEXADECIMAL (first {display_len} bits)")
    print("="*80)
    
    hex_str = hex(int(padded, 2))[2:].upper().zfill(display_len // 4)
    
    # Print in rows of 16 chars (64 bits)
    for i in range(0, len(hex_str), 16):
        print(f"  {hex_str[i:i+16]}")
    
    print("="*80 + "\n")


def print_keys_visual(bit_string, rows=20):
    """
    In keys dưới dạng hình ảnh (█/░)
    """
    print("\n" + "="*80)
    print(f"KEYS VISUAL REPRESENTATION")
    print("="*80)
    
    cols = 64
    for row in range(min(rows, (len(bit_string) + cols - 1) // cols)):
        start = row * cols
        end = min(start + cols, len(bit_string))
        line = bit_string[start:end]
        
        visual = line.replace('0', '░').replace('1', '█')
        print(f"[{start:06d}] {visual}")
    
    if len(bit_string) > rows * cols:
        remaining = len(bit_string) - rows * cols
        print(f"[...] {remaining} more bits")
    
    print("="*80 + "\n")


def print_key_statistics(bit_string):
    """
    Thống kê keys
    """
    import numpy as np
    
    bits = np.array([int(b) for b in bit_string])
    ones = np.sum(bits)
    zeros = len(bits) - ones
    
    print("\n" + "="*80)
    print(f"QUANTUM KEYS STATISTICS")
    print("="*80)
    print(f"Total sifted key bits: {len(bit_string):,}")
    print(f"\nBit Distribution:")
    print(f"  Ones  (1): {ones:,} ({ones/len(bit_string)*100:.2f}%)")
    print(f"  Zeros (0): {zeros:,} ({zeros/len(bit_string)*100:.2f}%)")
    print(f"  Ratio: {ones/zeros:.3f}")
    
    # Randomness
    if len(bits) > 1:
        diffs = np.abs(np.diff(bits))
        transitions = np.sum(diffs)
        transition_ratio = transitions / len(bits)
        
        print(f"\nRandomness Analysis:")
        print(f"  Bit transitions: {transitions:,} ({transition_ratio*100:.2f}%)")
        print(f"  Expected (perfect random): 50%")
        
        if abs(transition_ratio - 0.5) < 0.1:
            print(f"  ✓ EXCELLENT randomness!")
        elif abs(transition_ratio - 0.5) < 0.2:
            print(f"  ✓ Good randomness")
        else:
            print(f"  ⚠️  Poor randomness")
    
    print("="*80 + "\n")


def export_keys(bit_string, key_count, prefix="fpga_keys"):
    """
    Export keys to files
    """
    print(f"\n[*] Exporting keys to files...")
    
    # Binary format
    with open(f"{prefix}.bin", "w") as f:
        f.write(bit_string)
    print(f"  ✓ {prefix}.bin ({len(bit_string)} bits)")
    
    # Hex format
    padding = (4 - len(bit_string) % 4) % 4
    padded = bit_string + '0' * padding
    hex_str = hex(int(padded, 2))[2:].upper()
    with open(f"{prefix}.hex", "w") as f:
        f.write(hex_str)
    print(f"  ✓ {prefix}.hex")
    
    # Formatted text
    with open(f"{prefix}_formatted.txt", "w") as f:
        for i in range(0, len(bit_string), 64):
            f.write(f"{i:08d}: {bit_string[i:i+64]}\n")
    print(f"  ✓ {prefix}_formatted.txt")
    
    # Metadata
    with open(f"{prefix}_metadata.txt", "w") as f:
        f.write("ACTUAL QUANTUM KEYS FROM FPGA\n")
        f.write("="*50 + "\n")
        f.write(f"Total key bits: {key_count}\n")
        f.write(f"Total bytes: {(key_count + 7) // 8}\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Source: FPGA Quantum Receiver\n")
    print(f"  ✓ {prefix}_metadata.txt")


def main():
    """
    Main interactive mode
    """
    print("\n" + "🔐 "*40)
    print("FPGA QUANTUM KEY READER")
    print("🔐 "*40)
    
    # Connect to FPGA
    port = input("\nEnter COM port (default COM16): ").strip() or "COM16"
    
    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
        print(f"[✓] Connected to {port} @ 115200 bps")
    except Exception as e:
        print(f"[!] Failed to connect: {e}")
        return
    
    # Get number of keys
    try:
        num = int(input("Number of key packets to read (default 5): ").strip() or "5")
    except:
        num = 5
    
    # Read keys
    packets = read_multiple_keys(ser, num_packets=num)
    
    if not packets:
        print("\n[!] No keys received from FPGA")
        ser.close()
        return
    
    print(f"\n[✓] Successfully received {len(packets)} key packets!")
    
    # Process first packet
    packet = packets[0]
    keys = packet['keys']
    
    print_keys(keys, max_display=512)
    print_keys_hex(keys, max_display=512)
    print_keys_visual(keys, rows=16)
    print_key_statistics(keys)
    
    # Export
    export_keys(keys, packet['key_count'], prefix="fpga_quantum_keys")
    
    # Combine if multiple
    if len(packets) > 1:
        print(f"\n[*] Combining {len(packets)} key packets...")
        combined_keys = ''.join(p['keys'] for p in packets)
        total_key_count = sum(p['key_count'] for p in packets)
        export_keys(combined_keys, total_key_count, prefix="fpga_quantum_keys_combined")
        print(f"[✓] Combined total: {len(combined_keys):,} bits")
    
    ser.close()
    print("\n[✓] Done! Keys exported successfully.\n")


if __name__ == "__main__":
    main()
