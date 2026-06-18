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

# Option 1: Read ACTUAL quantum keys from FPGA ⭐⭐⭐ (RECOMMENDED)
python fpga_key_and_metric_reader.py
# Interactive mode - connect to FPGA and extract real sifted keys
# Generates: fpga_quantum_keys.bin, fpga_quantum_keys.hex, fpga_quantum_keys_metadata.txt
# See FPGA_KEYS_GUIDE.md for integration instructions

# Option 2: Generate simulated bitstream from QBER metrics
python bitstream_simulator.py
# This generates:
# - bitstream.bin (raw binary format)
# - bitstream.hex (hexadecimal format)  
# - bitstream_formatted.txt (formatted for reading)
# - bitstream_analysis.png (visualization plots)

# Option 3: Read bitstream from FPGA (requires RTL modification)
python bitstream_reader.py  # Alternative reader
```

**For real FPGA keys:** See [FPGA_KEYS_GUIDE.md](FPGA_KEYS_GUIDE.md) for detailed setup.

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

The FPGA transmits one complete UART frame per measurement window:

0xAA
14-byte metric payload
0xBB
2-byte key payload length
raw sifted key payload
0x55

Use:
python fpga_key_and_metric_reader.py

### 1. Actual Sifted Keys from FPGA (Real Quantum Keys) ⭐
Uses the new `qkd_sifted_key_extractor.v` RTL module to generate and transmit **real sifted keys**:

**Features:**
- FPGA generates actual sifted bits (basis matched photons)
- Real-time key extraction during each 1-second window
- Transmitted via extended UART protocol (frame 0xAA + 0xBB)
- Interactive Python reader to capture and export keys
- Statistical analysis and randomness validation

**Usage:**
```bash
cd monitoring/
python fpga_key_and_metric_reader.py
```

**Implementation:** See [FPGA_KEYS_GUIDE.md](FPGA_KEYS_GUIDE.md) for RTL integration

**Output files:**
- `fpga_quantum_keys.bin` - Raw sifted bits (actual keys!)
- `fpga_quantum_keys.hex` - Hexadecimal format
- `fpga_quantum_keys_formatted.txt` - Formatted with timestamps
- `fpga_quantum_keys_metadata.txt` - Metadata (bit count, QBER, etc)

### 2. Simulated Bitstream (Python-based)
Uses the `bitstream_simulator.py` script to generate synthetic bit sequences based on measured QBER

**Features:**
- Generates realistic bit patterns matching quantum channel characteristics
- Output formats: Binary, Hexadecimal, Formatted text
- Statistical analysis of bit distribution and run-length encoding
- Visualization plots showing bit patterns, error positions, and distributions

**Usage:**
```bash
cd monitoring/
python bitstream_simulator.py
```

### 3. Actual Bitstream from FPGA (Alternative)
The `bitstream_reader.py` and `real_bitstream_reader.py` provide alternative ways to capture raw bitstream

---

## Key Generation Architecture

```
FPGA Quantum Receiver
│
├─ Photon Detection (APD)
├─ Basis Selection (Random basis)
├─ Basis Matching Check
│
└─ Sifted Bits → qkd_sifted_key_extractor.v
                  │
                  ├─ Buffer capture (1024 bits max)
                  ├─ Count sifted bits
                  └─ UART transmission (0xAA + 14-byte metric + 0xBB + key payload length + key payload + 0x55)
                     │
                     ↓
                  UART @ 115200 bps
                     │
                     ↓ (PC via serial port)
                     │
         fpga_key_and_metric_reader.py (Python)
                     │
                     ├─ Verify checksum
                     ├─ Extract bits
                     ├─ Analyze randomness
                     └─ Export to files
                        │
                        ✓ fpga_quantum_keys.bin (SIFTED KEYS)
                        ✓ Statistical analysis
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
