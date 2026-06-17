`timescale 1ns / 1ps

// ============================================================
// MODULE: qkd_bitstream_buffer
// PURPOSE: Capture actual sifted bits and send via UART
// 
// This module maintains a circular buffer of sifted bits
// and transmits them to PC every window (typically 1 second)
// ============================================================

module qkd_bitstream_buffer (
    input  wire        clk,
    input  wire        rst_n,
    
    // From receiver
    input  wire        pulse_valid,
    input  wire        photon_received,
    input  wire        basis_match,
    input  wire        received_bit,
    input  wire        bit_error,
    
    // Control
    input  wire        clear_window,
    input  wire        trigger_transmit,
    
    // Status
    output reg  [9:0]  bit_count,        // How many bits in current buffer
    output reg  [9:0]  error_count,      // How many errors
    
    // Output interface
    output reg         valid_out,
    output reg  [7:0]  data_out,
    output reg  [9:0]  packet_index,     // Which byte of buffer being transmitted
    input  wire        ready_out
);

    // ============================================================
    // 1. BIT BUFFER (1024 bits = 128 bytes)
    // ============================================================
    reg [7:0] bit_buffer[127:0];  // 128 bytes
    
    // Working registers during capture
    reg [7:0] byte_accumulator;
    reg [2:0] bit_in_byte;        // 0-7
    reg [9:0] total_bits;         // 0-1023
    reg [9:0] error_positions[31:0]; // Store up to 32 error positions
    reg [4:0] error_idx;
    
    // ============================================================
    // 2. CAPTURE BITS DURING 1-SECOND WINDOW
    // ============================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            byte_accumulator <= 8'b0;
            bit_in_byte      <= 3'b0;
            total_bits       <= 10'b0;
            error_idx        <= 5'b0;
            bit_count        <= 10'b0;
            error_count      <= 10'b0;
        end
        else if (clear_window) begin
            byte_accumulator <= 8'b0;
            bit_in_byte      <= 3'b0;
            total_bits       <= 10'b0;
            error_idx        <= 5'b0;
            bit_count        <= 10'b0;
            error_count      <= 10'b0;
        end
        else if (pulse_valid && photon_received && basis_match && total_bits < 10'd1024) begin
            // Capture sifted bit
            byte_accumulator[bit_in_byte] <= received_bit;
            
            // Track errors
            if (bit_error) begin
                error_count <= error_count + 1'b1;
                if (error_idx < 5'd31)
                    error_positions[error_idx] <= total_bits;
                error_idx <= error_idx + 1'b1;
            end
            
            // Increment bit position
            if (bit_in_byte == 3'b111) begin
                // Byte complete, store it
                bit_buffer[total_bits[9:3]] <= byte_accumulator;
                byte_accumulator <= 8'b0;
                bit_in_byte <= 3'b0;
            end else begin
                bit_in_byte <= bit_in_byte + 1'b1;
            end
            
            total_bits <= total_bits + 1'b1;
        end
        else if (trigger_transmit) begin
            bit_count <= total_bits;
        end
    end
    
    // ============================================================
    // 3. TRANSMIT BUFFER VIA UART
    //
    // Packet format:
    // Byte 0    : 0xCC (start marker for bitstream)
    // Byte 1-128: bit_buffer[0:127]
    // Byte 129  : error_count[7:0]
    // Byte 130  : error_count[15:8]
    // Byte 131  : total_bits[7:0]
    // Byte 132  : total_bits[15:8]
    // Byte 133  : checksum
    // Byte 134  : 0x55 (end marker)
    //
    // Total: 135 bytes per packet
    // ============================================================
    
    reg [7:0] state;
    reg [9:0] tx_index;
    reg [7:0] tx_checksum;
    
    localparam STATE_IDLE       = 8'd0;
    localparam STATE_START      = 8'd1;
    localparam STATE_BUFFER     = 8'd2;  // Transmit bit_buffer
    localparam STATE_ERROR_LO   = 8'd3;
    localparam STATE_ERROR_HI   = 8'd4;
    localparam STATE_COUNT_LO   = 8'd5;
    localparam STATE_COUNT_HI   = 8'd6;
    localparam STATE_CHECKSUM   = 8'd7;
    localparam STATE_END        = 8'd8;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= STATE_IDLE;
            valid_out   <= 1'b0;
            data_out    <= 8'b0;
            tx_index    <= 10'b0;
            tx_checksum <= 8'b0;
            packet_index <= 10'b0;
        end
        else begin
            valid_out <= 1'b0;
            
            case (state)
                STATE_IDLE: begin
                    if (trigger_transmit) begin
                        state <= STATE_START;
                        tx_checksum <= 8'b0;
                        tx_index <= 10'b0;
                    end
                end
                
                STATE_START: begin
                    if (ready_out) begin
                        valid_out <= 1'b1;
                        data_out <= 8'hCC;  // Start marker
                        tx_checksum <= tx_checksum ^ 8'hCC;
                        state <= STATE_BUFFER;
                        tx_index <= 10'b0;
                    end
                end
                
                STATE_BUFFER: begin
                    if (ready_out) begin
                        if (tx_index < 10'd128) begin
                            valid_out <= 1'b1;
                            data_out <= bit_buffer[tx_index];
                            tx_checksum <= tx_checksum ^ bit_buffer[tx_index];
                            packet_index <= tx_index;
                            tx_index <= tx_index + 1'b1;
                        end else begin
                            state <= STATE_ERROR_LO;
                        end
                    end
                end
                
                STATE_ERROR_LO: begin
                    if (ready_out) begin
                        valid_out <= 1'b1;
                        data_out <= error_count[7:0];
                        tx_checksum <= tx_checksum ^ error_count[7:0];
                        state <= STATE_ERROR_HI;
                    end
                end
                
                STATE_ERROR_HI: begin
                    if (ready_out) begin
                        valid_out <= 1'b1;
                        data_out <= error_count[15:8];
                        tx_checksum <= tx_checksum ^ error_count[15:8];
                        state <= STATE_COUNT_LO;
                    end
                end
                
                STATE_COUNT_LO: begin
                    if (ready_out) begin
                        valid_out <= 1'b1;
                        data_out <= bit_count[7:0];
                        tx_checksum <= tx_checksum ^ bit_count[7:0];
                        state <= STATE_COUNT_HI;
                    end
                end
                
                STATE_COUNT_HI: begin
                    if (ready_out) begin
                        valid_out <= 1'b1;
                        data_out <= bit_count[15:8];
                        tx_checksum <= tx_checksum ^ bit_count[15:8];
                        state <= STATE_CHECKSUM;
                    end
                end
                
                STATE_CHECKSUM: begin
                    if (ready_out) begin
                        valid_out <= 1'b1;
                        data_out <= tx_checksum;
                        state <= STATE_END;
                    end
                end
                
                STATE_END: begin
                    if (ready_out) begin
                        valid_out <= 1'b1;
                        data_out <= 8'h55;  // End marker
                        state <= STATE_IDLE;
                    end
                end
                
                default:
                    state <= STATE_IDLE;
            endcase
        end
    end

endmodule
