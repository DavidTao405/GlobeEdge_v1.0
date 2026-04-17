"""Station 3c：CoT + 完整內文 + 推文串反串偵測。

用 Chain-of-Thought 推理 + 推文串語氣分析判斷反串。
這是 Station 3 的最終版本。
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

import httpx

OLLAMA_CHAT = "http://localhost:11434/api/chat"
CHAT_MODEL = "qwen3.5:9b"

START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)

DIM_KEYWORDS = {
    0: {"name": "政府信任度",   "keywords": ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"]},
    1: {"name": "制度公信力",   "keywords": ["柯文哲", "京華城", "判決", "司法", "違憲"]},
    5: {"name": "政治改革意願", "keywords": ["罷免", "民主", "改革", "青鳥"]},
    6: {"name": "群體凝聚度",   "keywords": ["黃國昌", "民眾黨", "李貞秀", "黨籍", "開除"]},
    7: {"name": "外部威脅感知", "keywords": ["鄭習會", "鄭麗文", "習近平", "兩岸", "訪中"]},
}

# PTT 語境（嵌入 prompt）
PTT_CONTEXT = """【台灣 PTT 文化】
反串格式：用誇張正面語氣嘲諷、引用對方言論加諷刺結論、推文「推」跟在諷刺文後=認同諷刺。
推文串線索：「笑死」「可憐哪」「嘻嘻」= 嘲諷語氣。推文如果在接力玩梗 = 整串是反串。
真誠批評：直接指出問題、有數據佐證、語氣可能憤怒但有論點。"""

_cache: dict[str, dict] = {}
_CACHE_FILE = "results/cot_sarcasm_cache.json"


def _load_cache():
    global _cache
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _cache = json.load(f)


def _save_cache():
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False)


def format_push_comments(comments: list[dict], max_n: int = 30) -> str:
    if not comments:
        return "（無推文）"
    lines = []
    type_map = {"推": "👍", "噓": "👎", "→": "→"}
    for c in comments[:max_n]:
        symbol = type_map.get(c.get("type", "→"), "→")
        lines.append(f"{symbol} {c.get('author', '?')}: {c.get('content', '')}")
    if len(comments) > max_n:
        lines.append(f"...（共 {len(comments)} 則推文，僅顯示前 {max_n} 則）")
    return "\n".join(lines)


def cot_classify(
    title: str,
    content: str,
    push_comments: list[dict],
    push: int, boo: int,
    dim_name: str,
) -> dict:
    """CoT + 推文串反串偵測。"""
    cache_key = hashlib.md5(f"cot:{title}:{dim_name}".encode()).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key]

    comments_text = format_push_comments(push_comments or [], max_n=30)
    content_snippet = (content or "")[:300]

    prompt = f"""/no_think
{PTT_CONTEXT}

請分析以下 PTT 文章：

【標題】{title}

【文章內文（前 300 字）】
{content_snippet if content_snippet else "（無內文）"}

【推文串（前 30 則）】
{comments_text}
推文數：{push}  噓文數：{boo}

請用三個步驟推理：

Step 1：推文串語氣分析
  這些推文是在認同文章觀點、嘲諷文章、還是正常討論？
  有沒有推文在「呼應諷刺」或「識破反串」？

Step 2：文章立場判斷
  結合標題和內文，作者的真實立場是什麼？
  語氣是誇張、諷刺、還是直接陳述？

Step 3：最終結論
  這篇文章對「{dim_name}」的真實立場是？
  是否為反串？為什麼？

只輸出 JSON：
{{"is_sarcasm": true或false, "stance": "positive"或"negative"或"neutral", "confidence": 0到1的小數, "reasoning": "一句話說明"}}"""

    try:
        r = httpx.post(OLLAMA_CHAT, json={
            "model": CHAT_MODEL,
            "stream": False,
            "options": {"temperature": 0.05},
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=90)
        r.raise_for_status()
        raw = r.json().get("message", {}).get("content", "")
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        match = re.search(r"\{[^}]+\}", raw)
        if match:
            result = json.loads(match.group())
        else:
            result = {"is_sarcasm": False, "stance": "neutral", "confidence": 0.3, "reasoning": "parse_fail"}
    except Exception as e:
        logger.debug(f"LLM error: {e}")
        result = {"is_sarcasm": False, "stance": "neutral", "confidence": 0.0, "reasoning": str(e)[:50]}

    _cache[cache_key] = result
    return result


def fetch_articles(dim_idx: int) -> list[dict]:
    """從 DB 取文章（含內文 + 推文串）。"""
    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    keywords = DIM_KEYWORDS[dim_idx]["keywords"]
    app = create_app()
    with app.app_context():
        filters = [PttArticle.title.contains(kw) for kw in keywords]
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
                "url": a.url,
                "title": a.title,
                "content": a.content or "",
                "push_comments": a.push_comments or [],
                "board": a.board,
                "push": a.push_count or 0,
                "boo": a.boo_count or 0,
                "arrow": a.arrow_count or 0,
                "day": (dt.date() - START.date()).days,
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="CoT + 推文串反串偵測")
    parser.add_argument("--dims", default="0", help="維度（逗號分隔）")
    parser.add_argument("--sample", type=int, default=20)
    parser.add_argument("--output", default="results/cot_sarcasm.json")
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    dims = [int(d.strip()) for d in args.dims.split(",")]
    _load_cache()

    logger.info("=" * 60)
    logger.info("  Station 3c：CoT + 完整內文 + 推文串反串偵測")
    logger.info("=" * 60)

    all_results = {}
    for dim_idx in dims:
        info = DIM_KEYWORDS.get(dim_idx)
        if not info:
            continue
        logger.info(f"\ndim{dim_idx} {info['name']}")

        articles = fetch_articles(dim_idx)
        logger.info(f"  文章數：{len(articles)}  有內文：{sum(1 for a in articles if a['content'])}  有推文串：{sum(1 for a in articles if a['push_comments'])}")

        genuine = []
        sarcasm = []
        for i, a in enumerate(articles):
            result = cot_classify(
                a["title"], a["content"], a["push_comments"],
                a["push"], a["boo"], info["name"],
            )
            a["cot"] = result
            if result.get("is_sarcasm"):
                sarcasm.append(a)
            else:
                genuine.append(a)
            if (i + 1) % 20 == 0:
                logger.info(f"    {i+1}/{len(articles)} done  (sarcasm so far: {len(sarcasm)})")
                _save_cache()

        _save_cache()

        gp = sum(a["push"] for a in genuine)
        gb = sum(a["boo"] for a in genuine)
        sp = sum(a["push"] for a in sarcasm)
        sb = sum(a["boo"] for a in sarcasm)

        logger.info(f"  GENUINE: {len(genuine)} ({len(genuine)/len(articles)*100:.0f}%)  push:boo={gp}:{gb}")
        logger.info(f"  SARCASM: {len(sarcasm)} ({len(sarcasm)/len(articles)*100:.0f}%)  push:boo={sp}:{sb}")

        # 人工抽樣
        import random
        random.seed(42)
        sample_s = random.sample(sarcasm, min(args.sample, len(sarcasm)))
        if sample_s:
            logger.info(f"\n  SARCASM 抽樣 ({len(sample_s)} 篇):")
            for j, a in enumerate(sample_s):
                r = a["cot"]
                logger.info(f"    [{j+1}] {a['title'][:50]}")
                logger.info(f"      推{a['push']} 噓{a['boo']}  stance={r['stance']}  conf={r['confidence']}")
                logger.info(f"      reasoning: {r.get('reasoning', '')[:60]}")

        sample_g = random.sample(genuine, min(5, len(genuine)))
        logger.info(f"\n  GENUINE 抽樣 ({len(sample_g)} 篇):")
        for j, a in enumerate(sample_g):
            r = a["cot"]
            logger.info(f"    [{j+1}] {a['title'][:50]}")
            logger.info(f"      推{a['push']} 噓{a['boo']}  stance={r['stance']}  conf={r['confidence']}")

        all_results[dim_idx] = {
            "total": len(articles),
            "genuine": len(genuine),
            "sarcasm": len(sarcasm),
            "sarcasm_ratio": round(len(sarcasm) / max(len(articles), 1), 3),
            "genuine_urls": [a["url"] for a in genuine],
            "sarcasm_urls": [a["url"] for a in sarcasm],
        }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告：{args.output}")
    logger.info(f"Cache: {len(_cache)} entries")


if __name__ == "__main__":
    main()
