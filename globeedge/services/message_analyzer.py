"""訊息情緒性分析 — System 1/2 的輸入層。

用 Ollama qwen3.5:9b 分析文本的情緒性程度。
0 = 純理性論述（數據、政策分析）
1 = 純情緒表達（憤怒、恐懼、謾罵）

含 in-memory cache，同樣內容不重複呼叫 LLM。
"""

import hashlib
import logging
import re

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3.5:9b"

SYSTEM_PROMPT = """/no_think
分析以下訊息的情緒性程度。
0 = 純理性論述（數據、邏輯、政策分析、學術討論）
1 = 純情緒表達（憤怒、恐懼、謾罵、激動、嘲諷）
0.5 = 混合（有論點但帶情緒）
只回傳一個 0 到 1 之間的小數，不要任何說明。"""

# In-memory cache（同樣內容不重複呼叫）
_cache: dict[str, float] = {}
_MAX_CACHE = 5000


def _cache_key(text: str) -> str:
    return hashlib.md5(text[:500].encode()).hexdigest()


def analyze_emotionality(text: str, timeout: float = 60) -> float:
    """分析單篇文本的情緒性。

    Returns:
        0.0 (純理性) 到 1.0 (純情緒)
    """
    if not text or not text.strip():
        return 0.5

    key = _cache_key(text)
    if key in _cache:
        return _cache[key]

    try:
        r = httpx.post(OLLAMA_URL, json={
            "model": MODEL,
            "stream": False,
            "options": {"temperature": 0.05, "top_p": 0.9},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text[:500]},
            ],
        }, timeout=timeout)
        r.raise_for_status()
        raw = r.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.debug("emotionality analysis failed: %s", e)
        return 0.5

    # 解析數字
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    match = re.search(r"([01]\.?\d*)", raw)
    if match:
        val = max(0.0, min(1.0, float(match.group(1))))
    else:
        val = 0.5

    # Cache
    if len(_cache) >= _MAX_CACHE:
        # 簡單 FIFO：清掉一半
        keys = list(_cache.keys())
        for k in keys[:len(keys) // 2]:
            del _cache[k]
    _cache[key] = val
    return val


def analyze_batch(texts: list[str], timeout: float = 30) -> list[float]:
    """批次分析多篇文本的情緒性。"""
    return [analyze_emotionality(t, timeout) for t in texts]


def get_average_emotionality(texts: list[str], timeout: float = 30) -> float:
    """取得多篇文本的平均情緒性。"""
    if not texts:
        return 0.5
    scores = analyze_batch(texts, timeout)
    return round(sum(scores) / len(scores), 3)
