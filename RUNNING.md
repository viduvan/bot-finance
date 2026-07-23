# Hướng Dẫn Khởi Chạy Hệ Thống ACTA Từ Đầu

Tài liệu này hướng dẫn chi tiết cách khởi chạy toàn bộ hệ thống cố vấn giao dịch crypto đa tác nhân ACTA khi mở máy lên.

---

## ⚡ Cách 1: Chạy Tự Động 1-Click (Khuyên Dùng)

Đã tạo sẵn file kịch bản tự động `start.sh` và `stop.sh` tại thư mục gốc dự án.

### 🚀 Khởi chạy hệ thống:
Mở Terminal tại thư mục `bot-finance` và chạy:
```bash
./start.sh
```
*Script sẽ tự động khởi động lần lượt: Docker Containers → Ollama LLM → Backend FastAPI → Frontend React.*

### 🛑 Tắt toàn bộ hệ thống:
```bash
./stop.sh
```

---

## 🛠️ Cách 2: Chạy Thủ Công Từng Bước (Manual)

Nếu bạn muốn mở từng Terminal riêng biệt để dễ theo dõi log sống:

### 📍 Bước 1: Khởi động Hạ tầng Docker (Database, Redis, Monitoring)
```bash
cd /home/vietpv/Desktop/bot-finance
docker compose up -d postgres redis prometheus grafana
```
*Kiểm tra trạng thái:* `docker compose ps`

---

### 📍 Bước 2: Khởi động Ollama Server (Model LLM Local)
```bash
OLLAMA_MODELS=/usr/share/ollama/.ollama/models ollama serve
```
*Kiểm tra model sẵn sàng:* mở terminal khác gõ `ollama list` (thấy `qwen3:14b`).

---

### 📍 Bước 3: Khởi động Backend FastAPI Server
Mở Terminal mới:
```bash
cd /home/vietpv/Desktop/bot-finance/apps/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Docs (Swagger UI): http://localhost:8000/api/docs
- Health check: http://localhost:8000/api/v1/system/health

---

### 📍 Bước 4: Khởi động Frontend React Web App
Mở Terminal mới:
```bash
cd /home/vietpv/Desktop/bot-finance/apps/frontend
npm run dev -- --host 0.0.0.0
```
- Dashboard Giao Diện: http://localhost:5173

---

## 📌 Các Địa Chỉ & Cổng Dịch Vụ Sau Khi Chạy

| Dịch vụ | Địa chỉ URL | Thông tin đăng nhập / Ghi chú |
|---|---|---|
| **Frontend UI** | [http://localhost:5173](http://localhost:5173) | Đăng nhập tài khoản admin bên dưới |
| **Backend API Docs** | [http://localhost:8000/api/docs](http://localhost:8000/api/docs) | Giao diện Swagger UI test API |
| **Grafana Monitoring** | [http://localhost:3001](http://localhost:3001) | User: `admin` / Password: `acta_grafana` |
| **Prometheus Metrics** | [http://localhost:9090](http://localhost:9090) | Môi trường giám sát chỉ số hệ thống |
| **Ollama LLM Server** | [http://localhost:11434](http://localhost:11434) | Phục vụ model `qwen3:14b` |

---

## 🔐 Tài Khoản Admin Đã Khởi Tạo

- **Email**: `admin@acta.io`
- **Password**: `AdminPass123456!@`

---

## 🔍 Xem Logs Khi Dùng Auto Script (`./start.sh`)

- Log Backend: `tail -f /tmp/acta_backend.log`
- Log Frontend: `tail -f /tmp/acta_frontend.log`
- Log Ollama: `tail -f /tmp/ollama.log`
