`timescale 1ns / 1ps

// =============================================================
// UWOC-QKD SoC with TRNG-assisted BB84 bit/basis generation.
//
// Main function:
// - Generate Alice bit, Alice basis, and Bob basis.
// - Emulate underwater optical channel loss, fading, noise.
// - Generate photon_received, basis_match, bit_error.
// - Output received_bit for sifted-key extraction.
//
// Fixed-point convention:
// - h_o, h_s   : UQ4.12, 1.0 = 4096
// - L_s_const : Q0.32
// - prob_click: Q0.32
// =============================================================

module uwoc_qkd_soc #(
    parameter USE_TRNG_QKD   = 1,
    parameter TRNG_SIM_MODE  = 0,
    parameter TRNG_LANES     = 16,
    parameter TRNG_RO_BANKS  = 4,
    parameter TRNG_RO_STAGES = 5,

    parameter UPDATE_DIV = 5000,
    parameter K_HO       = 6,
    parameter K_HS       = 7
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire [5:0]  SW_env,

    output wire [15:0] addr_ho,
    input  wire [15:0] data_ho,

    output wire [15:0] addr_hs,
    input  wire [15:0] data_hs,

    input  wire [31:0] L_s_const,
    input  wire [31:0] bg_thresh_32,

    output reg         photon_received,
    output reg         basis_match,
    output reg         bit_error,

    // NEW:
    // Bob-side received bit.
    // This bit is kept as raw sifted key when:
    // qkd_event_valid && photon_received && basis_match
    output reg         received_bit,

    output reg         qkd_event_valid,

    output wire        trng_ready_debug,
    output wire [7:0]  trng_buffered_bits_debug
);

    // =========================================================
    // 1. Internal PRNGs for channel/noise emulator
    // =========================================================

    function [31:0] lfsr_next;
        input [31:0] x;
        reg feedback;
        begin
            feedback  = x[31] ^ x[21] ^ x[1] ^ x[0];
            lfsr_next = {x[30:0], feedback};

            if (lfsr_next == 32'd0)
                lfsr_next = 32'h0000_0001;
        end
    endfunction

    reg [31:0] rand_photon;
    reg [31:0] rand_qkd_prng;
    reg [31:0] rand_opt_error;
    reg [31:0] rand_dark;
    reg [31:0] rand_bg;
    reg [31:0] rand_addr_ho;
    reg [31:0] rand_addr_hs;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rand_photon    <= 32'h1357_2468;
            rand_qkd_prng  <= 32'hCAFE_BABE;
            rand_opt_error <= 32'h0F0F_A5A5;
            rand_dark      <= 32'h1234_ABCD;
            rand_bg        <= 32'h8765_4321;
            rand_addr_ho   <= 32'hDEAD_BEEF;
            rand_addr_hs   <= 32'hFACE_CAFE;
        end else begin
            rand_photon    <= lfsr_next(rand_photon);
            rand_qkd_prng  <= lfsr_next(rand_qkd_prng);
            rand_opt_error <= lfsr_next(rand_opt_error);
            rand_dark      <= lfsr_next(rand_dark);
            rand_bg        <= lfsr_next(rand_bg);
            rand_addr_ho   <= lfsr_next(rand_addr_ho);
            rand_addr_hs   <= lfsr_next(rand_addr_hs);
        end
    end

    assign addr_ho = {SW_env[5:0], rand_addr_ho[9:0]};
    assign addr_hs = {SW_env[5:0], rand_addr_hs[9:0]};

    // =========================================================
    // 2. TRNG source for BB84 random bit/basis
    // =========================================================

    wire       trng_bits_valid;
    wire [2:0] trng_bits;
    wire       trng_ready;
    wire [7:0] trng_buffered_bits;

    trng_qkd3_source #(
        .SIM_MODE    (TRNG_SIM_MODE),
        .LANE_COUNT  (TRNG_LANES),
        .RO_BANKS    (TRNG_RO_BANKS),
        .RO_STAGES   (TRNG_RO_STAGES),
        .BUFFER_BITS (128)
    ) u_trng_qkd3_source (
        .clk           (clk),
        .rst_n         (rst_n),
        .request_3bits (1'b1),
        .random_valid  (trng_bits_valid),
        .random_bits   (trng_bits),
        .ready_3bits   (trng_ready),
        .buffered_bits (trng_buffered_bits)
    );

    assign trng_ready_debug         = trng_ready;
    assign trng_buffered_bits_debug = trng_buffered_bits;

    wire       bb84_valid_w;
    wire [2:0] bb84_bits_w;

    assign bb84_valid_w = (USE_TRNG_QKD != 0) ? trng_bits_valid : 1'b1;
    assign bb84_bits_w  = (USE_TRNG_QKD != 0) ? trng_bits : rand_qkd_prng[2:0];

    wire alice_bit_w;
    wire alice_basis_w;
    wire bob_basis_w;
    wire basis_match_w;

    assign alice_bit_w   = bb84_bits_w[0];
    assign alice_basis_w = bb84_bits_w[1];
    assign bob_basis_w   = bb84_bits_w[2];

    assign basis_match_w = (alice_basis_w == bob_basis_w);

    // =========================================================
    // 3. Realtime IIR channel h_o(s,t), h_s(s,t)
    // =========================================================

    reg [31:0] update_cnt;
    reg [15:0] ho_state;
    reg [15:0] hs_state;

    wire [15:0] ho_diff_abs;
    wire [15:0] hs_diff_abs;

    assign ho_diff_abs = (data_ho >= ho_state) ? (data_ho - ho_state) : (ho_state - data_ho);
    assign hs_diff_abs = (data_hs >= hs_state) ? (data_hs - hs_state) : (hs_state - data_hs);

    wire [15:0] ho_step_raw;
    wire [15:0] hs_step_raw;
    wire [15:0] ho_step;
    wire [15:0] hs_step;

    assign ho_step_raw = ho_diff_abs >> K_HO;
    assign hs_step_raw = hs_diff_abs >> K_HS;

    assign ho_step = ((ho_diff_abs != 16'd0) && (ho_step_raw == 16'd0)) ? 16'd1 : ho_step_raw;
    assign hs_step = ((hs_diff_abs != 16'd0) && (hs_step_raw == 16'd0)) ? 16'd1 : hs_step_raw;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            update_cnt <= 32'd0;
            ho_state   <= 16'd4096;
            hs_state   <= 16'd4096;
        end else begin
            if (update_cnt == UPDATE_DIV - 1) begin
                update_cnt <= 32'd0;

                if (data_ho > ho_state)
                    ho_state <= ho_state + ho_step;
                else if (data_ho < ho_state)
                    ho_state <= ho_state - ho_step;

                if (data_hs > hs_state)
                    hs_state <= hs_state + hs_step;
                else if (data_hs < hs_state)
                    hs_state <= hs_state - hs_step;
            end else begin
                update_cnt <= update_cnt + 1'b1;
            end
        end
    end

    // =========================================================
    // 4. Pipelined probability calculation
    // =========================================================

    reg [31:0] h_mult_q24_r;
    reg [31:0] h_total_q12_r;
    reg [63:0] prob_mult_r;
    reg [63:0] prob_shift_r;
    reg [31:0] prob_click_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            h_mult_q24_r  <= 32'd0;
            h_total_q12_r <= 32'd0;
            prob_mult_r   <= 64'd0;
            prob_shift_r  <= 64'd0;
            prob_click_r  <= 32'd0;
        end else begin
            h_mult_q24_r  <= {16'd0, ho_state} * {16'd0, hs_state};
            h_total_q12_r <= h_mult_q24_r >> 12;
            prob_mult_r   <= {32'd0, L_s_const} * {32'd0, h_total_q12_r};
            prob_shift_r  <= prob_mult_r >> 12;

            if (|prob_shift_r[63:32])
                prob_click_r <= 32'hFFFF_FFFF;
            else
                prob_click_r <= prob_shift_r[31:0];
        end
    end

    wire [31:0] prob_click;
    assign prob_click = prob_click_r;

    // =========================================================
    // 5. Photon detection, dark count, background count, error
    // =========================================================

    localparam [15:0] OPT_ERR_THRESH = 16'd983;
    localparam [31:0] DARK_THRESH_32 = 32'd5154;

    wire actual_photon_arrived_w;
    wire is_dark_count_w;
    wire is_bg_count_w;
    wire optical_error_w;

    assign actual_photon_arrived_w = (rand_photon < prob_click);
    assign is_dark_count_w         = (rand_dark   < DARK_THRESH_32);
    assign is_bg_count_w           = (rand_bg     < bg_thresh_32);
    assign optical_error_w         = (rand_opt_error[15:0] < OPT_ERR_THRESH);

    wire signal_bit_w;
    wire noise_bit_w;
    wire photon_received_w;
    wire bob_bit_w;
    wire bit_error_w;

    assign signal_bit_w = basis_match_w ? (alice_bit_w ^ optical_error_w) : rand_qkd_prng[4];
    assign noise_bit_w  = rand_dark[0] ^ rand_bg[0] ^ rand_qkd_prng[5];

    assign photon_received_w = actual_photon_arrived_w | is_dark_count_w | is_bg_count_w;

    assign bob_bit_w = actual_photon_arrived_w ? signal_bit_w : noise_bit_w;

    assign bit_error_w = photon_received_w &&
                         basis_match_w &&
                         (bob_bit_w != alice_bit_w);

    // =========================================================
    // 6. Registered event output
    // =========================================================

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            photon_received <= 1'b0;
            basis_match     <= 1'b0;
            bit_error       <= 1'b0;
            received_bit    <= 1'b0;
            qkd_event_valid <= 1'b0;
        end else begin
            qkd_event_valid <= bb84_valid_w;

            if (bb84_valid_w) begin
                photon_received <= photon_received_w;
                basis_match     <= basis_match_w;
                bit_error       <= bit_error_w;
                received_bit    <= bob_bit_w;
            end else begin
                photon_received <= 1'b0;
                basis_match     <= 1'b0;
                bit_error       <= 1'b0;
                received_bit    <= 1'b0;
            end
        end
    end

endmodule 