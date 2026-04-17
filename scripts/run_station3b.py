"""Station 3b 完整執行：RAG 分類 + AUC 比較。

Phase B: 載入知識庫（已建立 8 份 .md）
Phase C: 對所有相關 PTT 文章執行 RAG 分類
Phase D: 與 Station 3a 比較，回答「需要文化語境嗎？」
"""

import hashlib
import json
import logging
import os
import re
import sys
import time
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

# 維度關鍵字（與 predictive_validation.py 一致）
DIM_KEYWORDS = {
    0: {"name": "政府信任度",   "keywords": ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"]},
    1: {"name": "制度公信力",   "keywords": ["柯文哲", "京華城", "判決", "司法", "違憲"]},
    5: {"name": "政治改革意願", "keywords": ["罷免", "民主", "改革", "青鳥"]},
    6: {"name": "群體凝聚度",   "keywords": ["黃國昌", "民眾黨", "李貞秀", "黨籍", "開除"]},
    7: {"name": "外部威脅感知", "keywords": ["鄭習會", "鄭麗文", "習近平", "兩岸", "訪中"]},
}

# 知識庫路徑
KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "globeedge", "station3b", "knowledge"
)

_llm_cache: dict[str, dict] = {}
_CACHE_FILE = "results/rag_llm_cache.json"


def _load_cache():
    global _llm_cache
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _llm_cache = json.load(f)
        logger.info(f"  LLM cache loaded: {len(_llm_cache)} entries")


def _save_cache():
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_llm_cache, f, ensure_ascii=False)


def load_knowledge(dim_idx: int) -> str:
    """載入維度的知識文件。"""
    dim_names = {
        0: "dim0_政府信任度", 1: "dim1_制度公信力",
        2: "dim2_社會公平感", 3: "dim3_經濟焦慮度",
        4: "dim4_對美信任度", 5: "dim5_政治改革意願",
        6: "dim6_群體凝聚度", 7: "dim7_外部威脅感知",
    }
    fname = dim_names.get(dim_idx, f"dim{dim_idx}")
    path = os.path.join(KNOWLEDGE_DIR, f"{fname}.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


def rag_classify_article(
    title: str, push: int, boo: int,
    dim_idx: int, knowledge: str,
) -> dict:
    """用 RAG + LLM 判斷單篇文章。"""
    cache_key = hashlib.md5(f"{title}:dim{dim_idx}".encode()).hexdigest()
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    dim_name = DIM_KEYWORDS.get(dim_idx, {}).get("name", f"dim{dim_idx}")

    # 取知識文件的關鍵段落（限 500 字避免 context 過長）
    context_snippet = knowledge[:500] if knowledge else "（無語境資料）"

    prompt = f"""/no_think
你是台灣 PTT 政治文化的專家。

以下是相關的 PTT 語境說明：
{context_snippet}

請判斷以下 PTT 文章對「{dim_name}」的真實立場：

文章標題：{title}
推文數：{push}  噓文數：{boo}

回答 JSON（只回 JSON，不要其他文字）：
{{"is_sarcasm": true或false, "stance": "positive"或"negative"或"neutral", "confidence": 0到1的小數}}"""

    try:
        r = httpx.post(OLLAMA_CHAT, json={
            "model": CHAT_MODEL,
            "stream": False,
            "options": {"temperature": 0.05},
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=60)
        r.raise_for_status()
        raw = r.json().get("message", {}).get("content", "")
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        match = re.search(r"\{[^}]+\}", raw)
        if match:
            result = json.loads(match.group())
        else:
            result = {"is_sarcasm": False, "stance": "neutral", "confidence": 0.3}
    except Exception as e:
        logger.debug(f"LLM error: {e}")
        result = {"is_sarcasm": False, "stance": "neutral", "confidence": 0.0}

    _llm_cache[cache_key] = result
    return result


def fetch_articles(dim_idx: int) -> list[dict]:
    """從 DB 取文章。"""
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
                "url": a.url, "title": a.title, "board": a.board,
                "push": a.push_count or 0, "boo": a.boo_count or 0,
                "arrow": a.arrow_count or 0,
                "day": (dt.date() - START.date()).days,
            })
    return results


def main():
    os.makedirs("results", exist_ok=True)
    _load_cache()

    logger.info("=" * 60)
    logger.info("  Station 3b：RAG 語境反串偵測（完整執行）")
    logger.info("=" * 60)

    # Phase B: 載入知識庫
    logger.info("\n── Phase B: 載入知識庫 ──")
    knowledge_cache = {}
    for dim_idx in DIM_KEYWORDS:
        k = load_knowledge(dim_idx)
        knowledge_cache[dim_idx] = k
        logger.info(f"  dim{dim_idx}: {len(k)} chars loaded")

    # Phase C: RAG 分類
    logger.info("\n── Phase C: RAG 分類 ──")
    all_results = {}
    total_articles = 0
    total_sarcasm = 0

    for dim_idx, info in DIM_KEYWORDS.items():
        logger.info(f"\ndim{dim_idx} {info['name']}")
        articles = fetch_articles(dim_idx)
        logger.info(f"  文章數：{len(articles)}")
        knowledge = knowledge_cache.get(dim_idx, "")

        genuine = []
        sarcasm = []
        for i, a in enumerate(articles):
            result = rag_classify_article(
                a["title"], a["push"], a["boo"], dim_idx, knowledge,
            )
            a["rag"] = result
            if result.get("is_sarcasm"):
                sarcasm.append(a)
            else:
                genuine.append(a)

            if (i + 1) % 50 == 0:
                logger.info(f"    {i+1}/{len(articles)} done")
                _save_cache()

        _save_cache()
        total_articles += len(articles)
        total_sarcasm += len(sarcasm)

        # 推噓比對比
        gp = sum(a["push"] for a in genuine)
        gb = sum(a["boo"] for a in genuine)
        sp = sum(a["push"] for a in sarcasm)
        sb = sum(a["boo"] for a in sarcasm)

        logger.info(f"  GENUINE: {len(genuine)}  push:boo={gp}:{gb}")
        logger.info(f"  SARCASM: {len(sarcasm)}  push:boo={sp}:{sb}")

        all_results[dim_idx] = {
            "total": len(articles),
            "genuine": len(genuine),
            "sarcasm": len(sarcasm),
            "sarcasm_ratio": round(len(sarcasm) / max(len(articles), 1), 3),
            "genuine_urls": [a["url"] for a in genuine],
            "sarcasm_urls": [a["url"] for a in sarcasm],
        }

        # 抽樣 5 篇 sarcasm
        import random
        random.seed(42)
        sample = random.sample(sarcasm, min(5, len(sarcasm)))
        for j, a in enumerate(sample):
            r = a["rag"]
            logger.info(f"    SARCASM [{j+1}] {a['title'][:45]}")
            logger.info(f"      推{a['push']} 噓{a['boo']} stance={r['stance']} conf={r['confidence']}")

    logger.info(f"\n── Phase C 摘要 ──")
    logger.info(f"  Total: {total_articles} articles, {total_sarcasm} sarcasm ({total_sarcasm/max(total_articles,1)*100:.0f}%)")

    # Phase D: 輸出 + 存檔
    output = {
        "method": "RAG + LLM (qwen3.5:9b) with PTT cultural context",
        "dimensions": {str(k): v for k, v in all_results.items()},
        "total_articles": total_articles,
        "total_sarcasm": total_sarcasm,
        "sarcasm_ratio": round(total_sarcasm / max(total_articles, 1), 3),
    }
    with open("results/station3b_rag.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"\n報告：results/station3b_rag.json")
    logger.info(f"LLM cache: {len(_llm_cache)} entries saved")


if __name__ == "__main__":
    main()
