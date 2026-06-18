`timescale 1ns / 1ps

// ============================================================
// TESTBENCH: tb_top_qkd_receiver_key_frame
//
// Purpose:
//   - Simulate top_qkd_receiver.v
//   - Decode UART TXD
//   - Verify frame format:
//
//       0xAA
//       14 bytes metric payload
//       0xBB
//       2 bytes key payload length, little endian
//       key payload
//       0x55
//
// Important fix:
//   UART receiver must not wait too long after stop bit.
//   Otherwise it will miss the start bit of the next byte.
// ============================================================

module tb_top_qkd_receiver_key_frame;

    // ========================================================
    // Clock / UART settings
    // ========================================================

    localparam integer CLK_PERIOD_NS = 20;      // 50 MHz
    localparam integer BIT_TIME_NS   = 8680;    // 50MHz / 115200 = 434 clocks = 8680 ns

    reg clk_50mhz;
    reg rst_n;

    wire alert_led;
    wire uart_txd;

    // ========================================================
    // DUT
    // ========================================================

    top_qkd_receiver #(
        .WINDOW_TICKS  (2000),   // smaller value for faster simulation
        .ENV_MODE      (2),      // 0 Clear | 1 Coastal | 2 Turbid
        .TRNG_SIM_MODE (1)       // simulation mode
    ) dut (
        .clk_50mhz (clk_50mhz),
        .rst_n     (rst_n),
        .alert_led (alert_led),
        .uart_txd  (uart_txd)
    );

    // ========================================================
    // Clock generation
    // ========================================================

    initial begin
        clk_50mhz = 1'b0;
        forever #(CLK_PERIOD_NS / 2) clk_50mhz = ~clk_50mhz;
    end

    // ========================================================
    // Reset
    // ========================================================

    initial begin
        rst_n = 1'b0;

        repeat (20) @(posedge clk_50mhz);

        rst_n = 1'b1;

        $display("============================================================");
        $display("[TB] Reset released");
        $display("[TB] Waiting for UART frames...");
        $display("============================================================");
    end

    // ========================================================
    // Timeout protection
    // ========================================================

    initial begin
        #200_000_000; // 200 ms timeout

        $display("============================================================");
        $display("[TB][TIMEOUT] Simulation timeout reached.");
        $display("============================================================");

        $finish;
    end

    // ========================================================
    // UART byte receiver
    //
    // Correct sampling:
    //   t0        : falling edge of start bit
    //   t0+0.5T  : center of start bit
    //   t0+1.5T  : center of data bit 0
    //   ...
    //   t0+8.5T  : center of data bit 7
    //   t0+9.5T  : center of stop bit
    //
    // Return at t0+9.5T, so the task is ready before the next
    // byte start bit around t0+10T.
    // ========================================================

    task uart_read_byte;
        output [7:0] data;
        integer i;
        reg stop_bit;
        begin
            data = 8'd0;
            stop_bit = 1'b0;

            // Wait for start bit falling edge
            @(negedge uart_txd);

            // Move to the center of start bit
            #(BIT_TIME_NS / 2);

            if (uart_txd !== 1'b0) begin
                $display("[TB][WARN] False start bit detected at time %0t", $time);
            end

            // Sample data bits, LSB first
            for (i = 0; i < 8; i = i + 1) begin
                #(BIT_TIME_NS);
                data[i] = uart_txd;
            end

            // Sample stop bit at center
            #(BIT_TIME_NS);
            stop_bit = uart_txd;

            if (stop_bit !== 1'b1) begin
                $display("[TB][WARN] Stop bit is not high at time %0t", $time);
            end

            // Do NOT wait another full bit here.
            // Returning now prevents missing the next byte start bit.
        end
    endtask

    // ========================================================
    // Wait until 0xAA frame header appears
    // ========================================================

    task wait_for_header_aa;
        output [7:0] header;
        begin
            header = 8'd0;

            while (header != 8'hAA) begin
                uart_read_byte(header);
                $display("[TB][UART] RX byte = 0x%02X", header);
            end

            $display("------------------------------------------------------------");
            $display("[TB] Found frame header 0xAA");
            $display("------------------------------------------------------------");
        end
    endtask

    // ========================================================
    // Read and verify one complete frame
    // ========================================================

    task read_one_frame;
        integer i;
        integer key_len;
        integer print_limit;

        reg [7:0] header;
        reg [7:0] metric [0:13];
        reg [7:0] key_header;
        reg [7:0] len_lsb;
        reg [7:0] len_msb;
        reg [7:0] key_byte;
        reg [7:0] footer;

        reg [31:0] final_skr;
        reg [31:0] n_sifted;
        reg [31:0] n_error;
        reg [9:0]  qber_index;
        reg [5:0]  sw_index;

        real distance_m;
        real qber_percent;

        begin
            // ------------------------------------------------
            // 1. Wait for 0xAA
            // ------------------------------------------------
            wait_for_header_aa(header);

            // ------------------------------------------------
            // 2. Read 14-byte metric payload
            // ------------------------------------------------
            for (i = 0; i < 14; i = i + 1) begin
                uart_read_byte(metric[i]);
            end

            final_skr  = {metric[0], metric[1], metric[2], metric[3]};
            sw_index   = metric[4][7:2];
            qber_index = {metric[4][1:0], metric[5]};
            n_sifted   = {metric[6], metric[7], metric[8], metric[9]};
            n_error    = {metric[10], metric[11], metric[12], metric[13]};

            distance_m = 1.0 + sw_index * 0.1;
            qber_percent = qber_index * 100.0 / 1024.0;

            $display("[TB] Metric payload:");
            $display("     final_skr  = %0d", final_skr);
            $display("     sw_index   = %0d", sw_index);
            $display("     distance   = %0.1f m", distance_m);
            $display("     qber_index = %0d", qber_index);
            $display("     qber        = %0.2f %%", qber_percent);
            $display("     n_sifted   = %0d", n_sifted);
            $display("     n_error    = %0d", n_error);

            // ------------------------------------------------
            // 3. Read 0xBB key header
            // ------------------------------------------------
            uart_read_byte(key_header);

            if (key_header != 8'hBB) begin
                $display("[TB][ERROR] Expected key header 0xBB, got 0x%02X", key_header);
                $finish;
            end else begin
                $display("[TB] Found key header 0xBB");
            end

            // ------------------------------------------------
            // 4. Read key payload length
            // ------------------------------------------------
            uart_read_byte(len_lsb);
            uart_read_byte(len_msb);

            key_len = len_lsb | (len_msb << 8);

            $display("[TB] key_payload_length = %0d bytes", key_len);

            if (key_len > 512) begin
                $display("[TB][ERROR] key_len > 512. Invalid payload length.");
                $finish;
            end

            // ------------------------------------------------
            // 5. Read key payload bytes
            // ------------------------------------------------
            print_limit = key_len;

            if (print_limit > 16)
                print_limit = 16;

            $display("[TB] First key payload bytes:");

            for (i = 0; i < key_len; i = i + 1) begin
                uart_read_byte(key_byte);

                if (i < print_limit) begin
                    $display("     key[%0d] = 0x%02X", i, key_byte);
                end
            end

            if (key_len > 16) begin
                $display("     ... key payload truncated in transcript ...");
            end

            // ------------------------------------------------
            // 6. Read footer 0x55
            // ------------------------------------------------
            uart_read_byte(footer);

            if (footer != 8'h55) begin
                $display("[TB][ERROR] Expected footer 0x55, got 0x%02X", footer);
                $finish;
            end else begin
                $display("[TB] Footer 0x55 OK");
            end

            $display("------------------------------------------------------------");
            $display("[TB][PASS] One complete frame received successfully.");
            $display("------------------------------------------------------------");
        end
    endtask

    // ========================================================
    // Main simulation flow
    // ========================================================

    initial begin
        // Wait until reset is released
        @(posedge rst_n);

        // Give DUT some time to start
        repeat (100) @(posedge clk_50mhz);

        // Read several frames
        read_one_frame();
        read_one_frame();
        read_one_frame();

        $display("============================================================");
        $display("[TB][PASS] Testbench completed.");
        $display("============================================================");

        $finish;
    end

endmodule