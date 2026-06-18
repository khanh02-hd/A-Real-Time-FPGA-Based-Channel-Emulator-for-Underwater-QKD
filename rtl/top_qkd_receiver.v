`timescale 1ns / 1ps

module top_qkd_receiver #(
    parameter WINDOW_TICKS  = 50_000_000,
    parameter ENV_MODE      = 2,  // 0: Clear Water | 1: Coastal Water | 2: Turbid Harbor
    parameter TRNG_SIM_MODE = 0   // 0: FPGA thật | 1: ModelSim simulation
)(
    input  wire clk_50mhz,
    input  wire rst_n,

    output wire alert_led,
    output wire uart_txd
);

    // ============================================================
    // 0. 1-SECOND TIMER
    // ============================================================

    reg [25:0] timer;
    reg        trigger_1sec;
    reg        clear_window;

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n) begin
            timer        <= 26'd0;
            trigger_1sec <= 1'b0;
            clear_window <= 1'b0;
        end else begin
            clear_window <= trigger_1sec;

            if (timer == WINDOW_TICKS - 1'b1) begin
                timer        <= 26'd0;
                trigger_1sec <= 1'b1;
            end else begin
                timer        <= timer + 1'b1;
                trigger_1sec <= 1'b0;
            end
        end
    end

    // ============================================================
    // 1. AUTO-SWEEP
    // ============================================================

    reg [5:0] auto_sw;
    reg [5:0] sw_snapshot;
    reg [2:0] window_cnt;

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n) begin
            auto_sw     <= 6'd0;
            sw_snapshot <= 6'd0;
            window_cnt  <= 3'd0;
        end else if (trigger_1sec) begin
            sw_snapshot <= auto_sw;

            if (window_cnt == 3'd4) begin
                window_cnt <= 3'd0;

                if (auto_sw < 6'd60)
                    auto_sw <= auto_sw + 6'd1;
                else
                    auto_sw <= 6'd60;
            end else begin
                window_cnt <= window_cnt + 3'd1;
            end
        end
    end

    // ============================================================
    // 2. BACKGROUND NOISE BY ENVIRONMENT
    // ============================================================

    reg [31:0] bg_thresh_32;
    reg [31:0] bg_thresh_next;

    localparam [31:0] BG_CLEAR_BASE   = 32'd0;

    localparam [31:0] BG_COASTAL_BASE = 32'd128849;
    localparam [31:0] BG_COASTAL_STEP = 32'd17180;

    localparam [31:0] BG_TURBID_BASE  = 32'd429497;
    localparam [31:0] BG_TURBID_STEP  = 32'd85899;

    wire bg_sweep_advance;
    assign bg_sweep_advance = trigger_1sec &&
                               (window_cnt == 3'd4) &&
                               (auto_sw < 6'd60);

    always @(*) begin
        bg_thresh_next = bg_thresh_32;

        if (ENV_MODE == 0) begin
            bg_thresh_next = BG_CLEAR_BASE;
        end else if (ENV_MODE == 1) begin
            if (bg_sweep_advance)
                bg_thresh_next = bg_thresh_32 + BG_COASTAL_STEP;
            else
                bg_thresh_next = bg_thresh_32;
        end else if (ENV_MODE == 2) begin
            if (bg_sweep_advance)
                bg_thresh_next = bg_thresh_32 + BG_TURBID_STEP;
            else
                bg_thresh_next = bg_thresh_32;
        end else begin
            bg_thresh_next = BG_CLEAR_BASE;
        end
    end

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n) begin
            if (ENV_MODE == 1)
                bg_thresh_32 <= BG_COASTAL_BASE;
            else if (ENV_MODE == 2)
                bg_thresh_32 <= BG_TURBID_BASE;
            else
                bg_thresh_32 <= BG_CLEAR_BASE;
        end else begin
            bg_thresh_32 <= bg_thresh_next;
        end
    end

    // ============================================================
    // 3. PATH LOSS MUX
    // ============================================================
    // NOTE:
    // This L_s_const table must match the selected environment.
    // If you change ENV_MODE, remember to regenerate/copy the correct
    // L_s_const table from the corresponding Python LUT script.
    // ============================================================

    reg [31:0] L_s_const;

    always @(*) begin
        case (auto_sw)
            6'b000000: L_s_const = 32'd68906972;
            6'b000001: L_s_const = 32'd45724626;
            6'b000010: L_s_const = 32'd30849306;
            6'b000011: L_s_const = 32'd21105398;
            6'b000100: L_s_const = 32'd14611558;
            6'b000101: L_s_const = 32'd10219801;
            6'b000110: L_s_const = 32'd7212027;
            6'b000111: L_s_const = 32'd5129462;
            6'b001000: L_s_const = 32'd3673643;
            6'b001001: L_s_const = 32'd2647324;
            6'b001010: L_s_const = 32'd1918345;
            6'b001011: L_s_const = 32'd1397077;
            6'b001100: L_s_const = 32'd1022082;
            6'b001101: L_s_const = 32'd750841;
            6'b001110: L_s_const = 32'd553673;
            6'b001111: L_s_const = 32'd409702;
            6'b010000: L_s_const = 32'd304140;
            6'b010001: L_s_const = 32'd226446;
            6'b010010: L_s_const = 32'd169063;
            6'b010011: L_s_const = 32'd126544;
            6'b010100: L_s_const = 32'd94944;
            6'b010101: L_s_const = 32'd71393;
            6'b010110: L_s_const = 32'd53796;
            6'b010111: L_s_const = 32'd40616;
            6'b011000: L_s_const = 32'd30721;
            6'b011001: L_s_const = 32'd23277;
            6'b011010: L_s_const = 32'd17666;
            6'b011011: L_s_const = 32'd13428;
            6'b011100: L_s_const = 32'd10221;
            6'b011101: L_s_const = 32'd7791;
            6'b011110: L_s_const = 32'd5947;
            6'b011111: L_s_const = 32'd4545;
            6'b100000: L_s_const = 32'd3477;
            6'b100001: L_s_const = 32'd2663;
            6'b100010: L_s_const = 32'd2042;
            6'b100011: L_s_const = 32'd1568;
            6'b100100: L_s_const = 32'd1204;
            6'b100101: L_s_const = 32'd926;
            6'b100110: L_s_const = 32'd713;
            6'b100111: L_s_const = 32'd549;
            6'b101000: L_s_const = 32'd423;
            6'b101001: L_s_const = 32'd327;
            6'b101010: L_s_const = 32'd252;
            6'b101011: L_s_const = 32'd195;
            6'b101100: L_s_const = 32'd151;
            6'b101101: L_s_const = 32'd116;
            6'b101110: L_s_const = 32'd90;
            6'b101111: L_s_const = 32'd70;
            6'b110000: L_s_const = 32'd54;
            6'b110001: L_s_const = 32'd42;
            6'b110010: L_s_const = 32'd32;
            6'b110011: L_s_const = 32'd25;
            6'b110100: L_s_const = 32'd19;
            6'b110101: L_s_const = 32'd15;
            6'b110110: L_s_const = 32'd11;
            6'b110111: L_s_const = 32'd9;
            6'b111000: L_s_const = 32'd7;
            6'b111001: L_s_const = 32'd5;
            6'b111010: L_s_const = 32'd4;
            6'b111011: L_s_const = 32'd3;
            6'b111100: L_s_const = 32'd2;
            default:   L_s_const = 32'd0;
        endcase
    end

    // ============================================================
    // 4. ROM, SOC, COUNTERS
    // ============================================================

    wire [15:0] addr_ho;
    wire [15:0] addr_hs;
    wire [15:0] data_ho;
    wire [15:0] data_hs;

    wire [15:0] rom_skr_data;
    wire [9:0]  rom_skr_addr;

    wire photon_received;
    wire basis_match;
    wire bit_error;
    wire received_bit;
    wire qkd_event_valid;

    wire [31:0] n_total;
    wire [31:0] n_received;
    wire [31:0] n_basis_match;
    wire [31:0] n_sifted;
    wire [31:0] n_error;
    wire [31:0] final_skr;

    wire       trng_ready_debug;
    wire [7:0] trng_buffered_bits_debug;

    rom_ho u_rom_ho (
        .address (addr_ho),
        .clock   (clk_50mhz),
        .q       (data_ho)
    );

    rom_hs u_rom_hs (
        .address (addr_hs),
        .clock   (clk_50mhz),
        .q       (data_hs)
    );

    rom_skr u_rom_skr (
        .address (rom_skr_addr),
        .clock   (clk_50mhz),
        .q       (rom_skr_data)
    );

    uwoc_qkd_soc #(
        .USE_TRNG_QKD  (1),
        .TRNG_SIM_MODE (TRNG_SIM_MODE)
    ) u_soc (
        .clk                      (clk_50mhz),
        .rst_n                    (rst_n),
        .SW_env                   (auto_sw),

        .addr_ho                  (addr_ho),
        .data_ho                  (data_ho),
        .addr_hs                  (addr_hs),
        .data_hs                  (data_hs),

        .L_s_const                (L_s_const),
        .bg_thresh_32             (bg_thresh_32),

        .photon_received          (photon_received),
        .basis_match              (basis_match),
        .bit_error                (bit_error),
        .received_bit             (received_bit),
        .qkd_event_valid          (qkd_event_valid),

        .trng_ready_debug         (trng_ready_debug),
        .trng_buffered_bits_debug (trng_buffered_bits_debug)
    );

    qkd_metrics_counter u_counter (
        .clk             (clk_50mhz),
        .rst_n           (rst_n),
        .clear_window    (clear_window),
        .pulse_valid     (qkd_event_valid),
        .photon_received (photon_received),
        .basis_match     (basis_match),
        .bit_error       (bit_error),

        .n_total         (n_total),
        .n_received      (n_received),
        .n_basis_match   (n_basis_match),
        .n_sifted        (n_sifted),
        .n_error         (n_error)
    );

    // ============================================================
    // 4B. SIFTED KEY EXTRACTOR
    // ============================================================

    wire [15:0] key_bytes_snapshot;
    reg  [8:0]  key_byte_addr_reg;
    wire [7:0]  key_byte_data;
    wire        key_overflow;
    wire [31:0] debug_key_bits_total;
    wire [31:0] debug_key_windows;

    qkd_sifted_key_extractor u_key_extractor (
        .clk              (clk_50mhz),
        .rst_n            (rst_n),

        .pulse_valid      (qkd_event_valid),
        .photon_received  (photon_received),
        .basis_match      (basis_match),
        .received_bit     (received_bit),

        .snapshot_window  (trigger_1sec),

        .key_bits_count   (),                  // not needed in top
        .key_bytes_count  (key_bytes_snapshot),

        .key_byte_addr    (key_byte_addr_reg),
        .key_byte_data    (key_byte_data),

        .overflow         (key_overflow),
        .debug_bits_total (debug_key_bits_total),
        .debug_windows    (debug_key_windows)
    );

    // ============================================================
    // 5. EVALUATOR & UART LATCH
    // ============================================================

    reg [31:0] n_sifted_snapshot;
    reg [31:0] n_error_snapshot;

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n) begin
            n_sifted_snapshot <= 32'd0;
            n_error_snapshot  <= 32'd0;
        end else if (trigger_1sec) begin
            n_sifted_snapshot <= n_sifted;
            n_error_snapshot  <= n_error;
        end
    end

    skr_evaluator u_eval (
        .clk          (clk_50mhz),
        .rst_n        (rst_n),
        .trigger_1sec (trigger_1sec),
        .n_sifted     (n_sifted),
        .n_error      (n_error),
        .rom_skr_addr (rom_skr_addr),
        .rom_skr_data (rom_skr_data),
        .final_skr    (final_skr)
    );

    reg [47:0] uart_trigger_delay;

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n)
            uart_trigger_delay <= 48'd0;
        else
            uart_trigger_delay <= {uart_trigger_delay[46:0], trigger_1sec};
    end

    wire uart_send_pulse;
    assign uart_send_pulse = uart_trigger_delay[47];

    reg [31:0] final_skr_latched;
    reg [31:0] n_sifted_latched;
    reg [31:0] n_error_latched;
    reg [9:0]  qber_latched;
    reg [5:0]  sw_latched;

    reg [15:0] key_bytes_latched;

    reg system_valid;

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n)
            system_valid <= 1'b0;
        else if (uart_send_pulse)
            system_valid <= 1'b1;
    end

    localparam [31:0] MIN_SIFTED_SAFE = 32'd1000;

    assign alert_led = system_valid &&
                       (
                           (qber_latched > 10'd112) ||
                           (final_skr_latched == 32'd0) ||
                           (n_sifted_latched < MIN_SIFTED_SAFE) ||
                           key_overflow
                       );

    // ============================================================
    // 6. UART TRANSMITTER
    //
    // One complete frame per second:
    //
    //   0xAA
    //   14 bytes metric:
    //       final_skr       : 4 bytes, big endian
    //       sw/qber         : 2 bytes
    //       n_sifted        : 4 bytes, big endian
    //       n_error         : 4 bytes, big endian
    //   0xBB
    //   key_payload_length  : 2 bytes, little endian, in bytes
    //   key_payload         : key_bytes_latched bytes
    //   0x55
    //
    // RAM read for key payload is synchronous:
    //   set address -> wait -> wait -> transmit key_byte_data
    // ============================================================

    wire tx_busy;
    reg  tx_start;
    reg  [7:0] tx_data;

    uart_tx u_uart (
        .clk      (clk_50mhz),
        .rst_n    (rst_n),
        .tx_start (tx_start),
        .tx_data  (tx_data),
        .tx_busy  (tx_busy),
        .txd      (uart_txd)
    );

    localparam MODE_METRIC = 1'b0;
    localparam MODE_KEY    = 1'b1;

    localparam UART_IDLE       = 4'd0;
    localparam UART_PREP_BYTE  = 4'd1;
    localparam UART_RAM_WAIT1  = 4'd2;
    localparam UART_RAM_WAIT2  = 4'd3;
    localparam UART_START_BYTE = 4'd4;
    localparam UART_WAIT_BUSY  = 4'd5;
    localparam UART_WAIT_DONE  = 4'd6;
    localparam UART_NEXT_BYTE  = 4'd7;

    reg        packet_mode;
    reg [3:0]  uart_state;
    reg [15:0] byte_index;

    reg [7:0] direct_packet_byte;

    wire [15:0] key_data_index;
    assign key_data_index = (byte_index >= 16'd3) ? (byte_index - 16'd3) : 16'd0;

    wire is_key_data_byte;
    assign is_key_data_byte = (packet_mode == MODE_KEY) &&
                              (byte_index >= 16'd3) &&
                              (byte_index < (16'd3 + key_bytes_latched));

    wire [15:0] key_last_index;
    assign key_last_index = 16'd3 + key_bytes_latched;

    wire current_packet_last;
    assign current_packet_last = (packet_mode == MODE_METRIC) ?
                                 (byte_index == 16'd14) :
                                 (byte_index == key_last_index);

    // Direct bytes do not need RAM access.
    always @(*) begin
        direct_packet_byte = 8'h00;

        if (packet_mode == MODE_METRIC) begin
            case (byte_index[3:0])
                4'd0:  direct_packet_byte = 8'hAA;

                4'd1:  direct_packet_byte = final_skr_latched[31:24];
                4'd2:  direct_packet_byte = final_skr_latched[23:16];
                4'd3:  direct_packet_byte = final_skr_latched[15:8];
                4'd4:  direct_packet_byte = final_skr_latched[7:0];

                4'd5:  direct_packet_byte = {sw_latched[5:0], qber_latched[9:8]};
                4'd6:  direct_packet_byte = qber_latched[7:0];

                4'd7:  direct_packet_byte = n_sifted_latched[31:24];
                4'd8:  direct_packet_byte = n_sifted_latched[23:16];
                4'd9:  direct_packet_byte = n_sifted_latched[15:8];
                4'd10: direct_packet_byte = n_sifted_latched[7:0];

                4'd11: direct_packet_byte = n_error_latched[31:24];
                4'd12: direct_packet_byte = n_error_latched[23:16];
                4'd13: direct_packet_byte = n_error_latched[15:8];
                4'd14: direct_packet_byte = n_error_latched[7:0];

                default: direct_packet_byte = 8'h00;
            endcase
        end else begin
            if (byte_index == 16'd0)
                direct_packet_byte = 8'hBB;
            else if (byte_index == 16'd1)
                direct_packet_byte = key_bytes_latched[7:0];
            else if (byte_index == 16'd2)
                direct_packet_byte = key_bytes_latched[15:8];
            else
                direct_packet_byte = 8'h55;
        end
    end

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n) begin
            uart_state        <= UART_IDLE;
            packet_mode       <= MODE_METRIC;
            byte_index        <= 16'd0;

            tx_start          <= 1'b0;
            tx_data           <= 8'd0;

            key_byte_addr_reg <= 9'd0;

            final_skr_latched <= 32'd0;
            n_sifted_latched  <= 32'd0;
            n_error_latched   <= 32'd0;
            qber_latched      <= 10'd0;
            sw_latched        <= 6'd0;

            key_bytes_latched <= 16'd0;
        end else begin
            tx_start <= 1'b0;

            case (uart_state)

                UART_IDLE: begin
                    if (uart_send_pulse) begin
                        final_skr_latched <= final_skr;
                        qber_latched      <= rom_skr_addr;
                        n_sifted_latched  <= n_sifted_snapshot;
                        n_error_latched   <= n_error_snapshot;
                        sw_latched        <= sw_snapshot;

                        key_bytes_latched <= key_bytes_snapshot;

                        packet_mode       <= MODE_METRIC;
                        byte_index        <= 16'd0;
                        uart_state        <= UART_PREP_BYTE;
                    end
                end

                UART_PREP_BYTE: begin
                    if (!tx_busy) begin
                        if (is_key_data_byte) begin
                            key_byte_addr_reg <= key_data_index[8:0];
                            uart_state        <= UART_RAM_WAIT1;
                        end else begin
                            tx_data    <= direct_packet_byte;
                            uart_state <= UART_START_BYTE;
                        end
                    end
                end

                UART_RAM_WAIT1: begin
                    uart_state <= UART_RAM_WAIT2;
                end

                UART_RAM_WAIT2: begin
                    tx_data    <= key_byte_data;
                    uart_state <= UART_START_BYTE;
                end

                UART_START_BYTE: begin
                    tx_start   <= 1'b1;
                    uart_state <= UART_WAIT_BUSY;
                end

                UART_WAIT_BUSY: begin
                    if (tx_busy)
                        uart_state <= UART_WAIT_DONE;
                end

                UART_WAIT_DONE: begin
                    if (!tx_busy)
                        uart_state <= UART_NEXT_BYTE;
                end

                UART_NEXT_BYTE: begin
                    if (current_packet_last) begin
                        if (packet_mode == MODE_METRIC) begin
                            packet_mode <= MODE_KEY;
                            byte_index  <= 16'd0;
                            uart_state  <= UART_PREP_BYTE;
                        end else begin
                            uart_state <= UART_IDLE;
                        end
                    end else begin
                        byte_index <= byte_index + 1'b1;
                        uart_state <= UART_PREP_BYTE;
                    end
                end

                default: begin
                    uart_state <= UART_IDLE;
                end
            endcase
        end
    end

endmodule 