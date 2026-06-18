`timescale 1ns / 1ps

module tb_top_qkd_receiver();

    // ============================================================
    // 1. KHAI BÁO TÍN HIỆU
    // ============================================================
    reg clk_50mhz;
    reg rst_n;

    wire alert_led;
    wire uart_txd;

    // 2 ms/window tại clock 50 MHz
    localparam SIM_WINDOW_TICKS = 100_000;
    localparam [63:0] SCALE_TO_1SEC = 64'd50_000_000 / SIM_WINDOW_TICKS;

    // Chọn môi trường mô phỏng:
    // 0: Clear Water
    // 1: Coastal Water
    // 2: Turbid Harbor
    localparam TB_ENV_MODE = 1;

    // Mỗi khoảng cách chỉ in 2 mẫu
    localparam integer SAMPLES_PER_DISTANCE = 2;

    // ============================================================
    // 2. KHỞI TẠO MODULE DUT
    // ============================================================
    top_qkd_receiver #(
        .WINDOW_TICKS(SIM_WINDOW_TICKS),
        .ENV_MODE(TB_ENV_MODE)
    ) uut (
        .clk_50mhz(clk_50mhz),
        .rst_n(rst_n),
        .alert_led(alert_led),
        .uart_txd(uart_txd)
    );

    // ============================================================
    // 3. TẠO CLOCK 50 MHz
    // ============================================================
    initial begin
        clk_50mhz = 1'b0;
        forever #10 clk_50mhz = ~clk_50mhz;
    end

    // ============================================================
    // 4. BIẾN PHỤ CHO TESTBENCH
    // ============================================================
    real qber_pc_pct;
    real qber_fpga_pct;

    reg [63:0] sifted_1sec;
    reg [63:0] error_1sec;
    reg [63:0] skr_1sec;

    reg [5:0] current_sw;
    integer sample_count;
    integer total_print_count;
    reg done;

    // ============================================================
    // 5. KỊCH BẢN MÔ PHỎNG
    // ============================================================
    initial begin
        rst_n = 1'b0;
        current_sw = 6'd63;
        sample_count = 0;
        total_print_count = 0;
        done = 1'b0;

        #100;
        rst_n = 1'b1;

        $display("[%0t] HET RESET, BAT DAU MO PHONG AUTO-SWEEP", $time);
        $display("ENV_MODE = %0d | Moi khoang cach in %0d mau hop le", TB_ENV_MODE, SAMPLES_PER_DISTANCE);
        $display("Auto-sweep: 1.0m -> 7.0m, step 0.1m");
        $display("------------------------------------------------------------");

        wait(done == 1'b1);

        $display("\n[%0t] HOAN THANH MO PHONG 1.0m -> 7.0m", $time);
        $display("Tong so mau da in = %0d", total_print_count);
        $stop;
    end

    // ============================================================
    // 6. IN KẾT QUẢ RA CONSOLE
    // ============================================================
    always @(posedge uut.uart_send_pulse) begin
        #1;

        // Bỏ packet đầu/pipeline chưa có dữ liệu
        if (uut.n_sifted_latched == 32'd0) begin
            // Không in packet rỗng
        end else begin

            // Nếu sang khoảng cách mới thì reset bộ đếm mẫu
            if (uut.sw_latched != current_sw) begin
                current_sw = uut.sw_latched;
                sample_count = 0;

                $display("");
                $display("============================================================");
                $display("BAT DAU KHOANG CACH: SW=%0d  <=>  %0.1f m",
                         uut.sw_latched, 1.0 + uut.sw_latched * 0.1);
                $display("============================================================");
            end

            // Chỉ in tối đa 2 mẫu mỗi khoảng cách
            if (sample_count < SAMPLES_PER_DISTANCE) begin

                sample_count = sample_count + 1;
                total_print_count = total_print_count + 1;

                if (uut.n_sifted_latched != 0)
                    qber_pc_pct = (100.0 * uut.n_error_latched) / uut.n_sifted_latched;
                else
                    qber_pc_pct = 0.0;

                qber_fpga_pct = (100.0 * uut.qber_latched) / 1024.0;

                sifted_1sec = {32'd0, uut.n_sifted_latched} * SCALE_TO_1SEC;
                error_1sec  = {32'd0, uut.n_error_latched}  * SCALE_TO_1SEC;
                skr_1sec    = {32'd0, uut.final_skr_latched} * SCALE_TO_1SEC;

                $display("------------------------------------------------------------");
                $display("[%0t] FPGA AUTO-SWEEP REPORT", $time);
                $display("Distance         = %0.1f m", 1.0 + uut.sw_latched * 0.1);
                $display("SW_latched       = %0d", uut.sw_latched);
                $display("Sample           = %0d / %0d", sample_count, SAMPLES_PER_DISTANCE);
                $display("ENV_MODE         = %0d", TB_ENV_MODE);
                $display("bg_thresh_32     = %0d", uut.bg_thresh_32);
                $display("L_s_const        = %0d", uut.L_s_const);

                $display("n_sifted raw     = %0d", uut.n_sifted_latched);
                $display("n_sifted 1s      = %0d", sifted_1sec);

                $display("n_error raw      = %0d", uut.n_error_latched);
                $display("n_error 1s       = %0d", error_1sec);

                $display("QBER_FPGA        = %0.2f %%", qber_fpga_pct);
                $display("QBER_PC          = %0.2f %%", qber_pc_pct);

                $display("final_skr raw    = %0d", uut.final_skr_latched);
                $display("final_skr 1s     = %0d bps", skr_1sec);

                if (uut.alert_led)
                    $display("STATUS           = ALERT / OUTAGE (LED ON)");
                else
                    $display("STATUS           = SAFE (LED OFF)");

                $display("------------------------------------------------------------");
            end

            // Dừng khi đã tới 7.0m và đã in đủ 2 mẫu
            if ((uut.sw_latched == 6'd60) && (sample_count >= SAMPLES_PER_DISTANCE)) begin
                done = 1'b1;
            end
        end
    end

endmodule 