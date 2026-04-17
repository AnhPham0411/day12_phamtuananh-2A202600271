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

### Exercise 3.2: Comparison of render.yaml vs railway.toml
- **railway.toml**: Chú trọng tính tối giản, dễ cấu hình nhanh qua CLI. Phù hợp cho các service đơn lẻ hoặc deploy nhanh.
- **render.yaml**: Là "Infrastructure as Code" thực thụ, cho phép quản lý toàn bộ hệ sinh thái (Web, Redis, Postgres) trong một file duy nhất. Dễ dàng tái sử dụng và quản lý version.

### Exercise 3.1: Deployment URL
- Public URL: [Sẽ cập nhật sau khi deploy]
