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

## Data Analysis

The project tracks:
- Quantum Bit Error Rate (QBER)
- Secret Key Rate (SKR)
- Path loss and attenuation
- Scattering effects
- Turbulence impact

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
