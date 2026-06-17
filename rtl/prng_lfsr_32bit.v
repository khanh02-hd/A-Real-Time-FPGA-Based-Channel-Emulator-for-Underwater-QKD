`timescale 1ns / 1ps

module prng_lfsr_32bit #(
    parameter SEED = 32'hDEADBEEF
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        en,
    output reg  [31:0] lfsr_out
);

    wire feedback;

    assign feedback = lfsr_out[31] ^ lfsr_out[21] ^ lfsr_out[1] ^ lfsr_out[0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            if (SEED == 32'h00000000)
                lfsr_out <= 32'h00000001;
            else
                lfsr_out <= SEED;
        end
        else if (en) begin
            if (lfsr_out == 32'h00000000)
                lfsr_out <= 32'h00000001;
            else
                lfsr_out <= {lfsr_out[30:0], feedback};
        end
    end

endmodule