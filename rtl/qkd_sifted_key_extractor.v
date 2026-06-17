`timescale 1ns / 1ps

// ============================================================
// MODULE: qkd_sifted_key_extractor
// PURPOSE: Extract sifted bits (keys) from QKD receiver
//          and transmit them via UART
//
// This module:
// 1. Captures sifted bits (basis_match + photon_received)
// 2. Buffers keys during 1-second window
// 3. Transmits keys via UART every second
// ============================================================

module qkd_sifted_key_extractor (
    input  wire        clk,
    input  wire        rst_n,
    
    // ========== FROM RECEIVER ==========
    input  wire        pulse_valid,      // New quantum event
    input  wire        photon_received,  // Photon detected
    input  wire        basis_match,      // Basis matches (keep bit)
    input  wire        received_bit,     // Actual quantum bit value
    
    // ========== CONTROL ==========
    input  wire        clear_window,     // Reset counters (every 1 sec)
    input  wire        trigger_transmit, // Start sending keys via UART
    
    // ========== STATUS ==========
    output reg  [15:0] key_bits_count,   // How many sifted bits in this window
    
    // ========== UART OUTPUT INTERFACE ==========
    output reg         uart_key_valid,
    output reg  [7:0]  uart_key_data,
    input  wire        uart_key_ready,
    
    // ========== DEBUG ==========
    output reg  [31:0] debug_bits_total,
    output reg  [31:0] debug_keys_sent
);

    // ============================================================
    // 1. KEY BUFFER (4096 bits = 512 bytes max per window)
    // ============================================================
    reg [7:0] key_buffer[511:0];  // 512 bytes = 4096 bits
    
    reg [7:0] byte_accumulator;
    reg [2:0] bit_in_byte;         // 0-7: which bit in current byte
    reg [15:0] key_count;          // 0-4095 bits in current window
    
    // ============================================================
    // 2. CAPTURE SIFTED BITS (KEYS)
    // ============================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            byte_accumulator <= 8'b0;
            bit_in_byte      <= 3'b0;
            key_count        <= 16'b0;
            key_bits_count   <= 16'b0;
            debug_bits_total <= 32'b0;
        end
        else if (clear_window) begin
            // Reset for new window
            byte_accumulator <= 8'b0;
            bit_in_byte      <= 3'b0;
            key_count        <= 16'b0;
            key_bits_count   <= 16'b0;
        end
        else if (pulse_valid && photon_received && basis_match && key_count < 16'd4096) begin
            // ==============================================
            // CAPTURE SIFTED BIT (this is the key!)
            // ==============================================
            byte_accumulator[bit_in_byte] <= received_bit;
            debug_bits_total <= debug_bits_total + 1'b1;
            
            // Check if byte is complete
            if (bit_in_byte == 3'b111) begin
                // Byte complete - store it
                key_buffer[key_count[15:3]] <= byte_accumulator;
                byte_accumulator <= 8'b0;
                bit_in_byte <= 3'b0;
            end else begin
                bit_in_byte <= bit_in_byte + 1'b1;
            end
            
            key_count <= key_count + 1'b1;
        end
        else if (trigger_transmit) begin
            key_bits_count <= key_count;
        end
    end
    
    // ============================================================
    // 3. TRANSMIT KEYS VIA UART
    //
    // Packet format:
    // Byte 0    : 0xDD (key data start marker)
    // Byte 1-2  : key_bits_count (16-bit little-endian)
    // Byte 3... : key_buffer[] (up to 512 bytes)
    // Last byte : 0x55 (end marker)
    //
    // Example for 256 keys (32 bytes):
    // 0xDD 0x00 0x01 [32 bytes] 0x55
    // ============================================================
    
    reg [8:0] state;
    reg [15:0] tx_index;
    reg [15:0] buffer_size;
    
    localparam STATE_IDLE      = 9'd0;
    localparam STATE_START     = 9'd1;
    localparam STATE_COUNT_LO  = 9'd2;
    localparam STATE_COUNT_HI  = 9'd3;
    localparam STATE_BUFFER    = 9'd4;
    localparam STATE_END       = 9'd5;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= STATE_IDLE;
            uart_key_valid <= 1'b0;
            uart_key_data  <= 8'b0;
            tx_index      <= 16'b0;
            buffer_size   <= 16'b0;
            debug_keys_sent <= 32'b0;
        end
        else begin
            uart_key_valid <= 1'b0;
            
            case (state)
                STATE_IDLE: begin
                    if (trigger_transmit) begin
                        state <= STATE_START;
                        buffer_size <= (key_bits_count + 7) >> 3;  // Convert bits to bytes
                        tx_index <= 16'b0;
                    end
                end
                
                STATE_START: begin
                    if (uart_key_ready) begin
                        uart_key_valid <= 1'b1;
                        uart_key_data <= 8'hDD;  // Start marker
                        state <= STATE_COUNT_LO;
                    end
                end
                
                STATE_COUNT_LO: begin
                    if (uart_key_ready) begin
                        uart_key_valid <= 1'b1;
                        uart_key_data <= key_bits_count[7:0];
                        state <= STATE_COUNT_HI;
                    end
                end
                
                STATE_COUNT_HI: begin
                    if (uart_key_ready) begin
                        uart_key_valid <= 1'b1;
                        uart_key_data <= key_bits_count[15:8];
                        state <= STATE_BUFFER;
                        tx_index <= 16'b0;
                    end
                end
                
                STATE_BUFFER: begin
                    if (uart_key_ready) begin
                        if (tx_index < buffer_size) begin
                            uart_key_valid <= 1'b1;
                            uart_key_data <= key_buffer[tx_index];
                            tx_index <= tx_index + 1'b1;
                            debug_keys_sent <= debug_keys_sent + 1'b1;
                        end else begin
                            state <= STATE_END;
                        end
                    end
                end
                
                STATE_END: begin
                    if (uart_key_ready) begin
                        uart_key_valid <= 1'b1;
                        uart_key_data <= 8'h55;  // End marker
                        state <= STATE_IDLE;
                    end
                end
                
                default:
                    state <= STATE_IDLE;
            endcase
        end
    end

endmodule
