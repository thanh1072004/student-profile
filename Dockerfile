# Sử dụng ảnh cơ sở Python dung lượng nhẹ
FROM python:3.10-slim

# Thiết lập thư mục làm việc bên trong vùng chứa
WORKDIR /app

# Sao chép tệp cấu hình và cài đặt thư viện (Tận dụng bộ nhớ đệm lớp)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào vùng chứa
COPY . .

# Khai báo cổng giao tiếp
EXPOSE 5000

# Lệnh thực thi khởi động Web Server
CMD ["python", "app.py"]
