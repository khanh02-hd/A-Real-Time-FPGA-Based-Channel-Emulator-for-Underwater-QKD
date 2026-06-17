import sys
import serial
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# ==========================================
# CẤU HÌNH THÔNG SỐ
# ==========================================
PORT = 'COM3'         # Sửa lại cổng COM cho đúng
BAUDRATE = 460800
FS = 8000             # 8kHz
WINDOW_SIZE = FS * 1  # Hiển thị đúng 1 giây âm thanh trên màn hình (8000 mẫu)

# Tạo mảng đệm trượt chứa dữ liệu vẽ (ban đầu toàn số 0)
data_buffer = np.zeros(WINDOW_SIZE)

# ==========================================
# KHỞI TẠO CỔNG COM (NON-BLOCKING)
# ==========================================
print(f"Đang kết nối STM32 qua {PORT}...")
try:
    # timeout=0 là bí quyết để Python không bị treo khi chờ dữ liệu
    ser = serial.Serial(PORT, BAUDRATE, timeout=0)
    ser.reset_input_buffer()
except Exception as e:
    print(f"Lỗi mở cổng COM: {e}")
    sys.exit()

# ==========================================
# KHỞI TẠO GIAO DIỆN PYQTGRAPH
# ==========================================
app = QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="STM32 Real-time Oscilloscope")
win.resize(1000, 600)

plot = win.addPlot(title="Dạng sóng âm thanh (Real-time - 8kHz)")
plot.setYRange(0, 4095)  # Dải ADC 12-bit
plot.showGrid(x=True, y=True, alpha=0.3)
plot.setLabel('left', 'Biên độ ADC')
plot.setLabel('bottom', 'Thời gian trượt (Mẫu)')

# Tạo đường vẽ màu xanh lá phản quang
curve = plot.plot(pen=pg.mkPen('g', width=1.5))

# ==========================================
# HÀM CẬP NHẬT DỮ LIỆU LIÊN TỤC
# ==========================================
def update_plot():
    global data_buffer
    
    # Kiểm tra xem có bao nhiêu byte đang nằm chờ ở cổng USB máy tính
    bytes_waiting = ser.in_waiting
    
    if bytes_waiting >= 2:
        # Chỉ đọc số byte chẵn (1 mẫu = 2 byte)
        bytes_to_read = bytes_waiting - (bytes_waiting % 2)
        raw_data = ser.read(bytes_to_read)
        
        # Giải mã mảng byte nhị phân thành số nguyên 16-bit
        new_samples = []
        for i in range(0, len(raw_data), 2):
            val = (raw_data[i] << 8) | raw_data[i+1]
            new_samples.append(val)
        
        num_new = len(new_samples)
        if num_new > 0:
            # Thuật toán cuốn chiếu (Sliding Window)
            # Xóa bớt data cũ ở đầu, đắp data mới vào cuối
            if num_new >= WINDOW_SIZE:
                data_buffer = np.array(new_samples[-WINDOW_SIZE:])
            else:
                data_buffer = np.roll(data_buffer, -num_new)
                data_buffer[-num_new:] = new_samples
            
            # Đổ dữ liệu mới vào biểu đồ
            curve.setData(data_buffer)

# ==========================================
# VÒNG LẶP THỜI GIAN THỰC
# ==========================================
# Dùng Timer của PyQt để gọi hàm update_plot mỗi 30ms (~33 FPS)
timer = QTimer()
timer.timeout.connect(update_plot)
timer.start(60)

print("Đang chạy Real-time! Hãy nói vào mic...")

if __name__ == '__main__':
    # Chạy vòng lặp giao diện
    sys.exit(app.exec_())