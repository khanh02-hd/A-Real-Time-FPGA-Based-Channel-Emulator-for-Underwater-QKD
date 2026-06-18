`timescale 1ns / 1ps

// =============================================================
// TRNG source for BB84 QKD
//
// random_bits[0] -> Alice bit
// random_bits[1] -> Alice basis
// random_bits[2] -> Bob basis
//
// Hardware mode:
//   Uses multiple ring-oscillator TRNG lanes.
//   Uses whitening from 16 physical TRNG bits -> 3 BB84 bits.
//
// Simulation mode:
//   Uses xorshift LFSR for fast simulation.
//
// This version fixes buffered_bits latch inference in SIM_MODE.
// =============================================================

module trng_qkd3_source #(
    parameter SIM_MODE     = 0,
    parameter LANE_COUNT   = 16,
    parameter RO_BANKS     = 4,
    parameter RO_STAGES    = 5,
    parameter BUFFER_BITS  = 128
)(
    input  wire clk,
    input  wire rst_n,

    input  wire request_3bits,

    output reg        random_valid,
    output reg  [2:0] random_bits,
    output wire       ready_3bits,
    output reg  [7:0] buffered_bits
);

    generate
        // =====================================================
        // SIMULATION MODE
        // =====================================================
        if (SIM_MODE != 0) begin : GEN_SIM_MODE

            reg [31:0] sim_lfsr;

            assign ready_3bits = 1'b1;

            function [31:0] xs32_next;
                input [31:0] x;
                reg [31:0] y;
                begin
                    y = x;
                    y = y ^ (y << 13);
                    y = y ^ (y >> 17);
                    y = y ^ (y << 5);

                    if (y == 32'd0)
                        xs32_next = 32'h1ACE_B00C;
                    else
                        xs32_next = y;
                end
            endfunction

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    sim_lfsr      <= 32'hA5A5_1234;
                    random_valid  <= 1'b0;
                    random_bits   <= 3'b000;
                    buffered_bits <= 8'd255;
                end else begin
                    random_valid  <= 1'b0;
                    buffered_bits <= 8'd255;
                    sim_lfsr      <= xs32_next(sim_lfsr);

                    if (request_3bits) begin
                        random_bits  <= sim_lfsr[2:0];
                        random_valid <= 1'b1;
                    end
                end
            end

        end else begin : GEN_HARDWARE_TRNG

            // =================================================
            // HARDWARE TRNG MODE
            // =================================================

            wire [LANE_COUNT-1:0] lane_valid;
            wire [LANE_COUNT-1:0] lane_bit;

            genvar i;
            for (i = 0; i < LANE_COUNT; i = i + 1) begin : GEN_LANE
                trng_ro_lane #(
                    .RO_BANKS  (RO_BANKS),
                    .RO_STAGES (RO_STAGES)
                ) u_lane (
                    .clk       (clk),
                    .rst_n     (rst_n),
                    .bit_valid (lane_valid[i]),
                    .bit_out   (lane_bit[i])
                );
            end

            wire all_lane_valid;
            assign all_lane_valid = &lane_valid;

            assign ready_3bits = all_lane_valid;

            reg [31:0] whiten_state;

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    random_valid  <= 1'b0;
                    random_bits   <= 3'b000;
                    whiten_state  <= 32'hA3C5_7E19;
                    buffered_bits <= 8'd0;
                end else begin
                    random_valid <= 1'b0;

                    if (all_lane_valid)
                        buffered_bits <= 8'd16;
                    else
                        buffered_bits <= 8'd0;

                    if (request_3bits && all_lane_valid) begin

                        random_bits[0] <= lane_bit[0]  ^
                                          lane_bit[3]  ^
                                          lane_bit[5]  ^
                                          lane_bit[7]  ^
                                          lane_bit[11] ^
                                          lane_bit[13] ^
                                          whiten_state[0] ^
                                          whiten_state[11];

                        random_bits[1] <= lane_bit[1]  ^
                                          lane_bit[2]  ^
                                          lane_bit[6]  ^
                                          lane_bit[8]  ^
                                          lane_bit[12] ^
                                          lane_bit[15] ^
                                          whiten_state[5] ^
                                          whiten_state[19];

                        random_bits[2] <= lane_bit[0]  ^
                                          lane_bit[4]  ^
                                          lane_bit[9]  ^
                                          lane_bit[10] ^
                                          lane_bit[14] ^
                                          lane_bit[15] ^
                                          whiten_state[9] ^
                                          whiten_state[27];

                        random_valid <= 1'b1;

                        whiten_state <= (whiten_state ^ {16'd0, lane_bit[15:0]})
                                        ^ {whiten_state[24:0], 7'd0}
                                        ^ {3'd0, whiten_state[31:3]};
                    end
                end
            end

        end
    endgenerate

endmodule 