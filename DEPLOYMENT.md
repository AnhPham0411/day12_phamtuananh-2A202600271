# Deployment Information

## Public URL
https://ai-agent-lab-2db2.onrender.com

## Platform
Render (Singapore)

## Test Commands

### Health Check
```bash
curl https://ai-agent-lab-2db2.onrender.com/health
# Expected: {"status": "ok"}
```

### API Test (with authentication)
```bash
curl -X POST https://ai-agent-lab-2db2.onrender.com/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### Rate Limiting Test
```bash
for i in {1..15}; do 
  curl -H "X-API-Key: YOUR_KEY" https://ai-agent-lab-2db2.onrender.com/ask \
    -X POST -d '{"question":"test"}'; 
done
# Should eventually return 429
```

## Environment Variables Set
- PORT: 8000
- REDIS_URL: redis://...
- AGENT_API_KEY: (Mật khẩu bảo mật)
- LOG_LEVEL: INFO

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
