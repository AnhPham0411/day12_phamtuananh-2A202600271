"""
Cost Guard — Bảo Vệ Budget LLM

Mục tiêu: Tránh bill bất ngờ từ LLM API.
- Đếm tokens đã dùng mỗi ngày
- Cảnh báo khi gần hết budget
- Block khi vượt budget

Trong production: lưu trong Redis/DB, không phải in-memory.
"""
import time
import logging
import os
from datetime import datetime
import redis
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Kết nối Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(REDIS_URL, decode_responses=True)

# Giá token (tham khảo, thay đổi theo model)
PRICE_PER_1K_INPUT_TOKENS = 0.00015   # GPT-4o-mini: $0.15/1M input
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006   # GPT-4o-mini: $0.60/1M output

class CostGuard:
    def __init__(
        self,
        monthly_budget_usd: float = 10.0,     # $10/tháng per user (theo yêu cầu Lab)
        warn_at_pct: float = 0.8,              # Cảnh báo khi dùng 80%
    ):
        self.monthly_budget_usd = monthly_budget_usd
        self.warn_at_pct = warn_at_pct

    def _get_month_key(self, user_id: str) -> str:
        """Tạo key Redis theo user và tháng hiện tại."""
        month_str = datetime.now().strftime("%Y-%m")
        return f"budget:{user_id}:{month_str}"

    def check_budget(self, user_id: str) -> None:
        """
        Kiểm tra budget từ Redis trước khi gọi LLM.
        Raise 402 nếu vượt budget.
        """
        key = self._get_month_key(user_id)
        current_spent = float(r.get(key) or 0.0)

        # Per-user monthly budget check
        if current_spent >= self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": round(current_spent, 4),
                    "budget_usd": self.monthly_budget_usd,
                    "resets_at": "next month",
                },
            )

        # Warning khi gần hết budget
        if current_spent >= self.monthly_budget_usd * self.warn_at_pct:
            logger.warning(
                f"User {user_id} at {current_spent/self.monthly_budget_usd*100:.0f}% monthly budget"
            )

    def record_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Ghi nhận usage vào Redis sau khi gọi LLM xong."""
        key = self._get_month_key(user_id)
        
        cost = (input_tokens / 1000 * PRICE_PER_1K_INPUT_TOKENS +
                output_tokens / 1000 * PRICE_PER_1K_OUTPUT_TOKENS)
        
        # Tăng giá trị đã tiêu trong Redis
        r.incrbyfloat(key, cost)
        # Set expire 40 ngày để tự dọn dẹp data cũ
        r.expire(key, 40 * 24 * 3600)

        new_total = float(r.get(key))
        logger.info(
            f"Usage: user={user_id} added=${cost:.6f} total=${new_total:.4f}/${self.monthly_budget_usd}"
        )
        return new_total

    def get_usage(self, user_id: str) -> dict:
        key = self._get_month_key(user_id)
        current_spent = float(r.get(key) or 0.0)
        
        return {
            "user_id": user_id,
            "month": datetime.now().strftime("%Y-%m"),
            "cost_usd": round(current_spent, 4),
            "budget_usd": self.monthly_budget_usd,
            "budget_remaining_usd": max(0, round(self.monthly_budget_usd - current_spent, 4)),
            "budget_used_pct": round(current_spent / self.monthly_budget_usd * 100, 1),
        }

# Singleton
cost_guard = CostGuard(monthly_budget_usd=10.0)
