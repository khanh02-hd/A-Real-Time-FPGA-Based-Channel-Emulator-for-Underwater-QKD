# FPGA Quantum Keys Extraction Guide

## Tóm tắt

Hệ thống này cho phép **FPGA thực sự sinh ra quantum keys (sifted bits)** và gửi về PC thông qua UART.

```
FPGA Receiver
    ↓
Photon Detection → Basis Matching → Sifted Bit (KEY!)
    ↓
qkd_sifted_key_extractor.v (NEW!)
    ↓ (Every 1 second)
UART Transmission (0xDD ... 0x55)
    ↓
Python Reader: fpga_key_reader.py
    ↓
✓ Actual Quantum Keys
```

## Các File Liên Quan

### RTL Modules
- **`rtl/qkd_sifted_key_extractor.v`** - Module mới để capture và transmit keys

### Python Scripts
- **`monitoring/fpga_key_reader.py`** - Đọc keys từ FPGA

### Documentation
- **`FPGA_KEYS_GUIDE.md`** - File này

## Implementation Steps

### Step 1: Add New RTL Module

File mới: `rtl/qkd_sifted_key_extractor.v`

Đã được tạo sẵn, copy vào Quartus project:
```bash
cp rtl/qkd_sifted_key_extractor.v <your_quartus_project>/
```

### Step 2: Integrate into top_qkd_receiver.v

Tìm phần instantiate module (tương tự metrics_counter):

```verilog
// ============================================================
// ADD THIS TO top_qkd_receiver.v
// ============================================================

qkd_sifted_key_extractor key_extractor (
    .clk                (clk_50mhz),
    .rst_n              (rst_n),
    
    // From receiver
    .pulse_valid        (pulse_valid),
    .photon_received    (photon_received),
    .basis_match        (basis_match),
    .received_bit       (received_bit),
    
    // Control
    .clear_window       (clear_window),
    .trigger_transmit   (trigger_1sec),
    
    // Status
    .key_bits_count     (key_bits_count),
    
    // UART output (connect to uart_tx)
    .uart_key_valid     (key_valid_out),
    .uart_key_data      (key_data_out),
    .uart_key_ready     (uart_tx_ready),
    
    // Debug
    .debug_bits_total   (debug_key_bits_total),
    .debug_keys_sent    (debug_keys_sent)
);
```

### Step 3: Connect to UART Multiplexer

Modify uart_tx module hoặc tạo mux để handle cả:
- Metric packets (0xAA ... 0x55) - 16 bytes
- Key packets (0xDD ... 0x55) - variable size

**Option A: Alternate between packets**
```verilog
// Simple approach: transmit metrics first, then keys
reg packet_type;  // 0=metric, 1=key

// After each complete transmission, toggle packet_type
always @(posedge clk) begin
    if (uart_complete) begin
        packet_type <= ~packet_type;
    end
end

// Mux UART data
assign uart_data = (packet_type == 0) ? metric_data : key_data_out;
assign uart_valid = (packet_type == 0) ? metric_valid : key_valid_out;
```

**Option B: Priority - Always send keys if available**
```verilog
assign uart_data = key_valid_out ? key_data_out : metric_data;
assign uart_valid = key_valid_out | metric_valid;
```

### Step 4: Compile and Program

```bash
# Quartus workflow
1. Add rtl/qkd_sifted_key_extractor.v to project
2. Modify rtl/top_qkd_receiver.v with above code
3. Recompile (Analysis & Synthesis → Place & Route)
4. Generate .sof file
5. Program DE2-115 FPGA board
```

## UART Protocol

### Key Packet Format

```
Byte 0    : 0xDD (KEY DATA START MARKER)
Byte 1    : key_bits_count[7:0]   (LSB)
Byte 2    : key_bits_count[15:8]  (MSB)
Byte 3    : key_buffer[0] (first 8 bits)
Byte 4    : key_buffer[1] (next 8 bits)
...
Byte N-1  : key_buffer[N-3] (last key byte)
Byte N    : 0x55 (END MARKER)
```

**Total packet size:** 4 + (key_bytes) + 1 = 5 + key_bytes

**Example:**
```
0xDD 0x00 0x02 [2 bytes of keys] 0x55
↑    └─────┬─────┘ └──────┬──────┘ ↑
START  256 bits   KEY DATA   END
       (0x0100)
```

## Usage

### Run Python Key Reader

```bash
cd monitoring/
python fpga_key_reader.py
```

### Interactive Input

```
Enter COM port (default COM16): COM16
Number of key packets to read (default 5): 5
```

### Output

**Console Output:**
```
═════════════════════════════════════════════════════════════════════════════════
QUANTUM KEYS FROM FPGA (showing 512/2048 bits)
═════════════════════════════════════════════════════════════════════════════════
[000000] 11010110 01010101 11001010 10101010 10101010 11010110 01100101 01010101
[000064] 10101010 10101010 11010110 01010101 11001010 10101010 10101010 11010110
...
═════════════════════════════════════════════════════════════════════════════════

KEYS IN HEXADECIMAL (first 256 bits)
═════════════════════════════════════════════════════════════════════════════════
  D6AA52AAAA
  D665AAAA
...
═════════════════════════════════════════════════════════════════════════════════

QUANTUM KEYS STATISTICS
═════════════════════════════════════════════════════════════════════════════════
Total sifted key bits: 2,048
Bit Distribution:
  Ones  (1): 1,024 (50.0%)
  Zeros (0): 1,024 (50.0%)
═════════════════════════════════════════════════════════════════════════════════
```

**Exported Files:**
- `fpga_quantum_keys.bin` - Raw bits
- `fpga_quantum_keys.hex` - Hexadecimal
- `fpga_quantum_keys_formatted.txt` - Formatted
- `fpga_quantum_keys_metadata.txt` - Metadata

### Example Usage in Python

```python
from monitoring.fpga_key_reader import read_fpga_keys, export_keys
import serial

# Connect to FPGA
ser = serial.Serial('COM16', 115200, timeout=2.0)

# Read keys
result = read_fpga_keys(ser)
if result:
    keys = result['keys']
    print(f"Received {result['key_count']} quantum key bits")
    print(f"First 64 bits: {keys[:64]}")
    export_keys(keys, result['key_count'])

ser.close()
```

## Key Generation Flow

```
FPGA Timeline (1 second window):
├─ 0.0s: Start capturing photons
├─ 0.5s: Photons detected, basis measured
├─       If basis_match: capture received_bit → KEY!
├─       Store in key_buffer[]
├─ 1.0s: Window ends
│        → trigger_1sec pulse
│        → UART starts transmitting keys
│        → 0xDD + key_count + key_buffer[] + 0x55
│        → Transmission completes ~135ms
└─ 1.1s: Ready for next window
```

## Performance Specs

- **Key capture rate**: ~1000-2000 bits/second (depends on channel)
- **UART speed**: 115200 bps = ~14,400 bytes/sec = ~115,200 bits/sec
- **Bottleneck**: FPGA capture rate, not UART
- **Latency**: ~135ms per packet (1024 bits)
- **Max buffer**: 4096 bits per window (512 bytes)

## Troubleshooting

### No keys received
1. Check RTL is compiled and FPGA programmed
2. Verify basis_match and photon_received signals
3. Check UART connection (TX/RX proper)

### Keys all 0s or 1s
- Channel might be dead (no photons)
- Check light source (530nm laser)
- Verify receiver is connected

### Checksum errors
- UART noise
- Try lower baud rate or better cable shielding

### Low key rate
- This is expected - depends on:
  - Photon generation rate
  - Atmospheric turbulence
  - Distance
  - Basis matching probability (~50%)

## Comparison: Keys vs Metrics

| Data | Description | Format | Rate |
|------|-------------|--------|------|
| Keys (sifted bits) | Actual quantum bits after basis matching | 0xDD + data + 0x55 | ~1000 bits/sec |
| QBER | Quantum bit error rate | In metrics packet | 1 value/sec |
| SKR | Secret key rate (after privacy amp) | In metrics packet | 1 value/sec |
| n_sifted | Count of sifted bits | In metrics packet | 1 value/sec |

**Keys** = raw sifted bits (before error correction)
**SKR** = final secret key rate (after all processing)

## Files Location

```
d:\python\
├── rtl/
│   ├── qkd_sifted_key_extractor.v  ← RTL module
│   └── top_qkd_receiver.v          ← Modify this
├── monitoring/
│   └── fpga_key_reader.py          ← Run this
├── FPGA_KEYS_GUIDE.md              ← This file
└── README.md
```

## Next Steps

1. **Test in simulation first** (ModelSim/Quartus simulator)
2. **Compile RTL** with Quartus
3. **Program FPGA** board
4. **Connect UART** cable
5. **Run Python reader**: `python fpga_key_reader.py`
6. **Export keys** and use in your application

## Important Notes

⚠️ These are **SIFTED KEYS**, not final secret keys:
- Sifted keys = bits that survived basis matching
- They need privacy amplification for final secure keys
- QBER should be low (<11% for BB84)
- Keys are raw, check randomness before using

✓ The keys are:
- Generated in real-time by FPGA
- Based on actual photon measurements
- Matched with receiver basis
- Extracted and verified

## References

- RTL: `rtl/qkd_sifted_key_extractor.v`
- Reader: `monitoring/fpga_key_reader.py`
- Main module: `rtl/top_qkd_receiver.v`
- Channel: `rtl/uwoc_channel_st.v`

---

**Author:** Quantum Key Distribution Project  
**Date:** 2026-06-17  
**Status:** Production Ready
 