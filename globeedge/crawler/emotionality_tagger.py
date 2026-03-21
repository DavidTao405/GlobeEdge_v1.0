"""PTT 情緒性標記 — System 1/2 的資料管線。

跑 PTT 爬蟲時，批次對最新文章呼叫 message_analyzer，
結果存入 Redis（TTL=24h）。

仿真時取該時步的平均 emotionality 作為 dual_process 輸入。
"""

import logging
import os

import redis as redis_lib

from globeedge.services.message_analyzer import analyze_emotionality

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("WE_REDIS_URL", "redis://localhost:6379/0")
EMOTIONALITY_TTL = 86400  # 24h


def _get_redis() -> redis_lib.Redis | None:
    try:
        return redis_lib.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        return None


def tag_articles(articles: list[dict], max_tags: int = 50) -> list[float]:
    """對 PTT 文章批次標記情緒性。

    articles: [{"title": ..., "url": ...}, ...]
    結果存入 Redis: ptt:emotionality:{hash}

    Returns:
        情緒性分數清單
    """
    r = _get_redis()
    scores = []

    for article in articles[:max_tags]:
        text = article.get("title", "") + " " + article.get("content", "")
        if not text.strip():
            scores.append(0.5)
            continue

        # 檢查 Redis cache
        cache_key = f"ptt:emotionality:{hash(text[:200])}"
        if r:
            try:
                cached = r.get(cache_key)
                if cached is not None:
                    scores.append(float(cached))
                    continue
            except Exception:
                pass

        # 呼叫 LLM
        score = analyze_emotionality(text)
        scores.append(score)

        # 存 Redis
        if r:
            try:
                r.setex(cache_key, EMOTIONALITY_TTL, str(score))
            except Exception:
                pass

    logger.info("tagged %d articles, avg emotionality: %.3f",
                len(scores), sum(scores) / max(len(scores), 1))
    return scores


def get_current_emotionality() -> float:
    """從 Redis 取得最近一批 PTT 文章的平均情緒性。

    供仿真 FJEngine.run() 使用。
    如果 Redis 沒有資料，回傳 0.5（中性）。
    """
    r = _get_redis()
    if not r:
        return 0.5

    try:
        keys = r.keys("ptt:emotionality:*")
        if not keys:
            return 0.5
        vals = [float(v) for v in r.mget(keys) if v is not None]
        if not vals:
            return 0.5
        return round(sum(vals) / len(vals), 3)
    except Exception:
        return 0.5
