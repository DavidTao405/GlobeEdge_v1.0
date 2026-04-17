"""Station 3c v2：簡化 prompt + 雙模型比較實驗。

實驗 A: qwen3.5:9b
實驗 B: gemma4:31b

用法：
    python scripts/cot_sarcasm_v2.py --model qwen3.5:9b --output results/cot_v2_qwen.json
    python scripts/cot_sarcasm_v2.py --model gemma4:31b --output results/cot_v2_gemma.json
"""

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

OLLAMA_CHAT = "http://localhost:11434/api/chat"

START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)

DIM0_KEYWORDS = ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"]

PTT_CONTEXT = """【PTT 反串辨識重點】
反串＝表面立場和真實立場相反。
線索：誇張正面語氣、「笑死」「可憐哪」「嘻嘻」、推文接力玩梗。
真誠批評：有具體指控、數據或新聞引用。"""


def format_top_pushboo(comments: list[dict], n: int = 5) -> str:
    if not comments:
        return "（無推文）"
    pushes = [c for c in comments if c.get("type") == "推"][:n]
    boos = [c for c in comments if c.get("type") == "噓"][:n]
    lines = []
    for c in pushes:
        lines.append(f"👍 {c.get('author', '?')}: {c.get('content', '')}")
    for c in boos:
        lines.append(f"👎 {c.get('author', '?')}: {c.get('content', '')}")
    return "\n".join(lines) if lines else "（無推噓文）"


def classify(title, content, comments, push, boo, model, timeout=60):
    pushboo_text = format_top_pushboo(comments or [], n=5)
    content_snip = (content or "")[:150]

    prompt = f"""/no_think
{PTT_CONTEXT}

文章標題：{title}
內文摘要（前 150 字）：{content_snip if content_snip else "（無內文）"}

最具代表性的推噓文：
{pushboo_text}

推：{push} 噓：{boo}

請判斷：
1. 推文的人是在認同文章觀點，還是認同諷刺？
2. 這篇文章是真誠表態還是反串？

只輸出 JSON：
{{"is_sarcasm": true或false, "stance": "positive"或"negative"或"neutral", "confidence": 0到1的小數, "reasoning": "一句話說明"}}"""

    t0 = time.time()
    try:
        r = httpx.post(OLLAMA_CHAT, json={
            "model": model,
            "stream": False,
            "options": {"temperature": 0.05},
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=timeout)
        r.raise_for_status()
        elapsed = time.time() - t0
        raw = r.json().get("message", {}).get("content", "")
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        match = re.search(r"\{[^}]+\}", raw)
        if match:
            result = json.loads(match.group())
            result["elapsed"] = round(elapsed, 1)
            result["status"] = "ok"
            return result
        return {"is_sarcasm": False, "stance": "neutral", "confidence": 0.0,
                "reasoning": "parse_fail", "elapsed": round(elapsed, 1), "status": "parse_fail"}
    except httpx.TimeoutException:
        return {"is_sarcasm": False, "stance": "neutral", "confidence": 0.0,
                "reasoning": "timeout", "elapsed": timeout, "status": "timeout"}
    except Exception as e:
        return {"is_sarcasm": False, "stance": "neutral", "confidence": 0.0,
                "reasoning": str(e)[:50], "elapsed": time.time() - t0, "status": "error"}


def fetch_dim0():
    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    app = create_app()
    with app.app_context():
        filters = [PttArticle.title.contains(kw) for kw in DIM0_KEYWORDS]
        arts = PttArticle.query.filter(db.or_(*filters)).all()
        results = []
        for a in arts:
            m = re.search(r"M\.(\d+)\.A", a.url)
            if not m:
                continue
            dt = datetime.fromtimestamp(int(m.group(1)))
            if not (START <= dt < END):
                continue
            results.append({
                "url": a.url, "title": a.title,
                "content": a.content or "",
                "push_comments": a.push_comments or [],
                "push": a.push_count or 0, "boo": a.boo_count or 0,
                "arrow": a.arrow_count or 0,
            })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", default="results/cot_v2.json")
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"  Station 3c v2: {args.model}")
    logger.info("=" * 60)

    articles = fetch_dim0()
    logger.info(f"  dim0 文章：{len(articles)}")
    logger.info(f"  有內文：{sum(1 for a in articles if a['content'])}")
    logger.info(f"  有推文串：{sum(1 for a in articles if a['push_comments'])}")

    results = []
    sarcasm_count = 0
    timeout_count = 0
    total_time = 0

    for i, a in enumerate(articles):
        r = classify(a["title"], a["content"], a["push_comments"],
                      a["push"], a["boo"], args.model, args.timeout)
        a["result"] = r
        results.append(a)

        if r["status"] == "timeout":
            timeout_count += 1
        if r.get("is_sarcasm"):
            sarcasm_count += 1
        total_time += r.get("elapsed", 0)

        if (i + 1) % 20 == 0 or i < 5:
            logger.info(f"  [{i+1}/{len(articles)}] "
                        f"sarcasm={sarcasm_count} timeout={timeout_count} "
                        f"avg={total_time/(i+1):.1f}s/篇")
            if i < 5:
                logger.info(f"    title: {a['title'][:50]}")
                logger.info(f"    → sarcasm={r.get('is_sarcasm')} stance={r.get('stance')} "
                            f"conf={r.get('confidence')} elapsed={r.get('elapsed')}s")
                logger.info(f"    → reasoning: {r.get('reasoning', '')[:60]}")

    # Summary
    ok_count = sum(1 for a in results if a["result"]["status"] == "ok")
    logger.info(f"\n{'='*60}")
    logger.info(f"  結果摘要 ({args.model})")
    logger.info(f"{'='*60}")
    logger.info(f"  成功：{ok_count}/{len(articles)} ({ok_count/len(articles)*100:.0f}%)")
    logger.info(f"  Timeout：{timeout_count} ({timeout_count/len(articles)*100:.0f}%)")
    logger.info(f"  Sarcasm：{sarcasm_count} ({sarcasm_count/len(articles)*100:.0f}%)")
    logger.info(f"  平均速度：{total_time/len(articles):.1f} 秒/篇")

    # Sarcasm samples
    sarcasm_articles = [a for a in results if a["result"].get("is_sarcasm")]
    genuine_articles = [a for a in results if not a["result"].get("is_sarcasm") and a["result"]["status"] == "ok"]

    if sarcasm_articles:
        logger.info(f"\n  SARCASM 文章 ({len(sarcasm_articles)} 篇):")
        for j, a in enumerate(sarcasm_articles[:10]):
            r = a["result"]
            logger.info(f"    [{j+1}] {a['title'][:50]}")
            logger.info(f"      推{a['push']} 噓{a['boo']} conf={r['confidence']} reasoning: {r.get('reasoning','')[:60]}")

    # Save
    output = {
        "model": args.model,
        "total": len(articles),
        "ok": ok_count,
        "timeout": timeout_count,
        "sarcasm": sarcasm_count,
        "sarcasm_ratio": round(sarcasm_count / max(len(articles), 1), 3),
        "avg_speed": round(total_time / max(len(articles), 1), 1),
        "sarcasm_urls": [a["url"] for a in sarcasm_articles],
        "genuine_urls": [a["url"] for a in genuine_articles],
        "details": [{
            "url": a["url"], "title": a["title"],
            "push": a["push"], "boo": a["boo"],
            "result": a["result"],
        } for a in results],
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告：{args.output}")


if __name__ == "__main__":
    main()
