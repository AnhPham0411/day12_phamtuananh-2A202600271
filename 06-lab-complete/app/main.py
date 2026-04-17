"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting
  ✅ Cost guard
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""
import os
import time
import signal
import logging
import json
import redis
from datetime import datetime, timezone
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings

# Mock LLM (thay bằng OpenAI/Anthropic khi có API key)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# Redis connection
r = redis.from_url(settings.redis_url, decode_responses=True)

# ─────────────────────────────────────────────────────────
# Redis-based Rate Limiter (Sliding Window)
# ─────────────────────────────────────────────────────────
def check_rate_limit(key: str):
    now = time.time()
    redis_key = f"rl:{key}"
    
    # Sử dụng transaction (pipeline) để đảm bảo atomic
    with r.pipeline() as pipe:
        # Xóa các timestamps cũ hơn 60s
        pipe.zremrangebyscore(redis_key, 0, now - 60)
        # Đếm số request hiện tại
        pipe.zcard(redis_key)
        # Thêm timestamp mới
        pipe.zadd(redis_key, {str(now): now})
        # Set expire để tự cleanup
        pipe.expire(redis_key, 60)
        
        _, count, _, _ = pipe.execute()
        
    if count >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min",
            headers={"Retry-After": "60"},
        )

# ─────────────────────────────────────────────────────────
# Redis-based Cost Guard (Monthly)
# ─────────────────────────────────────────────────────────
def check_and_record_cost(user_id: str, input_tokens: int, output_tokens: int):
    month_str = datetime.now().strftime("%Y-%m")
    redis_key = f"cost:{user_id}:{month_str}"
    
    current_spent = float(r.get(redis_key) or 0.0)
    
    if current_spent >= settings.daily_budget_usd: # Dùng budget từ settings
        raise HTTPException(503, "Budget exhausted. Try again next month.")
    
    cost = (input_tokens / 1000) * 0.00015 + (output_tokens / 1000) * 0.0006
    r.incrbyfloat(redis_key, cost)
    r.expire(redis_key, 40 * 24 * 3600) # 40 days TTL
    return current_spent + cost

# ─────────────────────────────────────────────────────────
# Redis-based Chat History
# ─────────────────────────────────────────────────────────
def get_chat_history(session_id: str, limit: int = 10):
    redis_key = f"hist:{session_id}"
    history = r.lrange(redis_key, -limit*2, -1)
    return [json.loads(m) for m in history]

def append_chat_history(session_id: str, role: str, content: str):
    redis_key = f"hist:{session_id}"
    msg = json.dumps({"role": role, "content": content, "ts": time.time()})
    r.rpush(redis_key, msg)
    r.ltrim(redis_key, -20, -1) # Giữ tối đa 20 messages
    r.expire(redis_key, 3600 * 24) # 24h TTL

# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    try:
        r.ping()
        logger.info(json.dumps({"event": "redis_connected"}))
    except Exception as e:
        logger.error(json.dumps({"event": "redis_failed", "error": str(e)}))
        
    _is_ready = True
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers.pop("server", None)
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        logger.error(json.dumps({"event": "error", "path": request.url.path, "err": str(e)}))
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: "default")

class AskResponse(BaseModel):
    question: str
    answer: str
    session_id: str
    cost_usd: float
    timestamp: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "online" if _is_ready else "starting",
        "storage": "Redis",
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    # 1. Rate limit (Redis-based)
    check_rate_limit(_key[:8])

    # 2. Budget check (Redis-based)
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(_key[:8], input_tokens, 0)

    # 3. Get history (Redis-based)
    history = get_chat_history(body.session_id)
    
    # 4. Call LLM (mock)
    answer = llm_ask(body.question)

    # 5. Record usage & history
    output_tokens = len(answer.split()) * 2
    total_spent = check_and_record_cost(_key[:8], 0, output_tokens)
    append_chat_history(body.session_id, "user", body.question)
    append_chat_history(body.session_id, "assistant", answer)

    return AskResponse(
        question=body.question,
        answer=answer,
        session_id=body.session_id,
        cost_usd=round(total_spent, 6),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health")
def health():
    return {"status": "ok", "uptime": round(time.time() - START_TIME, 1)}


@app.get("/ready")
def ready():
    if not _is_ready: raise HTTPException(503)
    try:
        r.ping()
        return {"ready": True}
    except:
        raise HTTPException(503, "Redis unavailable")

# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum, "msg": "Graceful shutdown signal received"}))

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
