import serial
import struct
import time

# ============================================================
# EXTENDED UART READER - Đọc bitstream từ FPGA (nếu RTL được modify)
# ============================================================

def read_bitstream_packet(ser: serial.Serial, timeout=2.0):
    """
    Đọc packet bitstream từ FPGA
    
    Format (nếu RTL được modify):
    Byte 0    : 0xBB (start marker)
    Byte 1-128: 1024 bits (128 bytes)
    Byte 129  : Checksum
    Byte 130  : 0x55 (end marker)
    
    Total: 131 bytes
    """
    start_time = time.time()
    
    # Tìm start marker 0xBB
    while time.time() - start_time < timeout:
        b = ser.read(1)
        if len(b) == 0:
            continue
        if b[0] == 0xBB:
            break
    else:
        return None
    
    # Đọc 128 bytes bitstream
    bitstream_bytes = ser.read(128)
    if len(bitstream_bytes) != 128:
        return None
    
    # Đọc checksum
    checksum = ser.read(1)
    if len(checksum) != 1:
        return None
    
    # Đọc end marker
    end_marker = ser.read(1)
    if len(end_marker) != 1 or end_marker[0] != 0x55:
        return None
    
    # Verify checksum (simple XOR)
    calc_checksum = 0
    for byte in bitstream_bytes:
        calc_checksum ^= byte
    
    if calc_checksum != checksum[0]:
        print(f"[!] Checksum mismatch: expected {calc_checksum:02x}, got {checksum[0]:02x}")
        return None
    
    # Convert bytes to bit string
    bit_string = ''.join(format(byte, '08b') for byte in bitstream_bytes)
    
    return bit_string


def read_mixed_packets(ser: serial.Serial, max_packets=10):
    """
    Đọc liên tục cả metrics packets và bitstream packets
    
    Metric packet: 0xAA ... 0x55 (16 bytes)
    Bitstream packet: 0xBB ... 0x55 (131 bytes)
    """
    packets = []
    
    for i in range(max_packets):
        # Peek byte đầu
        peek = ser.read(1)
        if len(peek) == 0:
            break
        
        if peek[0] == 0xAA:  # Metric packet
            print(f"[{i}] Metric packet detected")
            # Read remaining 15 bytes
            rest = ser.read(15)
            if len(rest) == 15 and rest[14] == 0x55:
                final_skr = struct.unpack(">I", rest[0:4])[0]
                qber_high = rest[4] & 0x03
                qber_low = rest[5]
                qber_idx = (qber_high << 8) | qber_low
                n_sifted = struct.unpack(">I", rest[6:10])[0]
                n_error = struct.unpack(">I", rest[10:14])[0]
                
                packets.append({
                    'type': 'metric',
                    'final_skr': final_skr,
                    'qber_idx': qber_idx,
                    'n_sifted': n_sifted,
                    'n_error': n_error
                })
        
        elif peek[0] == 0xBB:  # Bitstream packet
            print(f"[{i}] Bitstream packet detected")
            # Put back the peeked byte by seeking back
            # This is a limitation - we need to handle this differently
            # For now, let's read the full packet
            ser.read(1)  # consume the peeked byte
            bitstream_bytes = ser.read(128)
            checksum = ser.read(1)
            end_marker = ser.read(1)
            
            if (len(bitstream_bytes) == 128 and 
                len(checksum) == 1 and 
                len(end_marker) == 1 and 
                end_marker[0] == 0x55):
                
                bit_string = ''.join(format(byte, '08b') for byte in bitstream_bytes)
                packets.append({
                    'type': 'bitstream',
                    'bits': bit_string
                })
        else:
            print(f"[!] Unknown packet start: 0x{peek[0]:02x}")
    
    return packets


def print_bitstream_hex_dump(bit_string, bytes_per_line=16):
    """
    In bitstream dưới dạng hex dump (như hexdump -C)
    """
    bytes_array = bytearray()
    
    # Convert bit string to bytes
    for i in range(0, len(bit_string), 8):
        byte_str = bit_string[i:i+8]
        if len(byte_str) == 8:
            bytes_array.append(int(byte_str, 2))
        else:
            # Pad with zeros
            bytes_array.append(int(byte_str.ljust(8, '0'), 2))
    
    # Print like hexdump
    print("\n" + "="*80)
    print("HEX DUMP OF BITSTREAM")
    print("="*80)
    for offset in range(0, len(bytes_array), bytes_per_line):
        chunk = bytes_array[offset:offset+bytes_per_line]
        
        # Hex values
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        hex_str = f"{hex_str:<{bytes_per_line*3-1}}"
        
        # ASCII representation (if printable)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        
        print(f"0x{offset:08x}  {hex_str}  |{ascii_str}|")
    print("="*80 + "\n")


def print_bitstream_visual(bit_string, rows=16, cols=64):
    """
    In bitstream dưới dạng grid (trực quan)
    """
    print("\n" + "="*80)
    print("VISUAL BITSTREAM REPRESENTATION")
    print("="*80)
    
    for row in range(0, min(rows, (len(bit_string) + cols - 1) // cols)):
        start = row * cols
        end = min(start + cols, len(bit_string))
        line = bit_string[start:end]
        
        # Replace 0/1 với symbols
        visual = line.replace('0', '░').replace('1', '█')
        
        print(f"[{start:06d}] {visual} [{end-start:3d}]")
    
    if len(bit_string) > rows * cols:
        print(f"... ({len(bit_string) - rows * cols} more bits)")
    print("="*80 + "\n")


# Demo usage
if __name__ == "__main__":
    print("BITSTREAM READER FOR MODIFIED QKD FPGA\n")
    
    # Example: Simulate reading bitstream
    # In thực tế, bạn cần connect tới COM port thực
    
    print("To use with real FPGA:")
    print("1. Modify rtl/top_qkd_receiver.v to output bitstream")
    print("2. Connect FPGA UART to PC")
    print("3. Run this code:")
    print("""
    ser = serial.Serial('COM16', 115200, timeout=1)
    
    # Read one bitstream packet
    bitstream = read_bitstream_packet(ser)
    if bitstream:
        print(f"Received {len(bitstream)} bits")
        print_bitstream_hex_dump(bitstream)
        print_bitstream_visual(bitstream)
    """)
