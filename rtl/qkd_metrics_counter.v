`timescale 1ns / 1ps

module qkd_metrics_counter (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        clear_window,

    input  wire        pulse_valid,
    input  wire        photon_received,
    input  wire        basis_match,
    input  wire        bit_error,

    output reg  [31:0] n_total,
    output reg  [31:0] n_received,
    output reg  [31:0] n_basis_match,
    output reg  [31:0] n_sifted,
    output reg  [31:0] n_error
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            n_total       <= 32'd0;
            n_received    <= 32'd0;
            n_basis_match <= 32'd0;
            n_sifted      <= 32'd0;
            n_error       <= 32'd0;
        end 
        else if (clear_window) begin
            n_total       <= 32'd0;
            n_received    <= 32'd0;
            n_basis_match <= 32'd0;
            n_sifted      <= 32'd0;
            n_error       <= 32'd0;
        end
        else if (pulse_valid) begin
            n_total <= n_total + 1'b1;

            if (photon_received)
                n_received <= n_received + 1'b1;

            if (basis_match)
                n_basis_match <= n_basis_match + 1'b1;

            if (photon_received && basis_match) begin
                n_sifted <= n_sifted + 1'b1;

                if (bit_error)
                    n_error <= n_error + 1'b1;
            end
        end
    end

endmodule