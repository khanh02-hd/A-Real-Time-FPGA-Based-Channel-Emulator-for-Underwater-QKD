`timescale 1ns / 1ps

// ============================================================
// MODULE: qkd_sifted_key_extractor
//
// PURPOSE:
//   Capture Bob-side raw sifted key bits.
//
// A bit is kept only when:
//   pulse_valid && photon_received && basis_match
//
// IMPORTANT FOR CYCLONE IV / QUARTUS II 13:
//   Use ONE 1024 x 8 synchronous RAM instead of two separate arrays.
//   Address[9] selects the ping-pong bank.
//   Address[8:0] selects byte inside each bank.
//
// Bank 0:
//   key_mem[0..511]
//
// Bank 1:
//   key_mem[512..1023]
//
// This style is much easier for Quartus to infer M9K Block RAM.
// ============================================================

module qkd_sifted_key_extractor #(
    parameter MAX_BITS  = 4096,
    parameter MAX_BYTES = 512
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        pulse_valid,
    input  wire        photon_received,
    input  wire        basis_match,
    input  wire        received_bit,

    input  wire        snapshot_window,

    output reg [15:0]  key_bits_count,
    output reg [15:0]  key_bytes_count,

    input  wire [8:0]  key_byte_addr,
    output reg  [7:0]  key_byte_data,

    output reg         overflow,
    output reg [31:0]  debug_bits_total,
    output reg [31:0]  debug_windows
);

    // ============================================================
    // Constants
    // ============================================================

    localparam [15:0] MAX_BITS_U16 = MAX_BITS[15:0];

    // 2 banks x 512 bytes = 1024 bytes
    localparam TOTAL_BYTES = 1024;

    // ============================================================
    // RAM
    // ============================================================

    (* ramstyle = "M9K" *) reg [7:0] key_mem [0:TOTAL_BYTES-1];

    // ============================================================
    // State
    // ============================================================

    reg        cap_buf_sel;      // current capture bank
    reg        tx_buf_sel;       // current transmit/read bank

    reg [15:0] cap_bit_count;
    reg [2:0]  bit_in_byte;
    reg [7:0]  byte_accumulator;

    wire sifted_event;
    assign sifted_event = pulse_valid && photon_received && basis_match;

    wire [8:0] cap_byte_addr;
    assign cap_byte_addr = cap_bit_count[11:3];

    wire [9:0] ram_rd_addr;
    assign ram_rd_addr = {tx_buf_sel, key_byte_addr};

    wire [9:0] ram_wr_addr;
    assign ram_wr_addr = {cap_buf_sel, cap_byte_addr};

    reg [7:0] acc_with_new_bit;

    always @(*) begin
        acc_with_new_bit = byte_accumulator;
        acc_with_new_bit[bit_in_byte] = received_bit;
    end

    // ============================================================
    // Synchronous RAM read/write
    //
    // Read latency:
    //   top_qkd_receiver.v must wait before using key_byte_data.
    //
    // Write cases:
    //   1. snapshot_window and partial byte exists
    //   2. sifted_event completes a full byte
    // ============================================================

    always @(posedge clk) begin
        if (!rst_n) begin
            key_byte_data <= 8'd0;
        end else begin
            // Synchronous read
            key_byte_data <= key_mem[ram_rd_addr];

            // Synchronous write
            if (snapshot_window) begin
                if (bit_in_byte != 3'd0) begin
                    key_mem[ram_wr_addr] <= byte_accumulator;
                end
            end else if (sifted_event && (cap_bit_count < MAX_BITS_U16)) begin
                if (bit_in_byte == 3'd7) begin
                    key_mem[ram_wr_addr] <= acc_with_new_bit;
                end
            end
        end
    end

    // ============================================================
    // Capture state + snapshot state
    // ============================================================

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cap_buf_sel      <= 1'b0;
            tx_buf_sel       <= 1'b1;

            cap_bit_count    <= 16'd0;
            bit_in_byte      <= 3'd0;
            byte_accumulator <= 8'd0;

            key_bits_count   <= 16'd0;
            key_bytes_count  <= 16'd0;

            overflow         <= 1'b0;
            debug_bits_total <= 32'd0;
            debug_windows    <= 32'd0;
        end else begin

            // ====================================================
            // Snapshot every measurement window
            // ====================================================
            if (snapshot_window) begin
                tx_buf_sel      <= cap_buf_sel;

                key_bits_count  <= cap_bit_count;
                key_bytes_count <= (cap_bit_count + 16'd7) >> 3;

                cap_buf_sel      <= ~cap_buf_sel;
                cap_bit_count    <= 16'd0;
                bit_in_byte      <= 3'd0;
                byte_accumulator <= 8'd0;

                overflow      <= 1'b0;
                debug_windows <= debug_windows + 1'b1;
            end

            // ====================================================
            // Capture one sifted key bit
            // ====================================================
            else if (sifted_event) begin
                if (cap_bit_count < MAX_BITS_U16) begin

                    if (bit_in_byte == 3'd7) begin
                        byte_accumulator <= 8'd0;
                        bit_in_byte      <= 3'd0;
                    end else begin
                        byte_accumulator <= acc_with_new_bit;
                        bit_in_byte      <= bit_in_byte + 1'b1;
                    end

                    cap_bit_count    <= cap_bit_count + 1'b1;
                    debug_bits_total <= debug_bits_total + 1'b1;
                end else begin
                    overflow <= 1'b1;
                end
            end
        end
    end

endmodule