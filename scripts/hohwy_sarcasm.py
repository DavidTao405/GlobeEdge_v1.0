"""Station 3a：Hohwy 預測誤差反串偵測。

基於 Hohwy (2013) Predictive Mind 框架：
  prediction_error = |surface_signal - semantic_signal|
  高 prediction_error → 表面推噓方向與語意不一致 → 疑似反串

用法：
  python scripts/hohwy_sarcasm.py
  python scripts/hohwy_sarcasm.py --dim dim0 --threshold 0.35
  python scripts/hohwy_sarcasm.py --sample 10   # 人工驗證抽樣
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

import httpx

EMBED_MODEL = "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest"
OLLAMA_URL = "http://localhost:11434/api/embed"
SARCASM_THRESHOLD = 0.35

START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)

# ── 立場基準敘事 ──────────────────────────────────────────

STANCE_BASELINES = {
    "dim0": {
        "positive": (
            "政府施政有效率，執政黨值得信任，政策方向正確，"
            "民眾生活有改善，國家治理走在正確的路上，做得很好"
        ),
        "negative": (
            "政府完全失能，執政黨只會騙票，政策一塌糊塗，"
            "國家被搞垮了，人民根本不信任這個政府，無能下台"
        ),
    },
    "dim1": {
        "positive": (
            "司法獨立公正，法院判決合理，制度運作正常，"
            "法治健全，程序正義得到保障，依法治國"
        ),
        "negative": (
            "司法是政治工具，判決不公，制度已經崩壞，"
            "法官被收買，程序正義蕩然無存，司法迫害異己"
        ),
    },
    "dim7": {
        "positive": (
            "兩岸緩和有和平的可能，對話有價值，"
            "戰爭風險降低，安全無虞，穩定的未來"
        ),
        "negative": (
            "外部威脅嚴重，戰爭風險升高，隨時可能開打，"
            "軍事演習不斷，國家安全岌岌可危，非常危險"
        ),
    },
}

# ── Embedding ────────────────────────────────────────────

_embed_cache: dict[str, list[float]] = {}


def get_embedding(text: str) -> np.ndarray:
    """用 Ollama GTE-Qwen2 取得 embedding。含快取。"""
    key = text[:200]
    if key in _embed_cache:
        return np.array(_embed_cache[key])

    try:
        r = httpx.post(OLLAMA_URL, json={
            "model": EMBED_MODEL,
            "input": text[:500],
        }, timeout=30)
        r.raise_for_status()
        embs = r.json().get("embeddings", [])
        if embs:
            _embed_cache[key] = embs[0]
            return np.array(embs[0])
    except Exception as e:
        logger.debug("embedding failed: %s", e)

    return np.zeros(1536)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity [-1, +1]."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ── Hohwy 預測誤差 ───────────────────────────────────────

def compute_prediction_error(
    article_text: str,
    push_ratio: float,
    dim: str,
) -> dict:
    """計算單篇文章的 Hohwy 預測誤差。"""
    baselines = STANCE_BASELINES.get(dim)
    if not baselines:
        return {"prediction_error": 0.0, "semantic_signal": 0.0, "surface_signal": 0.0}

    # Surface signal（推噓比）
    surface_signal = (push_ratio - 0.5) * 2  # [-1, +1]

    # Semantic signal（embedding cosine distance）
    article_vec = get_embedding(article_text)
    pos_vec = get_embedding(baselines["positive"])
    neg_vec = get_embedding(baselines["negative"])

    sim_pos = cosine_similarity(article_vec, pos_vec)
    sim_neg = cosine_similarity(article_vec, neg_vec)

    # 語意立場：正值偏正向（距離正向基準更近）
    semantic_signal = (sim_pos - sim_neg) * 2  # 放大到 [-1, +1] 範圍
    semantic_signal = max(-1.0, min(1.0, semantic_signal))

    # Hohwy 預測誤差
    prediction_error = abs(surface_signal - semantic_signal) / 2  # 正規化到 [0, 1]

    return {
        "surface_signal": round(surface_signal, 3),
        "semantic_signal": round(semantic_signal, 3),
        "prediction_error": round(prediction_error, 3),
        "sim_pos": round(sim_pos, 3),
        "sim_neg": round(sim_neg, 3),
    }


# ── 主要流程 ──────────────────────────────────────────────

def fetch_dim0_articles() -> list[dict]:
    """從 DB 取 dim0 相關文章。"""
    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    keywords = ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"]

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
            total_pb = (a.push_count or 0) + (a.boo_count or 0)
            push_ratio = (a.push_count or 0) / total_pb if total_pb > 0 else 0.5
            # 用標題 + 內文前 200 字做 embedding（內文補抓後可用）
            content_snippet = (a.content or "")[:200]
            embed_text = f"{a.title}\n{content_snippet}" if content_snippet else a.title
            results.append({
                "url": a.url,
                "title": a.title,
                "board": a.board,
                "date": dt.strftime("%Y-%m-%d"),
                "day": (dt.date() - START.date()).days,
                "push": a.push_count or 0,
                "boo": a.boo_count or 0,
                "arrow": a.arrow_count or 0,
                "push_ratio": round(push_ratio, 3),
                "text": embed_text,
                "has_content": bool(content_snippet),
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="Hohwy 預測誤差反串偵測")
    parser.add_argument("--dim", default="dim0")
    parser.add_argument("--threshold", type=float, default=SARCASM_THRESHOLD)
    parser.add_argument("--sample", type=int, default=10, help="人工驗證抽樣數")
    parser.add_argument("--output", default="results/hohwy_sarcasm.json")
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"  Hohwy 預測誤差反串偵測（{args.dim}）")
    logger.info(f"  Threshold: {args.threshold}")
    logger.info("=" * 60)

    # Step 1: 取文章
    logger.info("\nStep 1: 從 DB 取 dim0 相關文章")
    articles = fetch_dim0_articles()
    logger.info(f"  共 {len(articles)} 篇")

    # Step 2: 預計算基準 embedding
    logger.info("\nStep 2: 預計算基準敘事 embedding")
    baselines = STANCE_BASELINES[args.dim]
    pos_vec = get_embedding(baselines["positive"])
    neg_vec = get_embedding(baselines["negative"])
    baseline_sim = cosine_similarity(pos_vec, neg_vec)
    logger.info(f"  正負基準間 cosine sim: {baseline_sim:.3f}（越低區分度越好）")

    # Step 3: 對每篇文章計算 prediction_error
    logger.info(f"\nStep 3: 計算 {len(articles)} 篇文章的 prediction_error")
    for i, a in enumerate(articles):
        result = compute_prediction_error(a["text"], a["push_ratio"], args.dim)
        a.update(result)
        if (i + 1) % 20 == 0:
            logger.info(f"  {i+1}/{len(articles)} done")

    # Step 4: 分類
    genuine = [a for a in articles if a["prediction_error"] <= args.threshold]
    sarcasm = [a for a in articles if a["prediction_error"] > args.threshold]
    logger.info(f"\nStep 4: 分類結果")
    logger.info(f"  GENUINE:          {len(genuine)} 篇 ({len(genuine)/len(articles)*100:.0f}%)")
    logger.info(f"  SARCASM_SUSPECT:  {len(sarcasm)} 篇 ({len(sarcasm)/len(articles)*100:.0f}%)")

    # 統計
    logger.info(f"\n  GENUINE 推噓比:")
    if genuine:
        gp = sum(a["push"] for a in genuine)
        gb = sum(a["boo"] for a in genuine)
        logger.info(f"    push={gp} boo={gb} ratio={gp/(gp+gb)*100:.0f}%:{gb/(gp+gb)*100:.0f}%")

    logger.info(f"\n  SARCASM_SUSPECT 推噓比:")
    if sarcasm:
        sp = sum(a["push"] for a in sarcasm)
        sb = sum(a["boo"] for a in sarcasm)
        logger.info(f"    push={sp} boo={sb} ratio={sp/(sp+sb)*100:.0f}%:{sb/(sp+sb)*100:.0f}%" if sp+sb > 0 else "    no push/boo")

    # Step 5: 人工驗證抽樣
    logger.info(f"\nStep 5: 人工驗證抽樣（{min(args.sample, len(sarcasm))} 篇 SARCASM_SUSPECT）")
    import random
    random.seed(42)
    sample = random.sample(sarcasm, min(args.sample, len(sarcasm)))
    for i, a in enumerate(sample):
        logger.info(f"\n  [{i+1}] {a['title'][:55]}")
        logger.info(f"       推{a['push']} 噓{a['boo']} → surface={a['surface_signal']:+.2f}")
        logger.info(f"       semantic={a['semantic_signal']:+.2f}  PE={a['prediction_error']:.3f}")
        logger.info(f"       sim_pos={a['sim_pos']:.3f}  sim_neg={a['sim_neg']:.3f}")

    # Step 6: 輸出（供 predictive_validation 使用）
    output = {
        "dim": args.dim,
        "threshold": args.threshold,
        "total_articles": len(articles),
        "genuine_count": len(genuine),
        "sarcasm_count": len(sarcasm),
        "sarcasm_ratio": round(len(sarcasm) / len(articles), 3) if articles else 0,
        "baseline_cosine_sim": round(baseline_sim, 3),
        "genuine_urls": [a["url"] for a in genuine],
        "sarcasm_urls": [a["url"] for a in sarcasm],
        "prediction_error_stats": {
            "mean": round(float(np.mean([a["prediction_error"] for a in articles])), 3),
            "std": round(float(np.std([a["prediction_error"] for a in articles])), 3),
            "median": round(float(np.median([a["prediction_error"] for a in articles])), 3),
        },
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告已輸出：{args.output}")


if __name__ == "__main__":
    main()
