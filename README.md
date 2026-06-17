# Underwater Quantum Key Distribution (QKD) Analysis

This project implements a comprehensive analysis framework for Quantum Key Distribution (QKD) systems in underwater environments. It provides tools for modeling quantum bit error rate (QBER) and secure key rate under different water conditions using lookup tables and real-time monitoring capabilities.

## Project Overview

The project evaluates QKD performance across three distinct underwater scenarios:
- **Clear Water**: Clear ocean environments with minimal scattering
- **Coastal Water**: Coastal regions with moderate turbidity and bubbles
- **Turbid Harbor**: Harbor water with high turbidity, bubbles, and strong scattering

## Project Structure

```
├── data/                      # Experimental and simulation data
│   ├── Clear_Water_qkd_data.csv
│   ├── Coastal_Water_qkd_data.csv
│   ├── Turbid_Harbor_qkd_data.csv
│   └── summary_Turbid_Harbor.txt
│
├── lut/                       # Lookup Tables (LUT) and related data
│   ├── lut_env1_clear_ocean.py       # Clear water environment model
│   ├── lut_env2_coastal.py           # Coastal water environment model
│   ├── lut_env3_harbor_bubbles.py    # Turbid harbor environment model
│   ├── lut_ho_bank_65536.mif         # Oceanic turbulence LUT
│   ├── lut_hs_bank_65536.mif         # Scattering/bubble fading LUT
│   └── lut_skr_penalty.mif           # Secret key rate penalty LUT
│
├── monitoring/                # Real-time UART data acquisition and visualization
│   ├── uart_daq_plotter.py          # UART DAQ with real-time plotting
│   └── uart_live_monitor.py         # Live monitoring interface
│
├── plots/                     # Plotting and analysis utilities
│   └── plot_loss.py                 # Loss analysis and visualization
│
├── rtl/                       # FPGA RTL (Verilog) and design files
│   ├── top_qkd_receiver.v           # Top-level receiver module
│   ├── uwoc_channel_st.v            # Underwater optical channel model
│   ├── uwoc_qkd_soc.v               # QKD System-on-Chip
│   ├── uart_tx.v                    # UART transmitter
│   ├── qkd_metrics_counter.v        # QKD performance counter
│   ├── skr_evaluator.v              # Secret key rate evaluator
│   ├── trng_qkd3_source.v           # TRNG source
│   ├── rom_ho.v, rom_hs.v           # ROM instances for lookup tables
│   ├── prng_lfsr_32bit.v            # PRNG/LFSR for key generation
│   ├── *.qpf, *.qsf                 # Quartus project files
│   ├── *.sdc                        # Timing constraints
│   ├── *.mif                        # Memory initialization files
│   └── tb_*.v                       # Testbenches
│
├── deprecated/                # Deprecated or development files (not tracked)
│   ├── realtime.py
│   └── ve.py
│
├── .gitignore
└── README.md
```

## Features

### Environment-Specific Models
- **Path Loss Modeling**: Beer-Lambert law + geometric loss
- **Atmospheric Turbulence**: Weibull oceanic turbulence models
- **Scattering Effects**: Gamma-distributed fading for bubbles and particles
- **Channel Characterization**: Auto-sweep over 61 distance points (1.0-7.0 m)

### Lookup Table System
- Pre-computed quantum channel characteristics
- Memory-efficient storage using `.mif` format
- Support for different FPGA implementations (DE2-115)

### Data Acquisition
- UART communication with quantum key distribution hardware
- Real-time data visualization and monitoring
- Configurable baud rate: 115200 bps
- Auto-sweep capability over multiple distance points

### FPGA RTL Design
- **HDL Implementation**: Verilog modules for QKD receiver and channel emulation
- **Key Modules**:
  - `top_qkd_receiver`: Main QKD receiver architecture
  - `uwoc_channel_st`: Underwater optical wireless channel simulator
  - `uwoc_qkd_soc`: Complete System-on-Chip with integrated components
  - `qkd_metrics_counter`: Real-time QBER and key rate calculation
  - `skr_evaluator`: Secret Key Rate computation engine
  - `trng_qkd3_source`: True Random Number Generator
  - `uart_tx`: Serial communication interface
- **Lookup Table ROM**: Pre-loaded channel characteristic tables
- **Testbenches**: Complete simulation testbenches for validation
- **Design Tools**: Altera Quartus II project files for DE2-115 FPGA

## Hardware Requirements

- **FPGA**: DE2-115 or compatible
- **Serial Interface**: USB-to-UART converter
- **Receiver Module**: Adjustable receiver diameter (e.g., 10 cm)
- **Light Source**: 530 nm wavelength (green)

## Dependencies

- Python 3.x
- numpy
- scipy
- matplotlib
- pandas
- pyserial

## Installation

```bash
pip install numpy scipy matplotlib pandas pyserial
```

## Usage

### Viewing QKD Data
```bash
cd data/
# CSV files contain collected QKD measurements
```

### Lookup Table Generation
```bash
cd lut/
python lut_env1_clear_ocean.py    # Clear water LUT
python lut_env2_coastal.py         # Coastal water LUT
python lut_env3_harbor_bubbles.py  # Turbid harbor LUT
```

### FPGA RTL Compilation and Synthesis
```bash
cd rtl/
# Open with Altera Quartus II
quartus uwoc_qkd_receiver.qpf

# Build flow:
# 1. Analysis & Synthesis
# 2. Place & Route
# 3. Generate `.sof` file for programming
# 4. Program DE2-115 board
```

### RTL Simulation
```bash
# Run ModelSim/Quartus simulation
cd rtl/
vsim -do "tb_top_qkd_receiver.do"

# Or use Quartus integrated simulator
quartus_sh -t run_simulation.tcl
```

### Viewing Quantum Bit Stream (Key Output)
```bash
cd monitoring/

# Option 1: Generate simulated bitstream from QBER metrics
python bitstream_simulator.py
# This generates:
# - bitstream.bin (raw binary format)
# - bitstream.hex (hexadecimal format)  
# - bitstream_formatted.txt (formatted for reading)
# - bitstream_analysis.png (visualization plots)

# Option 2: Read REAL bitstream from FPGA hardware ⭐
# (Requires RTL modification - see REAL_BITSTREAM_GUIDE.md)
python real_bitstream_reader.py
# Interactive mode to read actual quantum bits captured by FPGA receiver
# Generates: real_qkd_bitstream.bin, real_qkd_metadata.txt, etc.

# Option 3: Read simulated bitstream with reader
python bitstream_reader.py
```

**For real bitstream extraction:** See [REAL_BITSTREAM_GUIDE.md](REAL_BITSTREAM_GUIDE.md) for detailed implementation instructions.

### Real-Time Monitoring
```bash
cd monitoring/
# Edit SERIAL_PORT in uart_daq_plotter.py to match your COM port
python uart_daq_plotter.py
```

### Visualization
```bash
cd plots/
python plot_loss.py
```

## Configuration

### UART Settings
- **Default Port**: COM16 (modify in `monitoring/uart_daq_plotter.py`)
- **Baud Rate**: 115200 bps
- **Data Points**: 61 distance sweep points
- **Samples per Distance**: 4 measurements (with first packet skipped after distance change)

### Environment Parameters
Each environment model includes:
- Device parameters: μ_alice (photon rate), η_bob (detector efficiency)
- Optical parameters: wavelength, water refractive index, receiver diameter, beam divergence
- Scattering model: fixed scattering coefficient and bubble parameters
- Turbulence parameters: oceanic turbulence correlation length

## Quantum Bit Stream Output

The project can output quantum bit sequences in two ways:

### 1. Simulated Bitstream (Python-based)
Uses the `bitstream_simulator.py` script to generate synthetic bit sequences based on measured QBER:

**Features:**
- Generates realistic bit patterns matching measured quantum channel characteristics
- Output formats: Binary, Hexadecimal, Formatted text
- Statistical analysis of bit distribution and run-length encoding
- Visualization plots showing bit patterns, error positions, and distributions

**Usage:**
```bash
cd monitoring/
python bitstream_simulator.py
```

**Output files:**
- `bitstream.bin` - Raw binary format (1s and 0s)
- `bitstream.hex` - Hexadecimal representation
- `bitstream_formatted.txt` - Formatted with byte grouping
- `bitstream_analysis.png` - Visualization plots

### 2. Actual Bitstream from FPGA (Hardware-based)
To output real quantum bit sequences from the FPGA receiver:

**RTL Modification Required:**
Modify `rtl/top_qkd_receiver.v` to add a bitstream buffer:

```verilog
// Add to top_qkd_receiver.v
reg [1023:0] sifted_bits;  // Store 1024 sifted bits
reg [1023:0] error_mask;   // Error positions (1=error, 0=ok)

// Capture bits when basis matches and photon received
always @(posedge clk_50mhz) begin
    if (basis_match && photon_received) begin
        sifted_bits[bit_count] <= received_bit;
        error_mask[bit_count]  <= bit_error;
    end
end

// Transmit bitstream packet format: 0xBB + 128 bytes + checksum + 0x55
```

**UART Protocol for Bitstream Packet:**
- Byte 0: 0xBB (start marker)
- Bytes 1-128: 1024 bits as 128 bytes
- Byte 129: XOR checksum
- Byte 130: 0x55 (end marker)

**Read bitstream in Python:**
```python
from monitoring.bitstream_reader import read_bitstream_packet
import serial

ser = serial.Serial('COM16', 115200)
bitstream = read_bitstream_packet(ser)
print(f"Received {len(bitstream)} bits: {bitstream[:64]}...")
```

## Data Analysis

The project tracks:
- Quantum Bit Error Rate (QBER)
- Secret Key Rate (SKR)
- Path loss and attenuation
- Scattering effects
- Turbulence impact
- **Quantum Bit Sequences** (with extended RTL)

## Contributing

When adding new features or modifications, ensure:
1. Environment-specific models maintain consistency
2. Lookup table parameters are properly validated
3. UART communication is robust to noise
4. Data files are properly stored in the `data/` directory

## License

[Add your license here]

## Notes

- Files in `deprecated/` folder are excluded from version control
- Use the lookup table `.mif` files as read-only for FPGA deployment
- Real-time monitoring may require calibration with your specific hardware setup
- Distance sweep range: 1.0 m to 7.0 m (0.1 m intervals)
