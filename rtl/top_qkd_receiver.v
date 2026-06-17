`timescale 1ns / 1ps

module top_qkd_receiver #(
    parameter WINDOW_TICKS  = 50_000_000, // 1 giây tại 50MHz
    parameter ENV_MODE      = 2,          // 0: Clear Water | 1: Coastal Water | 2: Turbid Harbor
    parameter TRNG_SIM_MODE = 0           // 0: Nạp xuống board FPGA thật | 1: Chạy mô phỏng ModelSim
)(
    input  wire        clk_50mhz,
    input  wire        rst_n,

    output wire        alert_led,
    output wire        uart_txd
);

    // ============================================================
    // 0. TIMER 1 GIÂY
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
    //
    // auto_sw = 0  -> 1.0 m
    // auto_sw = 1  -> 1.1 m
    // ...
    // auto_sw = 60 -> 7.0 m
    //
    // Mỗi mốc giữ 5 packet 1 giây.
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
    // 2. BACKGROUND NOISE THEO MÔI TRƯỜNG
    //
    // Không dùng:
    //   bg = base + auto_sw * step
    //
    // Vì phép nhân tổ hợp này dễ gây fail timing.
    //
    // Cách mới:
    //   - bg_thresh_next luôn được gán mặc định đầy đủ.
    //   - bg_thresh_32 là register, cập nhật bằng clock.
    //   - Khi auto_sw đổi mốc sau mỗi 5 giây, bg tăng thêm step.
    //   - Không infer latch.
    // ============================================================
    reg [31:0] bg_thresh_32;
    reg [31:0] bg_thresh_next;

    localparam [31:0] BG_CLEAR_BASE   = 32'd0;

    localparam [31:0] BG_COASTAL_BASE = 32'd128849;
    localparam [31:0] BG_COASTAL_STEP = 32'd17180;

    localparam [31:0] BG_TURBID_BASE  = 32'd429497;
    localparam [31:0] BG_TURBID_STEP  = 32'd85899;

    wire bg_sweep_advance;
    assign bg_sweep_advance = trigger_1sec && (window_cnt == 3'd4) && (auto_sw < 6'd60);

    always @(*) begin
        // Gán mặc định để không infer latch
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
    // 3. MUX PATH LOSS
    // ============================================================
    reg [31:0] L_s_const;

    always @(*) begin
        case (auto_sw)
            6'b000000: L_s_const = 32'd68906972; // d=1.0m, L_eff=1.604365e-02
            6'b000001: L_s_const = 32'd45724626; // d=1.1m, L_eff=1.064609e-02
            6'b000010: L_s_const = 32'd30849306; // d=1.2m, L_eff=7.182664e-03
            6'b000011: L_s_const = 32'd21105398; // d=1.3m, L_eff=4.913983e-03
            6'b000100: L_s_const = 32'd14611558; // d=1.4m, L_eff=3.402019e-03
            6'b000101: L_s_const = 32'd10219801; // d=1.5m, L_eff=2.379483e-03
            6'b000110: L_s_const = 32'd7212027; // d=1.6m, L_eff=1.679181e-03
            6'b000111: L_s_const = 32'd5129462; // d=1.7m, L_eff=1.194296e-03
            6'b001000: L_s_const = 32'd3673643; // d=1.8m, L_eff=8.553369e-04
            6'b001001: L_s_const = 32'd2647324; // d=1.9m, L_eff=6.163783e-04
            6'b001010: L_s_const = 32'd1918345; // d=2.0m, L_eff=4.466496e-04
            6'b001011: L_s_const = 32'd1397077; // d=2.1m, L_eff=3.252825e-04
            6'b001100: L_s_const = 32'd1022082; // d=2.2m, L_eff=2.379722e-04
            6'b001101: L_s_const = 32'd750841; // d=2.3m, L_eff=1.748189e-04
            6'b001110: L_s_const = 32'd553673; // d=2.4m, L_eff=1.289122e-04
            6'b001111: L_s_const = 32'd409702; // d=2.5m, L_eff=9.539129e-05
            6'b010000: L_s_const = 32'd304140; // d=2.6m, L_eff=7.081323e-05
            6'b010001: L_s_const = 32'd226446; // d=2.7m, L_eff=5.272371e-05
            6'b010010: L_s_const = 32'd169063; // d=2.8m, L_eff=3.936314e-05
            6'b010011: L_s_const = 32'd126544; // d=2.9m, L_eff=2.946335e-05
            6'b010100: L_s_const = 32'd94944; // d=3.0m, L_eff=2.210589e-05
            6'b010101: L_s_const = 32'd71393; // d=3.1m, L_eff=1.662262e-05
            6'b010110: L_s_const = 32'd53796; // d=3.2m, L_eff=1.252551e-05
            6'b010111: L_s_const = 32'd40616; // d=3.3m, L_eff=9.456703e-06
            6'b011000: L_s_const = 32'd30721; // d=3.4m, L_eff=7.152900e-06
            6'b011001: L_s_const = 32'd23277; // d=3.5m, L_eff=5.419713e-06
            6'b011010: L_s_const = 32'd17666; // d=3.6m, L_eff=4.113199e-06
            6'b011011: L_s_const = 32'd13428; // d=3.7m, L_eff=3.126465e-06
            6'b011100: L_s_const = 32'd10221; // d=3.8m, L_eff=2.379919e-06
            6'b011101: L_s_const = 32'd7791; // d=3.9m, L_eff=1.814147e-06
            6'b011110: L_s_const = 32'd5947; // d=4.0m, L_eff=1.384695e-06
            6'b011111: L_s_const = 32'd4545; // d=4.1m, L_eff=1.058227e-06
            6'b100000: L_s_const = 32'd3477; // d=4.2m, L_eff=8.096928e-07
            6'b100001: L_s_const = 32'd2663; // d=4.3m, L_eff=6.202322e-07
            6'b100010: L_s_const = 32'd2042; // d=4.4m, L_eff=4.756180e-07
            6'b100011: L_s_const = 32'd1568; // d=4.5m, L_eff=3.650992e-07
            6'b100100: L_s_const = 32'd1204; // d=4.6m, L_eff=2.805386e-07
            6'b100101: L_s_const = 32'd926; // d=4.7m, L_eff=2.157670e-07
            6'b100110: L_s_const = 32'd713; // d=4.8m, L_eff=1.661004e-07
            6'b100111: L_s_const = 32'd549; // d=4.9m, L_eff=1.279774e-07
            6'b101000: L_s_const = 32'd423; // d=5.0m, L_eff=9.868650e-08
            6'b101001: L_s_const = 32'd327; // d=5.1m, L_eff=7.616050e-08
            6'b101010: L_s_const = 32'd252; // d=5.2m, L_eff=5.882146e-08
            6'b101011: L_s_const = 32'd195; // d=5.3m, L_eff=4.546352e-08
            6'b101100: L_s_const = 32'd151; // d=5.4m, L_eff=3.516411e-08
            6'b101101: L_s_const = 32'd116; // d=5.5m, L_eff=2.721662e-08
            6'b101110: L_s_const = 32'd90; // d=5.6m, L_eff=2.107928e-08
            6'b101111: L_s_const = 32'd70; // d=5.7m, L_eff=1.633633e-08
            6'b110000: L_s_const = 32'd54; // d=5.8m, L_eff=1.266837e-08
            6'b110001: L_s_const = 32'd42; // d=5.9m, L_eff=9.829807e-09
            6'b110010: L_s_const = 32'd32; // d=6.0m, L_eff=7.631657e-09
            6'b110011: L_s_const = 32'd25; // d=6.1m, L_eff=5.928353e-09
            6'b110100: L_s_const = 32'd19; // d=6.2m, L_eff=4.607684e-09
            6'b110101: L_s_const = 32'd15; // d=6.3m, L_eff=3.583087e-09
            6'b110110: L_s_const = 32'd11; // d=6.4m, L_eff=2.787731e-09
            6'b110111: L_s_const = 32'd9; // d=6.5m, L_eff=2.169984e-09
            6'b111000: L_s_const = 32'd7; // d=6.6m, L_eff=1.689926e-09
            6'b111001: L_s_const = 32'd5; // d=6.7m, L_eff=1.316674e-09
            6'b111010: L_s_const = 32'd4; // d=6.8m, L_eff=1.026319e-09
            6'b111011: L_s_const = 32'd3; // d=6.9m, L_eff=8.003398e-10
            6'b111100: L_s_const = 32'd2; // d=7.0m, L_eff=6.243799e-10
            default:   L_s_const = 32'd0;
        endcase
    end

    // ============================================================
    // 4. ROM & SOC & COUNTERS
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

    wire [31:0] n_total;
    wire [31:0] n_received;
    wire [31:0] n_basis_match;
    wire [31:0] n_sifted;
    wire [31:0] n_error;
    wire [31:0] final_skr;

    wire        qkd_event_valid;
    wire        trng_ready_debug;
    wire [7:0]  trng_buffered_bits_debug;

    rom_ho u_rom_ho (
        .address(addr_ho),
        .clock(clk_50mhz),
        .q(data_ho)
    );

    rom_hs u_rom_hs (
        .address(addr_hs),
        .clock(clk_50mhz),
        .q(data_hs)
    );

    rom_skr u_rom_skr (
        .address(rom_skr_addr),
        .clock(clk_50mhz),
        .q(rom_skr_data)
    );

    uwoc_qkd_soc #(
        .USE_TRNG_QKD(1),
        .TRNG_SIM_MODE(TRNG_SIM_MODE)
    ) u_soc (
        .clk(clk_50mhz),
        .rst_n(rst_n),
        .SW_env(auto_sw),

        .addr_ho(addr_ho),
        .data_ho(data_ho),

        .addr_hs(addr_hs),
        .data_hs(data_hs),

        .L_s_const(L_s_const),
        .bg_thresh_32(bg_thresh_32),

        .photon_received(photon_received),
        .basis_match(basis_match),
        .bit_error(bit_error),

        .qkd_event_valid(qkd_event_valid),
        .trng_ready_debug(trng_ready_debug),
        .trng_buffered_bits_debug(trng_buffered_bits_debug)
    );

    qkd_metrics_counter u_counter (
        .clk(clk_50mhz),
        .rst_n(rst_n),
        .clear_window(clear_window),

        .pulse_valid(qkd_event_valid),
        .photon_received(photon_received),
        .basis_match(basis_match),
        .bit_error(bit_error),

        .n_total(n_total),
        .n_received(n_received),
        .n_basis_match(n_basis_match),
        .n_sifted(n_sifted),
        .n_error(n_error)
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
        .clk(clk_50mhz),
        .rst_n(rst_n),
        .trigger_1sec(trigger_1sec),

        .n_sifted(n_sifted),
        .n_error(n_error),

        .rom_skr_addr(rom_skr_addr),
        .rom_skr_data(rom_skr_data),
        .final_skr(final_skr)
    );

    // Delay để chờ divider/SKR pipeline xong trước khi gửi UART
    reg [47:0] uart_trigger_delay;

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n)
            uart_trigger_delay <= 48'd0;
        else
            uart_trigger_delay <= {uart_trigger_delay[46:0], trigger_1sec};
    end

    wire uart_send_pulse = uart_trigger_delay[47];

    reg [31:0] final_skr_latched;
    reg [31:0] n_sifted_latched;
    reg [31:0] n_error_latched;
    reg [9:0]  qber_latched;
    reg [5:0]  sw_latched;
    reg        system_valid;

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n)
            system_valid <= 1'b0;
        else if (uart_send_pulse)
            system_valid <= 1'b1;
    end

    localparam [31:0] MIN_SIFTED_SAFE = 32'd1000;

    assign alert_led =
        system_valid &&
        (
            (qber_latched > 10'd112) ||
            (final_skr_latched == 32'd0) ||
            (n_sifted_latched < MIN_SIFTED_SAFE)
        );

    // ============================================================
    // 6. UART PACKET 16 BYTE
    // ============================================================
    wire tx_busy;
    reg  tx_start;
    reg  [7:0] tx_data;

    uart_tx u_uart (
        .clk(clk_50mhz),
        .rst_n(rst_n),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx_busy(tx_busy),
        .txd(uart_txd)
    );

    reg [2:0] uart_state;
    reg [3:0] byte_index;
    reg [7:0] packet_byte;

    always @(*) begin
        case (byte_index)
            4'd0:  packet_byte = 8'hAA;

            4'd1:  packet_byte = final_skr_latched[31:24];
            4'd2:  packet_byte = final_skr_latched[23:16];
            4'd3:  packet_byte = final_skr_latched[15:8];
            4'd4:  packet_byte = final_skr_latched[7:0];

            4'd5:  packet_byte = {sw_latched[5:0], qber_latched[9:8]};
            4'd6:  packet_byte = qber_latched[7:0];

            4'd7:  packet_byte = n_sifted_latched[31:24];
            4'd8:  packet_byte = n_sifted_latched[23:16];
            4'd9:  packet_byte = n_sifted_latched[15:8];
            4'd10: packet_byte = n_sifted_latched[7:0];

            4'd11: packet_byte = n_error_latched[31:24];
            4'd12: packet_byte = n_error_latched[23:16];
            4'd13: packet_byte = n_error_latched[15:8];
            4'd14: packet_byte = n_error_latched[7:0];

            4'd15: packet_byte = 8'h55;

            default: packet_byte = 8'h00;
        endcase
    end

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n) begin
            uart_state        <= 3'd0;
            byte_index        <= 4'd0;
            tx_start          <= 1'b0;
            tx_data           <= 8'd0;

            final_skr_latched <= 32'd0;
            qber_latched      <= 10'd0;
            n_sifted_latched  <= 32'd0;
            n_error_latched   <= 32'd0;
            sw_latched        <= 6'd0;
        end else begin
            tx_start <= 1'b0;

            case (uart_state)
                3'd0: begin
                    if (uart_send_pulse) begin
                        final_skr_latched <= final_skr;
                        qber_latched      <= rom_skr_addr;
                        n_sifted_latched  <= n_sifted_snapshot;
                        n_error_latched   <= n_error_snapshot;
                        sw_latched        <= sw_snapshot;

                        byte_index <= 4'd0;
                        uart_state <= 3'd1;
                    end
                end

                3'd1: begin
                    if (!tx_busy) begin
                        tx_data    <= packet_byte;
                        uart_state <= 3'd2;
                    end
                end

                3'd2: begin
                    tx_start   <= 1'b1;
                    uart_state <= 3'd3;
                end

                3'd3: begin
                    if (tx_busy)
                        uart_state <= 3'd4;
                end

                3'd4: begin
                    if (!tx_busy)
                        uart_state <= 3'd5;
                end

                3'd5: begin
                    if (byte_index == 4'd15) begin
                        uart_state <= 3'd0;
                    end else begin
                        byte_index <= byte_index + 1'b1;
                        uart_state <= 3'd1;
                    end
                end

                default: begin
                    uart_state <= 3'd0;
                end
            endcase
        end
    end

endmodule