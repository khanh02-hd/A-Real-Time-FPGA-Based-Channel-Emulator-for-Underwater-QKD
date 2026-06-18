# Changelog

All notable changes to this project are documented below.

## [Unreleased]

## Project History

### Initial Setup & Architecture (c9982e7)
**Single-FPGA UWOC-QKD Emulator with TRNG and IIR Filter**

Established foundational QKD emulation system:
- Implemented True Random Number Generator (TRNG) using ring oscillators
- Integrated IIR filtering for channel response simulation
- Created single-FPGA architecture for quantum channel emulation
- Established UART communication protocol for data acquisition
- Designed base structure for QKD metrics and key rate evaluation

### Project Structure Reorganization (cb8f43f)
**Restructure Project into Modular Component Architecture**

Reorganized project to separate concerns and improve maintainability:
- **lut/**: Centralized lookup table system for environment-specific channel characteristics
  - Separated environment models: clear ocean, coastal, turbid harbor
  - Pre-computed quantum channel parameters for fast simulation
- **monitoring/**: Unified real-time data acquisition and visualization tools
  - UART DAQ with plotting capabilities
  - Live monitoring dashboard interface
- **rtl/**: Complete FPGA RTL (Verilog) design suite
  - HDL modules for channel simulation and metrics calculation
  - Design files and timing constraints
- **data/**: Experimental and simulation datasets
  - Per-environment test data for validation
- **plots/**: Analysis and visualization utilities

### FPGA RTL Implementation (d186aeb)
**Integrate Complete RTL Design: Channel Simulator, Metrics Counter, and Key Evaluator**

Developed comprehensive FPGA RTL modules for quantum channel simulation:
- **Channel Simulator** (`uwoc_channel_st.v`): Models underwater optical wireless channel with path loss, turbulence, and scattering
- **Metrics Counter** (`qkd_metrics_counter.v`): Real-time QBER (Quantum Bit Error Rate) and key rate calculation
- **Secret Key Rate Evaluator** (`skr_evaluator.v`): Computes secure key rate based on quantum channel conditions
- **ROM Lookup Tables**: Pre-loaded quantum channel characteristics for three environment models
- **System-on-Chip** (`uwoc_qkd_soc.v`): Integrated top-level architecture
- **UART Interface** (`uart_tx.v`): Serial communication with acquisition hardware
- **TRNG Source** (`trng_qkd3_source.v`): Hardware-based random number generation
- Quartus project files and timing constraints (SDC) for DE2-115 FPGA
- Comprehensive testbenches for simulation and validation

### Bitstream Output and Visualization (bebbc52)
**Add Bitstream Export Functionality and Real-Time Visualization Dashboard**

Enabled visualization and export of quantum key data:
- Bitstream export to file formats for post-processing
- Real-time plotting of QKD metrics (QBER, key rate, channel loss)
- Integration of visualization tools with UART data acquisition
- Dashboard interface for monitoring multiple environment conditions simultaneously
- Data logging with timestamp synchronization

### Real FPGA Hardware Integration (caa5c14)
**Enable Real-Time Bitstream Acquisition from FPGA Hardware with Data Logging**

Implemented direct hardware interface for production QKD system:
- Bitstream capture from actual FPGA hardware (DE2-115)
- Real-time data logging with persistent storage
- Hardware synchronization and timing verification
- Support for extended data acquisition sessions
- Integration with actual quantum optical components
- Performance benchmarking against simulation results

### Quantum Key Extraction System (fb9b98c)
**Implement Quantum Key Extraction and Sifting Mechanisms with Performance Metrics**

Developed core quantum key processing pipeline:
- **Key Sifting**: Extraction of valid quantum bits from measurement results (`qkd_sifted_key_extractor.v`)
- **Basis Matching**: Alignment of transmitter and receiver basis selections
- **QBER Calculation**: Real-time quantum bit error rate computation
- **Bitstream Buffering**: Temporary storage for key data (`qkd_bitstream_buffer.v`)
- **Performance Metrics**: Integration with counter and evaluator for SKR determination
- Environment-specific lookup tables for key validation
- Support for continuous key generation and extraction

### Monitoring System Optimization (aa4fc93)
**Streamline Project by Removing Deprecated Monitoring Utilities**

Cleaned up legacy monitoring implementation:
- Removed deprecated monitoring modules that were superseded by new visualization tools
- Streamlined data acquisition pipeline to use optimized UART interface
- Consolidated monitoring functionality into single unified dashboard
- Reduced codebase complexity while maintaining all core functionality
- Improved performance by eliminating redundant monitoring threads

---

## Version Strategy

This project follows semantic versioning once 1.0.0 is released.

- **Main features**: Major version increment
- **Non-breaking additions**: Minor version increment
- **Bug fixes and patches**: Patch version increment

## Future Enhancements

- Multi-FPGA synchronization for expanded key generation
- Machine learning-based channel prediction
- Adaptive key extraction based on channel conditions
- Production-ready bitstream certification system
 