`timescale 1ns / 1ps

module skr_evaluator (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        trigger_1sec,
    input  wire [31:0] n_sifted,
    input  wire [31:0] n_error,

    output wire [9:0]  rom_skr_addr,
    input  wire [15:0] rom_skr_data,

    output reg  [31:0] final_skr
);

    // -------------------------------------------------------------
    // 1. Latch data of each measurement window
    // -------------------------------------------------------------

    reg [31:0] latched_sifted;
    reg [31:0] latched_error;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            latched_sifted <= 32'd0;
            latched_error  <= 32'd0;
        end else if (trigger_1sec) begin
            latched_sifted <= n_sifted;
            latched_error  <= n_error;
        end
    end

    // -------------------------------------------------------------
    // 2. Delay trigger by 1 clock
    //
    // At trigger_1sec, latched_sifted/latched_error are updated.
    // The divider should start using the new data from the next clock.
    // -------------------------------------------------------------

    reg trigger_d1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            trigger_d1 <= 1'b0;
        else
            trigger_d1 <= trigger_1sec;
    end

    // -------------------------------------------------------------
    // 3. QBER numerator / denominator
    //
    // qber_index = round(n_error * 1024 / n_sifted)
    //
    // numerator = n_error * 1024 + n_sifted / 2
    // denominator = n_sifted
    // -------------------------------------------------------------

    wire [63:0] qber_numerator;
    wire [31:0] qber_denominator;

    assign qber_numerator =
        ({32'd0, latched_error} << 10) + {32'd0, (latched_sifted >> 1)};

    assign qber_denominator =
        (latched_sifted != 32'd0) ? latched_sifted : 32'd1;

    // -------------------------------------------------------------
    // 4. Pipelined Altera LPM divider
    //
    // IMPORTANT:
    // ModelSim/Altera lpm_divide expects the aclr port.
    // Without .aclr(~rst_n), ModelSim gives:
    //   Too few port connections
    //   Missing connection for port 'aclr'
    // -------------------------------------------------------------

    wire [63:0] qber_div_full;

    lpm_divide #(
        .lpm_widthn          (64),
        .lpm_widthd          (32),
        .lpm_nrepresentation ("UNSIGNED"),
        .lpm_drepresentation ("UNSIGNED"),
        .lpm_pipeline        (32)
    ) pipelined_divider (
        .numer     (qber_numerator),
        .denom     (qber_denominator),
        .clock     (clk),
        .clken     (1'b1),
        .aclr      (~rst_n),
        .quotient  (qber_div_full),
        .remain    ()
    );

    // -------------------------------------------------------------
    // 5. Valid pipeline
    //
    // lpm_divide has lpm_pipeline = 32.
    // div_done is asserted when qber_div_full is valid.
    // skr_calc is delayed slightly more to allow ROM data to settle.
    // -------------------------------------------------------------

    reg [36:0] valid_shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            valid_shift <= 37'd0;
        else
            valid_shift <= {valid_shift[35:0], trigger_d1};
    end

    wire div_done;
    wire skr_calc;

    assign div_done = valid_shift[32];
    assign skr_calc = valid_shift[35];

    // -------------------------------------------------------------
    // 6. QBER index for SKR ROM
    //
    // qber_index is limited to 0..1023.
    // qber_index = 1023 means very bad channel / outage.
    // -------------------------------------------------------------

    reg [9:0] qber_index;

    assign rom_skr_addr = qber_index;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            qber_index <= 10'd0;
        end else if (div_done) begin
            if (latched_sifted == 32'd0)
                qber_index <= 10'd1023;
            else if (qber_div_full > 64'd1023)
                qber_index <= 10'd1023;
            else
                qber_index <= qber_div_full[9:0];
        end
    end

    // -------------------------------------------------------------
    // 7. Calculate final SKR
    //
    // final_skr = latched_sifted * rom_skr_data / 4096
    //
    // rom_skr_data is UQ4.12:
    //   4096 means penalty = 1.0
    //   0 means no secure key
    // -------------------------------------------------------------

    wire [63:0] skr_mult_full;

    assign skr_mult_full =
        {32'd0, latched_sifted} * {48'd0, rom_skr_data};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            final_skr <= 32'd0;
        end else if (skr_calc) begin
            if (latched_sifted == 32'd0)
                final_skr <= 32'd0;
            else
                final_skr <= skr_mult_full[43:12];
        end
    end

endmodule