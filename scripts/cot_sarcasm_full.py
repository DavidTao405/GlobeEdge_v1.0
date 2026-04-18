"""Station 3c 全量版：qwen3:14b + /no_think，全 5 維度 876 篇。

隔夜執行，每 50 篇存一次。
"""

import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

import httpx

OLLAMA = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"
START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)

DIM_KEYWORDS = {
    0: {"name": "政府信任度",   "keywords": ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"]},
    1: {"name": "制度公信力",   "keywords": ["柯文哲", "京華城", "判決", "司法", "違憲"]},
    5: {"name": "政治改革意願", "keywords": ["罷免", "民主", "改革", "青鳥"]},
    6: {"name": "群體凝聚度",   "keywords": ["黃國昌", "民眾黨", "李貞秀", "黨籍", "開除"]},
    7: {"name": "外部威脅感知", "keywords": ["鄭習會", "鄭麗文", "習近平", "兩岸", "訪中"]},
}

_cache: dict[str, dict] = {}
_CACHE_FILE = "results/cot_full_cache.json"


def _load():
    global _cache
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _cache = json.load(f)
        logger.info(f"Cache loaded: {len(_cache)} entries")


def _save():
    os.makedirs("results", exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False)


def fmt_comments(comments, n=5):
    if not comments:
        return "(no comments)"
    pushes = [c for c in comments if c.get("type") == "推"][:n]
    boos = [c for c in comments if c.get("type") == "噓"][:n]
    lines = []
    for c in pushes:
        lines.append(f"push {c.get('author','?')}: {c.get('content','')}")
    for c in boos:
        lines.append(f"boo {c.get('author','?')}: {c.get('content','')}")
    return "\n".join(lines) if lines else "(no push/boo)"


def classify(title, content, comments, push, boo, dim_name):
    key = hashlib.md5(f"full:{dim_name}:{title}".encode()).hexdigest()
    if key in _cache:
        return _cache[key]

    prompt = f"""Article title: {title}
Content (first 150 chars): {(content or '')[:150]}
Top push/boo comments:
{fmt_comments(comments or [], 5)}
Push: {push}, Boo: {boo}
Is this article sarcastic about "{dim_name}"? Reply JSON only: {{"is_sarcasm":true/false,"stance":"positive/negative/neutral","confidence":0-1,"reasoning":"one sentence"}}"""

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
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                truncated = match.group()
                if truncated.count('"') % 2 == 1:
                    truncated += '"'
                if not truncated.endswith("}"):
                    truncated += "}"
                try:
                    result = json.loads(truncated)
                except json.JSONDecodeError:
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


def fetch_articles(dim_idx):
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
                "url": a.url, "title": a.title,
                "content": a.content or "",
                "comments": a.push_comments or [],
                "push": a.push_count or 0, "boo": a.boo_count or 0,
            })
    return results


def main():
    os.makedirs("results", exist_ok=True)
    _load()

    logger.info("=" * 60)
    logger.info("Station 3c FULL: qwen3:14b, all 5 dims")
    logger.info("=" * 60)

    all_results = {}
    grand_total = 0
    grand_sarcasm = 0

    for dim_idx, info in DIM_KEYWORDS.items():
        dim_name = info["name"]
        logger.info(f"\n--- dim{dim_idx} {dim_name} ---")
        articles = fetch_articles(dim_idx)
        logger.info(f"  Articles: {len(articles)}")

        sarcasm = []
        genuine = []
        timeout_n = 0
        total_t = 0

        for i, a in enumerate(articles):
            r = classify(a["title"], a["content"], a["comments"],
                         a["push"], a["boo"], dim_name)
            if r.get("is_sarcasm"):
                sarcasm.append(a)
            else:
                genuine.append(a)
            if r["status"] == "timeout":
                timeout_n += 1
            total_t += r.get("elapsed", 0)

            if (i + 1) % 50 == 0:
                _save()
                logger.info(f"  {i+1}/{len(articles)} sarc={len(sarcasm)} "
                            f"timeout={timeout_n} avg={total_t/(i+1):.1f}s")

        _save()
        grand_total += len(articles)
        grand_sarcasm += len(sarcasm)

        avg_conf = 0
        sarc_confs = [_cache.get(hashlib.md5(f"full:{dim_name}:{a['title']}".encode()).hexdigest(), {}).get("confidence", 0)
                      for a in sarcasm]
        if sarc_confs:
            avg_conf = sum(sarc_confs) / len(sarc_confs)

        logger.info(f"  DONE: genuine={len(genuine)} sarcasm={len(sarcasm)} "
                     f"({len(sarcasm)/max(len(articles),1)*100:.0f}%) "
                     f"avg_conf={avg_conf:.2f} timeout={timeout_n}")

        all_results[dim_idx] = {
            "dim_name": dim_name,
            "total": len(articles),
            "genuine": len(genuine),
            "sarcasm": len(sarcasm),
            "sarcasm_ratio": round(len(sarcasm) / max(len(articles), 1), 3),
            "avg_confidence": round(avg_conf, 3),
            "timeout": timeout_n,
            "sarcasm_urls": [a["url"] for a in sarcasm],
            "genuine_urls": [a["url"] for a in genuine],
        }

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"GRAND TOTAL: {grand_total} articles, {grand_sarcasm} sarcasm "
                 f"({grand_sarcasm/max(grand_total,1)*100:.0f}%)")
    logger.info(f"Cache: {len(_cache)} entries")
    logger.info(f"{'='*60}")

    for dim_idx, r in sorted(all_results.items()):
        logger.info(f"  dim{dim_idx} {r['dim_name']:10s}: "
                     f"{r['sarcasm']:3d}/{r['total']:3d} sarcasm "
                     f"({r['sarcasm_ratio']*100:.0f}%) "
                     f"avg_conf={r['avg_confidence']:.2f}")

    output = {
        "model": MODEL,
        "dimensions": {str(k): v for k, v in all_results.items()},
        "grand_total": grand_total,
        "grand_sarcasm": grand_sarcasm,
        "grand_ratio": round(grand_sarcasm / max(grand_total, 1), 3),
    }
    with open("results/cot_full_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"\nSaved: results/cot_full_results.json")


if __name__ == "__main__":
    main()
