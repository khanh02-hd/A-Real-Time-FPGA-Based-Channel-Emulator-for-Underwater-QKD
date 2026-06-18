`timescale 1ns / 1ps

module uart_tx #(
    parameter CLK_FREQ  = 50_000_000,
    parameter BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output reg        tx_busy,
    output reg        txd
);

    localparam integer BIT_TMR_MAX = CLK_FREQ / BAUD_RATE;

    reg [15:0] bit_timer;
    reg [3:0]  bit_index;
    reg [7:0]  data_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_busy   <= 1'b0;
            txd       <= 1'b1;   // UART idle high
            bit_timer <= 16'd0;
            bit_index <= 4'd0;
            data_reg  <= 8'd0;
        end else begin
            if (tx_start && !tx_busy) begin
                tx_busy   <= 1'b1;
                data_reg  <= tx_data;
                bit_timer <= 16'd0;
                bit_index <= 4'd0;
                txd       <= 1'b0;   // start bit phát ngay
            end 
            else if (tx_busy) begin
                if (bit_timer == BIT_TMR_MAX - 1) begin
                    bit_timer <= 16'd0;

                    if (bit_index < 8) begin
                        txd       <= data_reg[bit_index]; // data bit LSB first
                        bit_index <= bit_index + 1'b1;
                    end 
                    else if (bit_index == 8) begin
                        txd       <= 1'b1; // stop bit
                        bit_index <= bit_index + 1'b1;
                    end 
                    else begin
                        tx_busy   <= 1'b0;
                        txd       <= 1'b1; // idle
                    end
                end 
                else begin
                    bit_timer <= bit_timer + 1'b1;
                end
            end
        end
    end

endmodule 