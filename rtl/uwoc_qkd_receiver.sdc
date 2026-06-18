# ============================================================
# Main FPGA clock: 50 MHz = 20 ns
# ============================================================

create_clock -name clk_50mhz -period 20.000 [get_ports {clk_50mhz}]

derive_clock_uncertainty


# ============================================================
# Asynchronous reset
# ============================================================

set_false_path -from [get_ports {rst_n}]


# ============================================================
# NOTE:
# The TRNG raw_meta false path is intentionally not constrained here
# because TRNG_SIM_MODE=1 removes raw_meta during simulation.
# For FPGA hardware mode, timing warnings related to raw_meta can be
# safely ignored because raw_meta is the first synchronizer register
# for ring oscillator entropy.
# ============================================================ 