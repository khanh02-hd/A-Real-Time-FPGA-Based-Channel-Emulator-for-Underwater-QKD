# ============================================================
# Main FPGA clock: 50 MHz = 20 ns
# ============================================================
create_clock -name clk_50mhz -period 20.000 [get_ports {clk_50mhz}]

derive_clock_uncertainty

# ============================================================
# Asynchronous reset
# rst_n is an asynchronous active-low reset.
# ============================================================
set_false_path -from [get_ports {rst_n}]

# ============================================================
# TRNG ring oscillator timing exception
#
# raw_entropy comes from ring oscillator combinational loops.
# It is asynchronous to clk_50mhz.
#
# raw_meta is the first synchronizer register, so the path
# into raw_meta is excluded from normal timing analysis.
# ============================================================
set_false_path -to [get_registers -nowarn {*raw_meta*}]