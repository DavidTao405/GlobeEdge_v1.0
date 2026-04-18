"""Station 3c 完整版：qwen3:14b + /no_think。"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

import httpx

OLLAMA = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"
START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)
DIM0_KW = ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"]

_cache: dict[str, dict] = {}
_CACHE_FILE = "results/cot_qwen3_14b_cache.json"


def _load():
    global _cache
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _cache = json.load(f)


def _save():
    os.makedirs("results", exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False)


def fmt_comments(comments, n=5):
    if not comments:
        return "（無推文）"
    pushes = [c for c in comments if c.get("type") == "推"][:n]
    boos = [c for c in comments if c.get("type") == "噓"][:n]
    lines = []
    for c in pushes:
        lines.append(f"👍 {c.get('author','?')}: {c.get('content','')}")
    for c in boos:
        lines.append(f"👎 {c.get('author','?')}: {c.get('content','')}")
    return "\n".join(lines) if lines else "（無推噓文）"


def classify(title, content, comments, push, boo):
    key = hashlib.md5(f"q3_14b:{title}".encode()).hexdigest()
    if key in _cache:
        return _cache[key]

    prompt = f"""文章標題：{title}
內文前150字：{(content or '')[:150]}
推噓文：
{fmt_comments(comments or [], 5)}
推{push}噓{boo}。這篇是反串嗎？只回JSON：{{"is_sarcasm":true/false,"stance":"positive/negative/neutral","confidence":0-1,"reasoning":"一句話"}}"""

    t0 = time.time()
    try:
        r = httpx.post(OLLAMA, json={
            "model": MODEL, "stream": False,
            "options": {"temperature": 0.05, "num_predict": 1000, "num_ctx": 8192},
            "messages": [
                {"role": "system", "content": "/no_think"},
                {"role": "user", "content": prompt},
            ],
        }, timeout=120)
        r.raise_for_status()
        elapsed = time.time() - t0
        raw = r.json().get("message", {}).get("content", "")
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        # Try exact JSON match first, then truncated JSON repair
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                # Truncated JSON — try to repair by closing the string + brace
                truncated = match.group()
                if truncated.count('"') % 2 == 1:
                    truncated += '"'
                if not truncated.endswith("}"):
                    truncated += "}"
                try:
                    result = json.loads(truncated)
                except json.JSONDecodeError:
                    # Last resort: extract what we can
                    is_s = '"is_sarcasm":true' in raw.lower() or '"is_sarcasm": true' in raw.lower()
                    result = {"is_sarcasm": is_s, "stance": "neutral", "confidence": 0.5,
                              "reasoning": "truncated_repair"}
            result["elapsed"] = round(elapsed, 1)
            result["status"] = "ok"
        else:
            result = {"is_sarcasm": False, "stance": "neutral", "confidence": 0,
                      "reasoning": "parse_fail", "elapsed": round(elapsed, 1), "status": "parse_fail"}
    except httpx.TimeoutException:
        result = {"is_sarcasm": False, "stance": "neutral", "confidence": 0,
                  "reasoning": "timeout", "elapsed": 120, "status": "timeout"}
    except Exception as e:
        result = {"is_sarcasm": False, "stance": "neutral", "confidence": 0,
                  "reasoning": str(e)[:50], "elapsed": time.time() - t0, "status": "error"}

    _cache[key] = result
    return result


def main():
    os.makedirs("results", exist_ok=True)
    _load()

    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    app = create_app()
    with app.app_context():
        filters = [PttArticle.title.contains(kw) for kw in DIM0_KW]
        arts = PttArticle.query.filter(db.or_(*filters)).all()
        articles = []
        for a in arts:
            m = re.search(r"M\.(\d+)\.A", a.url)
            if not m:
                continue
            dt = datetime.fromtimestamp(int(m.group(1)))
            if not (START <= dt < END):
                continue
            articles.append({
                "url": a.url, "title": a.title,
                "content": a.content or "",
                "comments": a.push_comments or [],
                "push": a.push_count or 0, "boo": a.boo_count or 0,
                "day": (dt.date() - START.date()).days,
            })

    logger.info(f"dim0 文章：{len(articles)}  model={MODEL}")

    results = []
    sarc_n = 0
    timeout_n = 0
    total_t = 0

    for i, a in enumerate(articles):
        r = classify(a["title"], a["content"], a["comments"], a["push"], a["boo"])
        a["r"] = r
        results.append(a)
        if r.get("is_sarcasm"):
            sarc_n += 1
        if r["status"] == "timeout":
            timeout_n += 1
        total_t += r.get("elapsed", 0)
        if (i + 1) % 20 == 0:
            logger.info(f"  {i+1}/{len(articles)}  sarc={sarc_n} timeout={timeout_n} avg={total_t/(i+1):.1f}s")
            _save()

    _save()

    ok_n = sum(1 for a in results if a["r"]["status"] == "ok")
    logger.info(f"\n{'='*60}")
    logger.info(f"成功：{ok_n}/{len(articles)}  Timeout：{timeout_n}  Sarcasm：{sarc_n} ({sarc_n/len(articles)*100:.0f}%)")
    logger.info(f"平均耗時：{total_t/len(articles):.1f} 秒/篇")

    sarcasm = [a for a in results if a["r"].get("is_sarcasm")]
    genuine = [a for a in results if not a["r"].get("is_sarcasm") and a["r"]["status"] == "ok"]

    # 人工驗證樣本
    import random
    random.seed(42)
    sample_s = random.sample(sarcasm, min(10, len(sarcasm)))
    sample_g = random.sample(genuine, min(10, len(genuine)))

    logger.info(f"\n{'='*60}")
    logger.info(f"=== 驗證組 1：模型說「是反串」({len(sample_s)} 篇) ===")
    for j, a in enumerate(sample_s):
        r = a["r"]
        logger.info(f"\n#{j+1} 標題：{a['title'][:55]}")
        logger.info(f"   推：{a['push']} 噓：{a['boo']}")
        logger.info(f"   判斷：is_sarcasm={r['is_sarcasm']}  stance={r['stance']}  conf={r['confidence']}")
        logger.info(f"   reasoning：{r.get('reasoning','')[:70]}")
        logger.info(f"   你的判斷：[ 待填 ]")

    logger.info(f"\n{'='*60}")
    logger.info(f"=== 驗證組 2：模型說「不是反串」({len(sample_g)} 篇) ===")
    for j, a in enumerate(sample_g):
        r = a["r"]
        logger.info(f"\n#{j+1} 標題：{a['title'][:55]}")
        logger.info(f"   推：{a['push']} 噓：{a['boo']}")
        logger.info(f"   判斷：is_sarcasm={r['is_sarcasm']}  stance={r['stance']}  conf={r['confidence']}")
        logger.info(f"   reasoning：{r.get('reasoning','')[:70]}")
        logger.info(f"   你的判斷：[ 待填 ]")

    # Save full results
    output = {
        "model": MODEL,
        "total": len(articles), "ok": ok_n,
        "timeout": timeout_n, "sarcasm": sarc_n,
        "sarcasm_ratio": round(sarc_n / max(len(articles), 1), 3),
        "avg_speed": round(total_t / max(len(articles), 1), 1),
        "sarcasm_urls": [a["url"] for a in sarcasm],
        "genuine_urls": [a["url"] for a in genuine],
    }
    with open("results/cot_qwen3_14b.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告：results/cot_qwen3_14b.json")


if __name__ == "__main__":
    main()
