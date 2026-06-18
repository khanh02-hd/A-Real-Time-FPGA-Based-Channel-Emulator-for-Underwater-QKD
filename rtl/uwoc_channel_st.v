`timescale 1ns / 1ps

module uwoc_channel_st #(
    // -------------------------------------------------------------
    // Với clk = 50 MHz:
    //
    // UPDATE_DIV = 5000
    // update_rate = 50 MHz / 5000 = 10 kHz
    //
    // K_HO = 6:
    // hằng số thời gian xấp xỉ 2^6 / 10 kHz = 6.4 ms
    //
    // K_HS = 7:
    // hằng số thời gian xấp xỉ 2^7 / 10 kHz = 12.8 ms
    //
    // Lưu ý:
    // UPDATE_CNT_WIDTH phải đủ chứa UPDATE_DIV - 1.
    // Với UPDATE_DIV = 5000, cần 13 bit vì 2^13 = 8192.
    // Nếu đổi UPDATE_DIV lớn hơn, phải tăng UPDATE_CNT_WIDTH tương ứng.
    // -------------------------------------------------------------
    parameter integer UPDATE_DIV       = 5000,
    parameter integer UPDATE_CNT_WIDTH = 13,
    parameter integer K_HO             = 6,
    parameter integer K_HS             = 7
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire [15:0] data_ho,       // UQ4.12 sample from rom_ho
    input  wire [15:0] data_hs,       // UQ4.12 sample from rom_hs
    input  wire [31:0] L_s_const,     // Q0.32 path loss L(s)

    output wire [31:0] prob_click,    // Q0.32 probability
    output reg  [15:0] ho_state_dbg,  // UQ4.12 h_o(s,t)
    output reg  [15:0] hs_state_dbg,  // UQ4.12 h_s(s,t)
    output reg         channel_tick   // registered 1-clock tick
);

    // -------------------------------------------------------------
    // 1. Counter tạo tick cập nhật kênh
    // -------------------------------------------------------------
    reg [UPDATE_CNT_WIDTH-1:0] update_cnt;

    wire update_hit;
    assign update_hit = (update_cnt == UPDATE_DIV - 1);

    // -------------------------------------------------------------
    // 2. Tính hướng và bước cập nhật cho h_o
    //
    // h_o(t+1) = h_o(t) + sign(sample - state) * step
    // step = max(1, abs(sample - state) >> K_HO)
    //
    // Min-step = 1 giúp state không bị kẹt khi diff < 2^K.
    // -------------------------------------------------------------
    wire        ho_going_up;
    wire [15:0] diff_ho;
    wire [15:0] step_ho_raw;
    wire [15:0] step_ho;

    assign ho_going_up = (data_ho >= ho_state_dbg);

    assign diff_ho = ho_going_up ?
                     (data_ho - ho_state_dbg) :
                     (ho_state_dbg - data_ho);

    assign step_ho_raw = diff_ho >> K_HO;

    assign step_ho = ((diff_ho != 16'd0) && (step_ho_raw == 16'd0)) ?
                     16'd1 :
                     step_ho_raw;

    // -------------------------------------------------------------
    // 3. Tính hướng và bước cập nhật cho h_s
    //
    // h_s đổi chậm hơn h_o vì K_HS thường lớn hơn K_HO.
    // -------------------------------------------------------------
    wire        hs_going_up;
    wire [15:0] diff_hs;
    wire [15:0] step_hs_raw;
    wire [15:0] step_hs;

    assign hs_going_up = (data_hs >= hs_state_dbg);

    assign diff_hs = hs_going_up ?
                     (data_hs - hs_state_dbg) :
                     (hs_state_dbg - data_hs);

    assign step_hs_raw = diff_hs >> K_HS;

    assign step_hs = ((diff_hs != 16'd0) && (step_hs_raw == 16'd0)) ?
                     16'd1 :
                     step_hs_raw;

    // -------------------------------------------------------------
    // 4. Counter + cập nhật trạng thái kênh
    //
    // Reset về 1.0:
    // UQ4.12 => 1.0 = 4096
    //
    // channel_tick là reg, không phải so sánh tổ hợp trực tiếp.
    // Điều này tránh glitch khi dùng tick làm clock-enable/debug.
    // -------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            update_cnt   <= {UPDATE_CNT_WIDTH{1'b0}};
            channel_tick <= 1'b0;

            ho_state_dbg <= 16'd4096;
            hs_state_dbg <= 16'd4096;
        end else begin
            channel_tick <= 1'b0;

            if (update_hit) begin
                update_cnt   <= {UPDATE_CNT_WIDTH{1'b0}};
                channel_tick <= 1'b1;

                // Update h_o(s,t)
                if (ho_going_up)
                    ho_state_dbg <= ho_state_dbg + step_ho;
                else
                    ho_state_dbg <= ho_state_dbg - step_ho;

                // Update h_s(s,t)
                if (hs_going_up)
                    hs_state_dbg <= hs_state_dbg + step_hs;
                else
                    hs_state_dbg <= hs_state_dbg - step_hs;
            end else begin
                update_cnt <= update_cnt + 1'b1;
            end
        end
    end

    // -------------------------------------------------------------
    // 5. h_total(s,t) = h_o(s,t) * h_s(s,t)
    //
    // h_o, h_s: UQ4.12
    //
    // Tích:
    // UQ4.12 * UQ4.12 = UQ8.24
    //
    // Sau khi lấy [31:12]:
    // h_total có 12 fractional bits.
    //
    // h_mult_full tối đa:
    // 0xFFFF * 0xFFFF = 0xFFFE0001
    // vừa đủ 32 bit, nên không cần 64 bit ở đây.
    // -------------------------------------------------------------
    wire [31:0] h_mult_full;
    wire [19:0] h_total;

    assign h_mult_full = {16'd0, ho_state_dbg} * {16'd0, hs_state_dbg};

    // h_total = h_mult_full >> 12, giữ 20 bit có nghĩa.
    assign h_total = h_mult_full[31:12];

    // -------------------------------------------------------------
    // 6. prob_click(s,t) = L(s) * h_o(s,t) * h_s(s,t)
    //
    // h_total   : fixed-point có 12 fractional bits
    // L_s_const : Q0.32
    //
    // prob_full = h_total * L_s_const
    // prob_shifted = prob_full >> 12
    //
    // Kết quả mong muốn: Q0.32.
    //
    // Lưu ý:
    // Nếu h_o và h_s quá lớn, h_total có thể > 1.0.
    // Khi đó prob_click có thể vượt 1.0 nên cần saturation.
    // -------------------------------------------------------------
    wire [63:0] prob_full;
    wire [63:0] prob_shifted;

    assign prob_full = {44'd0, h_total} * {32'd0, L_s_const};

    assign prob_shifted = prob_full >> 12;

    assign prob_click = (prob_shifted > 64'h0000_0000_FFFF_FFFF) ?
                        32'hFFFF_FFFF :
                        prob_shifted[31:0];

endmodule 