import serial
import struct
import time
import numpy as np

# ============================================================
# REAL BITSTREAM READER FROM FPGA
# Đọc chuỗi bit thực tế được capture từ FPGA receiver
# ============================================================

def read_real_bitstream_packet(ser: serial.Serial, timeout=5.0):
    """
    Đọc packet containing actual sifted bits từ FPGA
    
    Packet format:
    Byte 0    : 0xCC (start marker)
    Byte 1-128: bit_buffer (128 bytes = 1024 bits)
    Byte 129  : error_count[7:0]
    Byte 130  : error_count[15:8]
    Byte 131  : total_bits[7:0]
    Byte 132  : total_bits[15:8]
    Byte 133  : XOR checksum
    Byte 134  : 0x55 (end marker)
    
    Total: 135 bytes
    
    Returns:
        dict with keys:
        - 'bitstream': bit string (0s and 1s)
        - 'bytes': raw bytes
        - 'error_count': number of bit errors
        - 'total_bits': total bits captured
        - 'qber': calculated QBER percentage
    """
    start_time = time.time()
    
    # Find start marker 0xCC
    while time.time() - start_time < timeout:
        b = ser.read(1)
        if len(b) == 0:
            continue
        if b[0] == 0xCC:
            break
    else:
        print(f"[!] Timeout waiting for bitstream packet")
        return None
    
    # Read 128 bytes of bitstream
    bitstream_bytes = ser.read(128)
    if len(bitstream_bytes) != 128:
        print(f"[!] Failed to read bitstream bytes: got {len(bitstream_bytes)}")
        return None
    
    # Read error count (2 bytes, little-endian)
    error_bytes = ser.read(2)
    if len(error_bytes) != 2:
        return None
    error_count = error_bytes[0] | (error_bytes[1] << 8)
    
    # Read total bits (2 bytes, little-endian)
    count_bytes = ser.read(2)
    if len(count_bytes) != 2:
        return None
    total_bits = count_bytes[0] | (count_bytes[1] << 8)
    
    # Read checksum
    checksum = ser.read(1)
    if len(checksum) != 1:
        return None
    
    # Read end marker
    end_marker = ser.read(1)
    if len(end_marker) != 1 or end_marker[0] != 0x55:
        print(f"[!] Invalid end marker: 0x{end_marker[0]:02x}")
        return None
    
    # Verify checksum
    calc_checksum = 0xCC  # Start with start marker
    for byte in bitstream_bytes:
        calc_checksum ^= byte
    calc_checksum ^= error_bytes[0]
    calc_checksum ^= error_bytes[1]
    calc_checksum ^= count_bytes[0]
    calc_checksum ^= count_bytes[1]
    
    if calc_checksum != checksum[0]:
        print(f"[!] Checksum mismatch: expected 0x{calc_checksum:02x}, got 0x{checksum[0]:02x}")
        return None
    
    # Convert bytes to bit string
    bit_string = ''.join(format(byte, '08b') for byte in bitstream_bytes)
    
    # Calculate QBER
    qber_percent = (error_count / total_bits * 100) if total_bits > 0 else 0.0
    
    return {
        'bitstream': bit_string,
        'bytes': bitstream_bytes,
        'error_count': error_count,
        'total_bits': total_bits,
        'qber': qber_percent,
        'timestamp': time.time()
    }


def read_multiple_bitstreams(ser: serial.Serial, num_packets=5, timeout=60.0):
    """
    Đọc nhiều packets bitstream liên tiếp
    """
    packets = []
    start_time = time.time()
    
    print(f"\n[*] Reading {num_packets} real bitstream packets from FPGA...")
    print(f"[*] Timeout: {timeout} seconds\n")
    
    for i in range(num_packets):
        if time.time() - start_time > timeout:
            print(f"[!] Timeout after {i} packets")
            break
        
        print(f"[{i+1}/{num_packets}] Waiting for bitstream packet... ", end='', flush=True)
        
        packet = read_real_bitstream_packet(ser)
        if packet is None:
            print("FAILED")
            continue
        
        print(f"OK ✓ (QBER={packet['qber']:.2f}%)")
        packets.append(packet)
    
    return packets


def print_bitstream_formatted(bitstream, bytes_per_line=16, grouping=8):
    """
    In bitstream dưới dạng readable format
    """
    print("\n" + "="*80)
    print("REAL BITSTREAM FROM FPGA")
    print("="*80)
    
    num_bytes = len(bitstream) // 8
    
    for offset in range(0, num_bytes, bytes_per_line):
        line = bitstream[offset*8:(offset+bytes_per_line)*8]
        
        # Convert to bytes
        byte_chars = []
        for i in range(0, len(line), 8):
            byte_str = line[i:i+8]
            if len(byte_str) == 8:
                byte_val = int(byte_str, 2)
                byte_chars.append(f"{byte_val:02x}")
        
        hex_str = " ".join(byte_chars)
        
        print(f"0x{offset*bytes_per_line:04x}: {hex_str}")
    
    print("="*80 + "\n")


def print_bitstream_visual(bitstream, cols=64, rows=16):
    """
    In bitstream dưới dạng hình ảnh (█/░)
    """
    print("\n" + "="*80)
    print("VISUAL REPRESENTATION OF REAL BITSTREAM")
    print("="*80)
    
    for row in range(min(rows, (len(bitstream) + cols - 1) // cols)):
        start = row * cols
        end = min(start + cols, len(bitstream))
        line = bitstream[start:end]
        
        visual = line.replace('0', '░').replace('1', '█')
        print(f"[{start:06d}] {visual} ({end-start:3d})")
    
    if len(bitstream) > rows * cols:
        remaining = len(bitstream) - rows * cols
        print(f"[...] {remaining} more bits")
    
    print("="*80 + "\n")


def print_bitstream_statistics(bitstream, error_count, total_bits_fpga):
    """
    Phân tích thống kê bitstream thực
    """
    bits = np.array([int(b) for b in bitstream])
    ones = np.sum(bits)
    zeros = len(bits) - ones
    
    print("\n" + "="*80)
    print("REAL BITSTREAM STATISTICS")
    print("="*80)
    print(f"Total bits captured by FPGA: {total_bits_fpga:,}")
    print(f"Bits in transmitted packet:  {len(bitstream):,}")
    print(f"\nBit distribution:")
    print(f"  Ones  (1): {ones:,} ({ones/len(bitstream)*100:.2f}%)")
    print(f"  Zeros (0): {zeros:,} ({zeros/len(bitstream)*100:.2f}%)")
    print(f"\nError information:")
    print(f"  Bit errors detected: {error_count:,}")
    print(f"  QBER: {error_count/total_bits_fpga*100:.3f}%")
    
    # Randomness analysis
    diffs = np.abs(np.diff(bits))
    transitions = np.sum(diffs)
    transition_ratio = transitions / len(bits)
    
    print(f"\nRandomness metrics:")
    print(f"  Bit transitions: {transitions:,} ({transition_ratio*100:.2f}%)")
    print(f"  Expected (random): ~50%")
    
    if transition_ratio < 0.3:
        print(f"  ⚠️  LOW randomness - possible correlation")
    elif transition_ratio > 0.7:
        print(f"  ⚠️  HIGH randomness - possible issues")
    else:
        print(f"  ✓  Good randomness level")
    
    # Run length statistics
    runs = []
    current_bit = bits[0]
    run_length = 1
    
    for bit in bits[1:]:
        if bit == current_bit:
            run_length += 1
        else:
            runs.append((current_bit, run_length))
            current_bit = bit
            run_length = 1
    runs.append((current_bit, run_length))
    
    one_runs = [r for b, r in runs if b == 1]
    zero_runs = [r for b, r in runs if b == 0]
    
    print(f"\nRun length statistics:")
    print(f"  One runs:  {len(one_runs):,}, avg length {np.mean(one_runs):.2f}")
    print(f"  Zero runs: {len(zero_runs):,}, avg length {np.mean(zero_runs):.2f}")
    
    print("="*80 + "\n")


def export_real_bitstream(bitstream, error_count, total_bits, prefix="real_qkd"):
    """
    Export real bitstream to files
    """
    import os
    
    print(f"\n[*] Exporting real bitstream data...")
    
    # Binary format
    with open(f"{prefix}_bitstream.bin", "w") as f:
        f.write(bitstream)
    print(f"✓ {prefix}_bitstream.bin")
    
    # Hex format
    hex_str = hex(int(bitstream, 2))[2:].upper()
    with open(f"{prefix}_bitstream.hex", "w") as f:
        f.write(hex_str)
    print(f"✓ {prefix}_bitstream.hex")
    
    # Formatted text
    with open(f"{prefix}_bitstream_formatted.txt", "w") as f:
        for i in range(0, len(bitstream), 64):
            f.write(f"{i:08d}: {bitstream[i:i+64]}\n")
    print(f"✓ {prefix}_bitstream_formatted.txt")
    
    # Metadata
    with open(f"{prefix}_metadata.txt", "w") as f:
        f.write(f"Real Bitstream Data\n")
        f.write(f"==================\n")
        f.write(f"Total bits: {total_bits}\n")
        f.write(f"Errors: {error_count}\n")
        f.write(f"QBER: {error_count/total_bits*100:.3f}%\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"✓ {prefix}_metadata.txt")


def main_interactive():
    """
    Interactive mode to read real bitstreams from FPGA
    """
    print("\n" + "🔐 "*35)
    print("REAL QUANTUM BITSTREAM READER - FPGA")
    print("🔐 "*35)
    
    # Get COM port
    port = input("\nEnter COM port (default COM16): ").strip() or "COM16"
    
    try:
        ser = serial.Serial(port, 115200, timeout=2.0)
        print(f"[✓] Connected to {port}")
    except Exception as e:
        print(f"[!] Failed to open {port}: {e}")
        return
    
    # Get number of packets
    try:
        num = int(input("Number of packets to read (default 5): ").strip() or "5")
    except:
        num = 5
    
    # Read packets
    packets = read_multiple_bitstreams(ser, num_packets=num)
    
    if not packets:
        print("[!] No packets received")
        ser.close()
        return
    
    print(f"\n[✓] Successfully read {len(packets)} bitstream packets")
    
    # Process first packet
    packet = packets[0]
    
    print_bitstream_formatted(packet['bitstream'])
    print_bitstream_visual(packet['bitstream'])
    print_bitstream_statistics(packet['bitstream'], packet['error_count'], packet['total_bits'])
    
    # Export
    export_real_bitstream(packet['bitstream'], packet['error_count'], packet['total_bits'])
    
    # Combine all packets
    if len(packets) > 1:
        print(f"\n[*] Combining {len(packets)} packets...")
        combined = ''.join(p['bitstream'] for p in packets)
        export_real_bitstream(combined, 
                            sum(p['error_count'] for p in packets),
                            sum(p['total_bits'] for p in packets),
                            prefix="real_qkd_combined")
        print(f"[✓] Combined bitstream: {len(combined):,} bits")
    
    ser.close()
    print("\n[*] Done!")


if __name__ == "__main__":
    main_interactive()
