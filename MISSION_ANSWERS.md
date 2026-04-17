# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. **Hardcoded Secrets:** API keys và Database URL được viết trực tiếp trong code (lines 17-18).
2. **Thiếu Config Management:** Các tham số như DEBUG, MAX_TOKENS được gán cứng, không linh hoạt theo môi trường.
3. **Sử dụng print():** Dùng print() để log thông tin thay vì dùng thư viện logging chuyên dụng.
4. **Lộ thông tin nhạy cảm:** Log cả API Key ra console (line 34).
5. **Cấu hình mạng cứng (Hardcoded Network):** Chạy trên `localhost` và port `8000`, khiến app không thể chạy trên các cloud platform (thường dùng port 0.0.0.0 và dynamic port).
6. **Reload mode:** Bật `reload=True` trong production gây tốn tài nguyên và bảo mật.
7. **Thiếu Health Check:** Không có endpoint để hệ thống giám sát kiểm tra trạng thái app.
8. **Thiếu Graceful Shutdown:** Không xử lý ngắt kết nối an toàn khi server bị tắt.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config  | Hardcode | Env vars / .env | Bảo mật và linh hoạt giữa các môi trường |
| Health check | Không có | Có (/health) | Giúp platform tự động restart khi app crash |
| Logging | print() | JSON Logging | Dễ dàng parse và quản lý log tập trung |
| Shutdown | Đột ngột | Graceful | Đảm bảo requests đang chạy được hoàn thành và đóng kết nối an toàn |
| Host/Port | Localhost:8000 | 0.0.0.0:${PORT} | Cho phép app nhận traffic từ bên ngoài (Internet/Cloud) |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** `python:3.11` (Full distribution, ~1GB).
2. **Working directory:** `/app`.
3. **Tại sao COPY requirements.txt trước?** Để tận dụng **Docker Layer Cache**. Khi code thay đổi nhưng `requirements.txt` không đổi, Docker sẽ sử dụng lại layer đã install dependencies, giúp build nhanh hơn rất nhiều.
4. **CMD vs ENTRYPOINT:** `ENTRYPOINT` quy định executable chính không đổi của container, còn `CMD` cung cấp các tham số mặc định và có thể bị ghi đè dễ dàng khi dùng `docker run`.

### Exercise 2.3: Image size comparison
- Develop: 1.15 GB
- Production: 160 MB
- Difference: ~86%

### Part 3: Cloud Deployment

### Exercise 3.1: Deployment Info
- **Public URL**: https://ai-agent-lab-2db2.onrender.com
- **Platform**: Render (Singapore)
- **Status**: Deployment successful with healthy Liveness/Readiness probes.

### Exercise 3.2: Comparison of render.yaml vs railway.toml
- **railway.toml**: Chú trọng tính tối giản, dễ cấu hình nhanh qua CLI. Phù hợp cho các service đơn lẻ hoặc deploy nhanh.
- **render.yaml**: Là "Infrastructure as Code" thực thụ, cho phép quản lý toàn bộ hệ sinh thái (Web, Redis, Postgres) trong một file duy nhất. Dễ dàng tái sử dụng và quản lý version.

### Part 4: API Security

#### Exercise 4.1: API Key authentication
- **API key được check ở đâu?**: Được kiểm tra trong hàm `verify_api_key`, hàm này được tiêm (inject) vào endpoint `/ask` thông qua `Depends`.
- **Điều gì xảy ra nếu sai key?**: Hệ thống sẽ trả về lỗi `403 Forbidden` với nội dung "Invalid API key." (Nếu thiếu key sẽ trả về `401 Unauthorized`).
- **Làm sao rotate key?**: Thay đổi giá trị của biến môi trường `AGENT_API_KEY` mà không cần sửa code.

- **Test result (401 - Missing key)**:
```json
{ "detail": "Invalid or missing API key. Include header: X-API-Key: <key>" }
```
- **Test result (200 - Correct key)**:
```json
{
  "question": "Hello",
  "answer": "Hello! I am your AI agent. How can I help you today?",
  "session_id": "default",
  "cost_usd": 0.0003,
  "timestamp": "2026-04-17T09:30:00Z"
}
```
- **Test result (429 - Rate Limit Exceeded)**:
```json
{
  "detail": "Rate limit exceeded: 20 req/min",
  "retry_after": "60"
}
```
#### Exercise 4.2: JWT authentication
- **JWT flow**: Client gửi username/password để lấy token -> Server trả về JWT. Các request sau đó Client gửi token này trong header `Authorization: Bearer <token>`. Server chỉ cần verify chữ ký (signature) để lấy thông tin user mà không cần truy vấn database.

#### Exercise 4.3: Rate limiting
- **Algorithm**: Sliding Window Counter (dùng `deque` để lưu timestamps).
- **Limit**: 10 requests/phút đối với User thường, 100 requests/phút đối với Admin.
- **Bypass for admin**: Sử dụng một instance `RateLimiter` riêng (`rate_limiter_admin`) với cấu hình cao hơn hoặc kiểm tra role của user trước khi áp dụng limiter.

#### Exercise 4.4: Cost Guard Implementation
- **Logic**: 
  - Mỗi user có budget $10/tháng.
  - Sử dụng Redis làm storage để đảm bảo tính Stateless (không mất dữ liệu khi restart container).
### Part 5: Scaling & Reliability

#### Exercise 5.1: Health & Readiness checks
- **Liveness probe (/health)**: Giúp hệ thống biết container còn sống hay không. Nếu endpoint này trả về lỗi liên tục, platform sẽ tự động restart container.
- **Readiness probe (/ready)**: Giúp Load Balancer biết instance này đã sẵn sàng nhận traffic chưa (đã kết nối Redis, DB xong chưa). Nếu chưa, nó sẽ tạm ngừng gửi request tới instance này.

#### Exercise 5.2: Graceful Shutdown
- **Tại sao quan trọng?**: Giúp đảm bảo các request đang xử lý (như đang chờ LLM trả lời) không bị ngắt quãng đột ngột khi container bị tắt/update. Server sẽ đợi cho đến khi xử lý xong các "in-flight requests" rồi mới thực sự tắt hẳn.

#### Exercise 5.3: Stateless Design
- **Tại sao stateless quan trọng khi scale?**: Trong hệ thống có nhiều instance (scale out), một user có thể được phục vụ bởi bất kỳ instance nào. Nếu lưu session trong memory instance A, khi user được điều hướng sang instance B, dữ liệu sẽ bị mất. Lưu session vào Redis giúp mọi instance đều truy cập được dữ liệu chung.
- **Kết quả test stateless**:
```text
Request 1: [instance-a] Q: What is Docker?
Request 2: [instance-b] Q: Why do we need containers?
...
✅ Session history preserved across all instances via Redis!
```

### Part 6: Final Project - Production AI Agent

Dự án đã được hoàn thiện với các tiêu chuẩn sau:
1. **Stateless Architecture**: Chuyển toàn bộ Rate Limit, Cost Guard và Lịch sử hội thoại vào Redis.
2. **Security**: Xác thực qua API Key, giới hạn truy cập theo Sliding Window và bảo vệ ngân sách theo tháng.
3. **Observability**: Hệ thống logging dưới dạng JSON structured, giúp dễ dàng tích hợp với CloudWatch/ELK.
4. **Reliability**:
   - Health check tự động restart container nếu lỗi.
   - Graceful shutdown đảm bảo không mất request khách hàng.
   - Multi-stage Dockerfile giúp image nhỏ gọn (< 300MB) và bảo mật (non-root user).

**Kết luận**: Agent đã sẵn sàng để triển khai thực tế trên các nền tảng Cloud như Render, Railway hoặc Kubernetes.
