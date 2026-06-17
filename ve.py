import serial
import matplotlib.pyplot as plt
import time

# ==========================================
# CẤU HÌNH THÔNG SỐ (Khớp 100% với STM32)
# ==========================================
PORT = 'COM3'         # Thay bằng cổng COM thực tế của bạn
BAUDRATE = 460800     # Tốc độ truyền (khớp với BRR = 17)
FS = 8000             # Tần số lấy mẫu (8kHz từ TIM3)
RECORD_TIME = 2       # Ghi âm trong 2 giây
NUM_SAMPLES = FS * RECORD_TIME # Tổng số mẫu cần lấy (16000 mẫu)

data = []

# ==========================================
# 1. ĐỌC DỮ LIỆU TỪ CỔNG COM
# ==========================================
print(f"Đang kết nối STM32 qua cổng {PORT} ở tốc độ {BAUDRATE} baud...")
try:
    ser = serial.Serial(PORT, BAUDRATE)
    
    # Xóa sạch bộ đệm rác trước khi bắt đầu đọc
    ser.reset_input_buffer() 
    
    print(f"\n[>>>] BẮT ĐẦU GHI ÂM! Hãy nói vào Micro trong {RECORD_TIME} giây...")
    
    while len(data) < NUM_SAMPLES:
        # Đọc 2 byte nhị phân mỗi lần (1 mẫu ADC = 2 byte)
        raw_bytes = ser.read(2) 
        if len(raw_bytes) == 2:
            # Ghép Byte cao và Byte thấp lại thành số nguyên 16-bit
            val = (raw_bytes[0] << 8) | raw_bytes[1]
            data.append(val)
            
    print("[V] ĐÃ LẤY ĐỦ DỮ LIỆU! Đang đóng cổng COM...")
    ser.close()
    
except Exception as e:
    print(f"Lỗi cổng COM: {e}")
    print("Vui lòng kiểm tra lại dây cắm hoặc xem cổng COM đã đúng chưa.")
    exit()

# ==========================================
# 2. XUẤT DỮ LIỆU RA FILE TEXT (MEMORY)
# ==========================================
filename = 'adc_data_log.txt'
print(f"Đang lưu dữ liệu ra file {filename}...")

with open(filename, 'w') as f:
    for val in data:
        f.write(f"{val}\n")
        
print("Lưu file thành công!")

# ==========================================
# 3. VẼ ĐỒ THỊ (PLOT)
# ==========================================
print("Đang khởi tạo đồ thị...")

# Tạo trục thời gian thực tế (Tính bằng giây)
# Ví dụ: mẫu thứ 8000 sẽ nằm ở giây thứ 1.0
time_axis = [i / FS for i in range(len(data))]

plt.figure(figsize=(12, 5))
plt.plot(time_axis, data, color='royalblue', linewidth=0.5)

# Trình bày đồ thị chuẩn kỹ thuật
plt.title(f"Dạng sóng Âm thanh thu từ STM32 DMA ({FS} Hz)", fontsize=14, fontweight='bold')
plt.xlabel("Thời gian (Giây)", fontsize=11)
plt.ylabel("Giá trị ADC (0 - 4095)", fontsize=11)
plt.ylim(0, 4150) # Giới hạn trục Y vừa vặn với độ phân giải 12-bit
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()

# Hiển thị biểu đồ
plt.show()