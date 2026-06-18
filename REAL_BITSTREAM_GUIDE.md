# Real Quantum Bitstream Extraction Guide

## Overview

This guide explains how to extract **real quantum bit sequences** directly from the FPGA receiver instead of simulated ones.

## Architecture

The system captures actual sifted bits during each 1-second window and transmits them via extended UART protocol:

```
FPGA Receiver
    ↓
Photon Detection → Basis Matching → Bit Capture
    ↓
qkd_bitstream_buffer.v (NEW)
    ↓ (Every 1 second)
Extended UART Protocol
    ↓
Python Reader (real_bitstream_reader.py)
    ↓
Real Bitstream Files
```

## Implementation Steps

### Step 1: Add New RTL Module

The new module `qkd_bitstream_buffer.v` has been created with:
- **1024-bit capture buffer** (128 bytes)
- **Error tracking** during capture
- **UART packet generation** every window

Copy to FPGA project:
```bash
cp rtl/qkd_bitstream_buffer.v <your_quartus_project>/
```

### Step 2: Integrate into top_qkd_receiver.v

Add this to `top_qkd_receiver.v`:

#### 2.1: Instantiate the module

```verilog
// Add to top_qkd_receiver.v after metrics_counter instantiation

qkd_bitstream_buffer bitstream_buf (
    .clk            (clk_50mhz),
    .rst_n          (rst_n),
    
    // From channel emulator
    .pulse_valid    (pulse_valid),
    .photon_received(photon_received),
    .basis_match    (basis_match),
    .received_bit   (received_bit),
    .bit_error      (bit_error),
    
    // Control signals
    .clear_window   (clear_window),
    .trigger_transmit(trigger_1sec),
    
    // Status outputs
    .bit_count      (bitstream_bit_count),
    .error_count    (bitstream_error_count),
    
    // UART output
    .valid_out      (bitstream_valid),
    .data_out       (bitstream_data),
    .ready_out      (uart_tx_ready)  // From uart_tx module
);
```

#### 2.2: Multiplex UART outputs

Modify UART transmitter to handle both metric packets and bitstream packets:

```verilog
// Packet type selector
reg packet_type;  // 0 = metric, 1 = bitstream

// In UART output mux:
assign uart_tx_data = (packet_type == 1) ? bitstream_data : metric_data;
assign uart_tx_valid = (packet_type == 1) ? bitstream_valid : metric_valid;

// Switch between packet types after each complete transmission
always @(posedge clk) begin
    if (uart_tx_complete) begin
        // Alternate between metric and bitstream packets
        packet_type <= ~packet_type;
    end
end
```

### Step 3: Compile and Program FPGA

```bash
# In Quartus
1. Add qkd_bitstream_buffer.v to project
2. Modify top_qkd_receiver.v as above
3. Analysis & Synthesis
4. Place & Route
5. Generate .sof file
6. Program DE2-115 board
```

### Step 4: Run Python Reader

```bash
cd monitoring/
python real_bitstream_reader.py
```

Follow the interactive prompts:
- Enter COM port (default: COM16)
- Specify number of packets to read (default: 5)

## UART Protocol Details

### Metric Packet (Existing)
```
Byte 0    : 0xAA (start)
Byte 1-4  : final_skr (32-bit)
Byte 5-6  : QBER (10-bit)
Byte 7-10 : n_sifted (32-bit)
Byte 11-14: n_error (32-bit)
Byte 15   : 0x55 (end)
Total: 16 bytes
```

### Bitstream Packet (NEW)
```
Byte 0     : 0xCC (start marker)
Byte 1-128 : bit_buffer (128 bytes = 1024 bits)
Byte 129   : error_count[7:0]
Byte 130   : error_count[15:8]
Byte 131   : total_bits[7:0]
Byte 132   : total_bits[15:8]
Byte 133   : XOR checksum
Byte 134   : 0x55 (end marker)
Total: 135 bytes
```

### Checksum Calculation (XOR)

```
checksum = 0xCC ⊕ buffer[0] ⊕ buffer[1] ⊕ ... ⊕ buffer[127]
         ⊕ error_count_lo ⊕ error_count_hi
         ⊕ total_bits_lo ⊕ total_bits_hi
```

## Output Format

The real_bitstream_reader.py produces:

### Files Generated
- `real_qkd_bitstream.bin` - Raw binary (1s and 0s)
- `real_qkd_bitstream.hex` - Hexadecimal format
- `real_qkd_bitstream_formatted.txt` - Formatted for reading
- `real_qkd_metadata.txt` - Metadata (timestamp, QBER, etc)

### Statistics Provided
- Bit distribution (1s vs 0s percentage)
- Randomness metrics (transition ratio)
- Run-length statistics
- Detected error positions
- QBER percentage

### Example Output

```
═════════════════════════════════════════════════════════════════════════════════
REAL BITSTREAM FROM FPGA
═════════════════════════════════════════════════════════════════════════════════
0x0000: a5 3c 9f 2b 4e 7d f1 c3 8a 5b d2 9e 4f 6c 1b 7a
0x0010: 3e 9d 52 c4 8f 1a 6b 9c 2d 7e f3 5b 8c 4a 6f 1d
0x0020: 92 a7 3f 8e 5c 1b d4 6a f9 2e 7b 5d 8a 3f 4c 9e
...
═════════════════════════════════════════════════════════════════════════════════

═════════════════════════════════════════════════════════════════════════════════
VISUAL REPRESENTATION OF REAL BITSTREAM
═════════════════════════════════════════════════════════════════════════════════
[000000] █░█░██░░ ██░░░█░ █████░░█ ░░██░░██  (64)
[000064] █░░░███░ █░░██░░ ░░░░█░░░ ░█░░█░░░  (64)
...
═════════════════════════════════════════════════════════════════════════════════

═════════════════════════════════════════════════════════════════════════════════
REAL BITSTREAM STATISTICS
═════════════════════════════════════════════════════════════════════════════════
Total bits captured by FPGA: 12,847
Bits in transmitted packet:  1,024

Bit distribution:
  Ones  (1): 512 (50.0%)
  Zeros (0): 512 (50.0%)

Error information:
  Bit errors detected: 128
  QBER: 0.995%

Randomness metrics:
  Bit transitions: 520 (50.8%)
  Expected (random): ~50%
  ✓  Good randomness level
═════════════════════════════════════════════════════════════════════════════════
```

## Troubleshooting

### No packets received
1. Check FPGA is programmed with modified RTL
2. Verify COM port is correct
3. Check UART connection (TX/RX crossed correctly)
4. Monitor with: `python -m serial.tools.miniterm COM16 115200`

### Checksum errors
- Indicates UART transmission corruption
- Try: lower baud rate, shorter cable, add shielding
- Or: reduce packet size

### Low QBER
- This is actually good! Means fewer errors
- If QBER < 1%, channel is very clean
- Good for producing secure keys

### High error count vs total_bits mismatch
- Indicates counter overflow or timing issue
- Check: FPGA clock frequency is correct
- Verify: no resets during capture window

## Advanced Usage

### Multiple Distance Sweep

To capture bitstreams at different distances:

```bash
# Auto-sweep runs 61 distances (1.0m to 7.0m)
# Each distance: capture for 5 seconds
# Then: 1 bitstream packet per second

python real_bitstream_reader.py
# Enter: 305 packets (61 distances × 5 seconds)
# Wait: ~5-10 minutes for complete sweep
```

### Post-Processing

Combine multiple bitstream files:

```python
# Combine all real_qkd_bitstream.bin files
combined = ""
for i in range(num_packets):
    with open(f"real_qkd_bitstream_{i}.bin", "r") as f:
        combined += f.read()

# Save combined
with open("combined_bitstream.bin", "w") as f:
    f.write(combined)

print(f"Combined {len(combined):,} bits")
```

### Cryptographic Analysis

Test bitstream randomness:

```bash
# NIST Statistical Test Suite
cd monitoring/
python -c "
import subprocess
# Generate NIST format file
with open('real_qkd_bitstream.bin', 'r') as f:
    bits = f.read()
# Run NIST tests
# ... 
"
```

## Performance Notes

- **Capture rate**: ~1000 bits/second (depends on photon count)
- **UART bandwidth**: 115200 bps → ~8.6 KB/sec → ~1024 bits/sec
- **Latency**: ~135 ms per packet (1024 bits + overhead)
- **Buffer efficiency**: Each packet = 1024 captured bits + metadata

## References

- FPGA RTL: `rtl/qkd_bitstream_buffer.v`
- Python reader: `monitoring/real_bitstream_reader.py`
- Main receiver: `rtl/top_qkd_receiver.v`
- Metrics counter: `rtl/qkd_metrics_counter.v`

---

**Note**: This implementation assumes standard FPGA environment (50 MHz clock, 115200 UART).
Adjust timing parameters if using different clock frequency.
 