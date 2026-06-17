import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# BITSTREAM SIMULATOR - Sinh chuỗi bit từ metrics QBER
# ============================================================

def generate_bitstream_from_qber(qber_percent, n_sifted, seed=None):
    """
    Sinh chuỗi bit dựa trên QBER thực tế
    
    Args:
        qber_percent: Tỉ lệ lỗi (%)
        n_sifted: Số bits được sift
        seed: Random seed
    
    Returns:
        Tuple: (sifted_bits, error_positions, bitstream_str)
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Sinh chuỗi bit ngẫu nhiên
    sifted_bits = np.random.randint(0, 2, n_sifted)
    
    # Tính số lỗi dựa trên QBER
    n_errors = int(n_sifted * qber_percent / 100)
    
    # Ngẫu nhiên chọn vị trí lỗi
    error_positions = np.random.choice(n_sifted, n_errors, replace=False)
    
    # Flip bits tại vị trí lỗi
    error_bits = sifted_bits.copy()
    error_bits[error_positions] = 1 - error_bits[error_positions]
    
    # Convert thành string
    bitstream_str = ''.join(str(bit) for bit in error_bits)
    
    return sifted_bits, error_positions, bitstream_str


def print_bitstream_detailed(bitstream_str, n_display=256, grouping=8):
    """
    In chuỗi bit với format dễ đọc
    
    Args:
        bitstream_str: Chuỗi bit
        n_display: Số bits hiển thị
        grouping: Số bits trong 1 nhóm
    """
    n_display = min(n_display, len(bitstream_str))
    
    print("\n" + "="*70)
    print(f"BIT STREAM (showing first {n_display}/{len(bitstream_str)} bits)")
    print("="*70)
    
    for i in range(0, n_display, grouping * 8):
        line_bits = bitstream_str[i:i + grouping * 8]
        
        # Tách thành 8-bit groups
        groups = [line_bits[j:j+grouping] for j in range(0, len(line_bits), grouping)]
        groups_str = " ".join(groups)
        
        print(f"[{i:06d}] {groups_str}")
    
    if len(bitstream_str) > n_display:
        print(f"... ({len(bitstream_str) - n_display} more bits)")
    print("="*70 + "\n")


def analyze_bitstream(bitstream_str):
    """
    Phân tích thống kê chuỗi bit
    """
    bits_array = np.array([int(b) for b in bitstream_str])
    
    ones = np.sum(bits_array)
    zeros = len(bits_array) - ones
    
    one_ratio = ones / len(bits_array) * 100
    zero_ratio = zeros / len(bits_array) * 100
    
    print("\n" + "="*70)
    print("BITSTREAM ANALYSIS")
    print("="*70)
    print(f"Total bits:      {len(bitstream_str):,}")
    print(f"Ones (1):        {ones:,} ({one_ratio:.2f}%)")
    print(f"Zeros (0):       {zeros:,} ({zero_ratio:.2f}%)")
    
    # Tính run lengths (đoạn liên tiếp của cùng giá trị)
    runs = []
    current_bit = bits_array[0]
    current_run = 1
    
    for bit in bits_array[1:]:
        if bit == current_bit:
            current_run += 1
        else:
            runs.append((current_bit, current_run))
            current_bit = bit
            current_run = 1
    runs.append((current_bit, current_run))
    
    one_runs = [r for b, r in runs if b == 1]
    zero_runs = [r for b, r in runs if b == 0]
    
    print(f"\nRun statistics:")
    print(f"  One runs:      {len(one_runs)}, avg length: {np.mean(one_runs):.2f}")
    print(f"  Zero runs:     {len(zero_runs)}, avg length: {np.mean(zero_runs):.2f}")
    print("="*70 + "\n")


def bitstream_to_hex(bitstream_str):
    """
    Convert bit string thành hex string
    """
    # Pad để chia hết cho 4
    padding = (4 - len(bitstream_str) % 4) % 4
    padded = bitstream_str + '0' * padding
    
    hex_str = hex(int(padded, 2))[2:].upper()
    
    print(f"\nHexadecimal representation (first 256 bits):")
    print("="*70)
    hex_display = bitstream_str[:256]
    padding2 = (4 - len(hex_display) % 4) % 4
    padded2 = hex_display + '0' * padding2
    hex_display_str = hex(int(padded2, 2))[2:].upper().zfill(64)
    
    for i in range(0, len(hex_display_str), 16):
        print(f"  {hex_display_str[i:i+16]}")
    print("="*70)


def main():
    """
    Demo: Sinh và hiển thị bitstream
    """
    # ============================================================
    # Example 1: Từ CSV data
    # ============================================================
    print("\n" + "🔐 "*35)
    print("QKD BIT STREAM SIMULATION & VISUALIZATION")
    print("🔐 "*35)
    
    # Đọc dữ liệu từ CSV
    try:
        df = pd.read_csv("../data/Turbid_Harbor_qkd_data.csv")
        
        # Chọn 1 dòng (ví dụ distance 3.0m)
        row = df[df["Distance(m)"] == 3.0].iloc[0]
        
        qber = row["QBER(%)"]
        n_sifted = int(row["Sifted_bits"]) if "Sifted_bits" in df.columns else 10000
        
        print(f"\n📊 DATA FROM: {row['Environment']}")
        print(f"   Distance: {row['Distance(m)']} m")
        print(f"   QBER: {qber:.2f}%")
        print(f"   Sifted bits: {n_sifted:,}")
        
    except Exception as e:
        print(f"\n⚠️  CSV not found: {e}")
        print("Using default parameters...")
        qber = 3.5
        n_sifted = 10000
    
    # Sinh bitstream
    print("\n⏳ Generating bitstream...")
    sifted_bits, error_positions, bitstream = generate_bitstream_from_qber(
        qber, n_sifted, seed=42
    )
    print(f"✓ Generated {len(bitstream):,} bits")
    
    # Hiển thị chi tiết
    print_bitstream_detailed(bitstream, n_display=512, grouping=8)
    
    # Phân tích
    analyze_bitstream(bitstream)
    
    # Hex representation
    bitstream_to_hex(bitstream)
    
    # ============================================================
    # Visualization
    # ============================================================
    print("\n📈 Creating visualizations...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Bit pattern (first 1000 bits)
    ax = axes[0, 0]
    bits_to_plot = bitstream[:1000]
    bits_array = np.array([int(b) for b in bits_to_plot])
    ax.plot(bits_array, marker='', linewidth=0.5, alpha=0.7)
    ax.set_title(f"Bit Pattern (first 1000 bits)", fontweight='bold')
    ax.set_xlabel("Bit Index")
    ax.set_ylabel("Bit Value")
    ax.set_ylim(-0.1, 1.1)
    ax.grid(alpha=0.3)
    
    # Plot 2: Bit distribution
    ax = axes[0, 1]
    bits_array = np.array([int(b) for b in bitstream])
    ones = np.sum(bits_array)
    zeros = len(bits_array) - ones
    ax.bar(['0 (Zero)', '1 (One)'], [zeros, ones], color=['lightblue', 'lightcoral'])
    ax.set_title(f"Bit Distribution\n(Total: {len(bitstream):,} bits)", fontweight='bold')
    ax.set_ylabel("Count")
    for i, v in enumerate([zeros, ones]):
        ax.text(i, v, f"{v:,}\n({v/len(bitstream)*100:.1f}%)", ha='center', va='bottom')
    
    # Plot 3: Running average of bits
    ax = axes[1, 0]
    window_size = 100
    running_avg = np.convolve(bits_array, np.ones(window_size)/window_size, mode='valid')
    ax.plot(running_avg, linewidth=1, label=f'Running avg (window={window_size})')
    ax.axhline(0.5, color='red', linestyle='--', label='Expected 0.5')
    ax.set_title("Running Average (should be ~0.5)", fontweight='bold')
    ax.set_xlabel("Position")
    ax.set_ylabel("Average Value")
    ax.legend()
    ax.grid(alpha=0.3)
    
    # Plot 4: Error positions (if any errors)
    ax = axes[1, 1]
    if len(error_positions) > 0:
        ax.scatter(error_positions[:min(1000, len(error_positions))], 
                  [1]*min(1000, len(error_positions)), 
                  alpha=0.5, s=10, color='red', label='Error positions')
        ax.set_title(f"Error Positions (QBER={qber:.2f}%)\n{len(error_positions)} errors in {len(bitstream):,} bits", 
                    fontweight='bold')
        ax.set_xlabel("Bit Index")
        ax.set_xlim(0, min(10000, len(bitstream)))
        ax.set_ylim(0.5, 1.5)
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No errors detected\n(QBER ≈ 0%)", 
               ha='center', va='center', fontsize=14, transform=ax.transAxes)
        ax.set_title("Error Positions")
    ax.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("bitstream_analysis.png", dpi=150, bbox_inches='tight')
    print("✓ Saved: bitstream_analysis.png")
    plt.show()
    
    # ============================================================
    # Export to file
    # ============================================================
    print("\n💾 Exporting bitstream to files...")
    
    # Export as binary file
    with open("bitstream.bin", "w") as f:
        f.write(bitstream)
    print(f"✓ Exported as binary: bitstream.bin ({len(bitstream)} bits)")
    
    # Export as hex file
    hex_str = hex(int(bitstream, 2))[2:]
    with open("bitstream.hex", "w") as f:
        f.write(hex_str)
    print(f"✓ Exported as hex: bitstream.hex")
    
    # Export as text with grouping
    with open("bitstream_formatted.txt", "w") as f:
        for i in range(0, len(bitstream), 64):
            group = bitstream[i:i+64]
            f.write(f"{i:08d}: {group}\n")
    print(f"✓ Exported formatted: bitstream_formatted.txt")


if __name__ == "__main__":
    main()
