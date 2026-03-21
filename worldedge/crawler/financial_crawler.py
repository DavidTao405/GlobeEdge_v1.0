"""金融資料爬蟲 — LLM 輔助文件理解，抽取信念向量。

⚠️ 內建硬性成本上限：
  - 每次排程最多 MAX_LLM_CALLS_PER_RUN 次 API 呼叫
  - 月預算硬限制 MONTHLY_BUDGET_USD
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 成本防護 ─────────────────────────────────────────────
MAX_LLM_CALLS_PER_RUN = 20      # 每次排程最多呼叫 20 次
MONTHLY_BUDGET_USD = 10.0        # 月預算硬限制

# 用檔案追蹤月度花費（避免 DB 依賴）
_COST_LOG_PATH = Path(os.environ.get(
    "WE_COST_LOG", Path(__file__).parent.parent.parent / "data" / "llm_cost.json"
))


def _load_monthly_cost() -> float:
    """讀取本月已累計的 LLM 費用（USD）。"""
    try:
        if not _COST_LOG_PATH.exists():
            return 0.0
        data = json.loads(_COST_LOG_PATH.read_text(encoding="utf-8"))
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        return data.get(current_month, 0.0)
    except Exception:
        logger.exception("failed to load cost log")
        return 0.0


def _record_cost(cost_usd: float) -> None:
    """記錄單次 LLM 呼叫費用。"""
    try:
        _COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if _COST_LOG_PATH.exists():
            data = json.loads(_COST_LOG_PATH.read_text(encoding="utf-8"))
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        data[current_month] = data.get(current_month, 0.0) + cost_usd
        _COST_LOG_PATH.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except Exception:
        logger.exception("failed to record cost")


def _check_budget() -> bool:
    """檢查是否還有預算。回傳 True = 可以呼叫。"""
    spent = _load_monthly_cost()
    if spent >= MONTHLY_BUDGET_USD:
        logger.warning(
            "monthly LLM budget exceeded: $%.2f / $%.2f",
            spent, MONTHLY_BUDGET_USD,
        )
        return False
    return True


# ── LLM 呼叫計數器 ──────────────────────────────────────
_llm_call_count = 0


def reset_call_counter() -> None:
    """在每次排程開始時重設計數器。"""
    global _llm_call_count
    _llm_call_count = 0


def _neutral_vector(dim: int = 8) -> list[float]:
    """回傳中性信念向量（全零），用於超出配額時的 fallback。"""
    return [0.0] * dim


async def extract_belief_from_doc(
    text: str,
    dim: int = 8,
    model: str = "gpt-4o-mini",
) -> list[float]:
    """用 LLM 從文件文字抽取信念向量。

    防護機制：
    1. 單次排程呼叫次數上限 (MAX_LLM_CALLS_PER_RUN)
    2. 月度預算上限 (MONTHLY_BUDGET_USD)
    任一超出即回傳中性向量，不呼叫 API。
    """
    global _llm_call_count

    # 防護 1：單次排程上限
    if _llm_call_count >= MAX_LLM_CALLS_PER_RUN:
        logger.warning(
            "LLM call limit reached (%d/%d), returning neutral vector",
            _llm_call_count, MAX_LLM_CALLS_PER_RUN,
        )
        return _neutral_vector(dim)

    # 防護 2：月度預算上限
    if not _check_budget():
        return _neutral_vector(dim)

    # 實際呼叫 LLM
    api_key = os.environ.get("WE_LLM_API_KEY")
    if not api_key:
        logger.error("WE_LLM_API_KEY not set, returning neutral vector")
        return _neutral_vector(dim)

    _llm_call_count += 1
    start = time.time()

    try:
        import httpx

        prompt = (
            f"Analyze the following text and return a JSON array of {dim} floats "
            f"between -1 and 1, representing belief stance on key dimensions "
            f"(economics, security, identity, governance, environment, technology, "
            f"social, international). Return ONLY the JSON array.\n\n"
            f"Text: {text[:3000]}"  # 截斷避免 token 爆量
        )

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 100,
                },
            )
            r.raise_for_status()
            data = r.json()

        # 估算費用（gpt-4o-mini: ~$0.00015/1K input, ~$0.0006/1K output）
        usage = data.get("usage", {})
        input_cost = usage.get("prompt_tokens", 0) / 1000 * 0.00015
        output_cost = usage.get("completion_tokens", 0) / 1000 * 0.0006
        total_cost = input_cost + output_cost
        _record_cost(total_cost)

        elapsed = time.time() - start
        logger.info(
            "LLM call %d/%d, cost=$%.5f, elapsed=%.1fs",
            _llm_call_count, MAX_LLM_CALLS_PER_RUN, total_cost, elapsed,
        )

        # 解析結果
        content = data["choices"][0]["message"]["content"].strip()
        # 嘗試從回應中提取 JSON array
        if "[" in content:
            json_str = content[content.index("["):content.rindex("]") + 1]
            vec = json.loads(json_str)
            if isinstance(vec, list) and len(vec) == dim:
                return [max(-1.0, min(1.0, float(v))) for v in vec]

        logger.warning("LLM response parsing failed: %s", content[:200])
        return _neutral_vector(dim)

    except Exception:
        logger.exception("LLM call failed")
        return _neutral_vector(dim)


def get_cost_summary() -> dict:
    """回傳成本摘要，供監控用。"""
    spent = _load_monthly_cost()
    return {
        "monthly_spent_usd": round(spent, 4),
        "monthly_budget_usd": MONTHLY_BUDGET_USD,
        "remaining_usd": round(MONTHLY_BUDGET_USD - spent, 4),
        "calls_this_run": _llm_call_count,
        "max_calls_per_run": MAX_LLM_CALLS_PER_RUN,
    }
