`timescale 1ns / 1ps

// =============================================================
// Von Neumann extractor
// 00 -> discard
// 11 -> discard
// 01 -> output 0
// 10 -> output 1
// =============================================================
module trng_vn_extractor (
    input  wire clk,
    input  wire rst_n,

    input  wire raw_valid,
    input  wire raw_bit,

    output reg  out_valid,
    output reg  out_bit
);

    reg have_first;
    reg first_bit;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            have_first <= 1'b0;
            first_bit  <= 1'b0;
            out_valid  <= 1'b0;
            out_bit    <= 1'b0;
        end else begin
            out_valid <= 1'b0;

            if (raw_valid) begin
                if (!have_first) begin
                    first_bit  <= raw_bit;
                    have_first <= 1'b1;
                end else begin
                    have_first <= 1'b0;

                    case ({first_bit, raw_bit})
                        2'b01: begin
                            out_valid <= 1'b1;
                            out_bit   <= 1'b0;
                        end

                        2'b10: begin
                            out_valid <= 1'b1;
                            out_bit   <= 1'b1;
                        end

                        default: begin
                            out_valid <= 1'b0; // 00 hoặc 11: bỏ
                            out_bit   <= 1'b0;
                        end
                    endcase
                end
            end
        end
    end

endmodule
