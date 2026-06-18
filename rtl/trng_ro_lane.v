`timescale 1ns / 1ps

// =============================================================
// Ring-Oscillator based TRNG lane
//
// Output:
//   bit_valid : 1 clock pulse when a random bit is available
//   bit_out   : conditioned TRNG bit
//
// Notes:
// - This module intentionally creates combinational loops.
// - Quartus "Found combinational loop" warnings are expected.
// - Do NOT remove the ring oscillator feedback.
// - Whitening is performed later in trng_qkd3_source.v.
// =============================================================

module trng_ro_lane #(
    parameter RO_BANKS   = 4,
    parameter RO_STAGES  = 5,
    parameter SAMPLE_DIV = 4
)(
    input  wire clk,
    input  wire rst_n,

    output reg  bit_valid,
    output reg  bit_out
);

    // ---------------------------------------------------------
    // 1. Ring oscillator banks
    // ---------------------------------------------------------
    wire [RO_BANKS-1:0] ro_raw;

    genvar b, s;
    generate
        for (b = 0; b < RO_BANKS; b = b + 1) begin : GEN_RO_BANK

            // Chỉ dùng một kiểu attribute để tránh warning override keep.
            (* keep = "true" *) wire [RO_STAGES-1:0] ro_tap;

            // Odd inversion loop
            assign ro_tap[0] = ~ro_tap[RO_STAGES-1];

            for (s = 1; s < RO_STAGES; s = s + 1) begin : GEN_RO_STAGE
                assign ro_tap[s] = ro_tap[s-1];
            end

            assign ro_raw[b] = ro_tap[RO_STAGES-1];

        end
    endgenerate

    // XOR nhiều RO để lấy entropy thô
    wire raw_entropy;
    assign raw_entropy = ^ro_raw;

    // ---------------------------------------------------------
    // 2. Synchronizer + simple conditioner
    // ---------------------------------------------------------
    reg raw_meta;
    reg raw_sync;

    reg [31:0] mix_shift;
    reg [7:0]  warmup_cnt;
    reg [7:0]  sample_cnt;

    wire conditioned_bit;

    assign conditioned_bit =
        raw_sync      ^
        mix_shift[0]  ^
        mix_shift[3]  ^
        mix_shift[7]  ^
        mix_shift[13] ^
        mix_shift[21] ^
        mix_shift[31];

    // ---------------------------------------------------------
    // 3. Sequential logic
    // ---------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            raw_meta   <= 1'b0;
            raw_sync   <= 1'b0;

            mix_shift  <= 32'hA5A5_5A5A;
            warmup_cnt <= 8'd0;
            sample_cnt <= 8'd0;

            bit_valid  <= 1'b0;
            bit_out    <= 1'b0;
        end else begin
            // Đồng bộ tín hiệu bất đồng bộ từ RO về clk
            raw_meta <= raw_entropy;
            raw_sync <= raw_meta;

            // Trộn đơn giản để giảm bias ngắn hạn
            mix_shift <= {
                mix_shift[30:0],
                raw_sync ^ mix_shift[1] ^ mix_shift[5] ^ mix_shift[17] ^ mix_shift[31]
            };

            bit_valid <= 1'b0;

            // Warm-up để RO chạy ổn định trước khi xuất bit
            if (warmup_cnt != 8'hFF) begin
                warmup_cnt <= warmup_cnt + 8'd1;
                sample_cnt <= 8'd0;
            end else begin
                if (sample_cnt >= (SAMPLE_DIV - 1)) begin
                    sample_cnt <= 8'd0;

                    bit_out   <= conditioned_bit;
                    bit_valid <= 1'b1;
                end else begin
                    sample_cnt <= sample_cnt + 8'd1;
                end
            end
        end
    end

endmodule 