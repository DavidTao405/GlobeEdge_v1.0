"""Station 3b：RAG 語境輔助反串偵測。

比較 Hohwy 純數學（3a）vs RAG 語境輔助（3b）。
回答：「台灣 PTT 反串識別需要文化語境嗎？」

用法：
    python scripts/rag_sarcasm.py
    python scripts/rag_sarcasm.py --max-articles 100   # 限制文章數（快速測試）
    python scripts/rag_sarcasm.py --dim dim0           # 只跑特定維度
"""

import argparse
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
OLLAMA_EMBED = "http://localhost:11434/api/embed"
EMBED_MODEL = "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest"
CHAT_MODEL = "qwen3.5:9b"

START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)

# ── PTT 語境知識庫（8 維度）────────────────────────────────

CONTEXT_DOCS = {
    "dim0": {
        "name": "政府信任度",
        "context": """【PTT 政黑板文化 — 政府信任度】
常見反串格式：
- 用誇張正面語氣嘲諷（「執政太讚了」「台灣要起飛了」= 反諷）
- 引用官員發言加「所以...」接諷刺結論
- 推文「推」跟在諷刺文後 = 認同諷刺，不是真的支持政府

真誠批評政府的特徵：
- 直接指出具體政策失敗
- 使用數據或新聞佐證
- 語氣憤怒但有論點

反串支持政府的特徵：
- 語氣過度正面，不合比例
- 沒有具體事實支撐
- 常搭配「笑死」「可憐哪」等嘲諷詞"""
    },
    "dim1": {
        "name": "制度公信力",
        "context": """【PTT — 制度公信力（司法/立法）】
常見反串格式：
- 「法院認證的XX」= 諷刺法院判決不公
- 「司法獨立大家都知道」= 反諷司法不獨立
- 推 = 認同諷刺司法，不是信任司法

真誠討論制度的特徵：
- 引用法條或判決書內容
- 比較不同案件的判決標準
- 語氣可能激動但有法律依據"""
    },
    "dim2": {
        "name": "社會公平感",
        "context": """【PTT — 社會公平感】
常見反串：「有錢就是正義」「窮人自己不努力」= 諷刺社會不公
真誠表達：直接訴說個人經歷或引用貧富差距數據"""
    },
    "dim3": {
        "name": "經濟焦慮度",
        "context": """【PTT — 經濟焦慮度】
常見反串：「台灣經濟火車頭」「GDP 世界最好」= 反諷經濟困境
真誠焦慮：討論房價、薪資、物價的具體數字"""
    },
    "dim4": {
        "name": "對美同盟信任度",
        "context": """【PTT — 對美同盟信任度】
常見反串：「美國爸爸」「靠美國就夠了」= 諷刺過度依賴美國
反串支持美國：語氣像信徒，沒有批判性思考
真誠分析：討論具體軍售案、外交政策利弊"""
    },
    "dim5": {
        "name": "政治改革意願",
        "context": """【PTT — 政治改革/罷免】
常見反串：「罷免是民主的表現（笑）」= 諷刺罷免被政治操弄
真誠支持罷免：論述為何特定政治人物應被罷免
真誠反對罷免：論述罷免程序不當或動機不純"""
    },
    "dim6": {
        "name": "群體凝聚度",
        "context": """【PTT — 群體凝聚度（政黨內部/社會團結）】
常見反串：「台灣最團結」= 反諷社會撕裂嚴重
「XX黨最有紀律」= 反諷黨內鬥爭
真誠討論：分析黨內路線分歧或社會對立原因"""
    },
    "dim7": {
        "name": "外部威脅感知",
        "context": """【PTT — 外部威脅/兩岸】
常見反串：「中共不會打台灣大家放心」= 反諷掉以輕心
「一家人不說兩家話」= 可能是真誠也可能是嘲諷，要看上下文
真誠分析：引用軍事部署、外交動態的具體資訊"""
    },
}

# 維度對應的搜尋關鍵字
DIM_KEYWORDS = {
    "dim0": ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"],
    "dim1": ["柯文哲", "京華城", "判決", "司法", "違憲"],
    "dim5": ["罷免", "民主", "改革", "青鳥"],
    "dim6": ["黃國昌", "民眾黨", "李貞秀", "黨籍", "開除"],
    "dim7": ["鄭習會", "鄭麗文", "習近平", "兩岸", "訪中"],
}

# ── ChromaDB 知識庫 ───────────────────────────────────────

def build_chroma_collection():
    """建立 ChromaDB 向量知識庫。"""
    import chromadb
    client = chromadb.Client()

    # 刪除舊的（如果存在）
    try:
        client.delete_collection("ptt_context")
    except Exception:
        pass

    collection = client.create_collection(
        name="ptt_context",
        metadata={"hnsw:space": "cosine"},
    )

    docs = []
    ids = []
    metadatas = []
    for dim_key, info in CONTEXT_DOCS.items():
        # 切成段落
        paragraphs = [p.strip() for p in info["context"].split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            doc_id = f"{dim_key}_{i}"
            docs.append(para)
            ids.append(doc_id)
            metadatas.append({"dim": dim_key, "dim_name": info["name"]})

    # 用 Ollama embedding
    embeddings = []
    for doc in docs:
        emb = _get_embedding(doc)
        embeddings.append(emb.tolist())

    collection.add(
        documents=docs,
        ids=ids,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    logger.info(f"  ChromaDB: {len(docs)} 段落")
    return collection


def _get_embedding(text: str) -> np.ndarray:
    """Ollama embedding。"""
    try:
        r = httpx.post(OLLAMA_EMBED, json={
            "model": EMBED_MODEL, "input": text[:500],
        }, timeout=30)
        r.raise_for_status()
        embs = r.json().get("embeddings", [])
        if embs:
            return np.array(embs[0])
    except Exception:
        pass
    return np.zeros(1536)


# ── RAG 分類 ──────────────────────────────────────────────

_llm_cache: dict[str, dict] = {}


def rag_classify(
    title: str,
    push: int, boo: int,
    dim_key: str,
    collection,
) -> dict:
    """用 RAG + LLM 判斷文章立場。"""
    cache_key = hashlib.md5(f"{title}:{dim_key}".encode()).hexdigest()
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    dim_name = CONTEXT_DOCS[dim_key]["name"]

    # RAG 查詢
    query_emb = _get_embedding(title)
    results = collection.query(
        query_embeddings=[query_emb.tolist()],
        n_results=3,
        where={"dim": dim_key},
    )
    retrieved = "\n".join(results["documents"][0]) if results["documents"] else ""

    prompt = f"""/no_think
你是台灣 PTT 文化的專家。

以下是相關的 PTT 語境說明：
{retrieved}

請判斷以下文章對「{dim_name}」的真實立場：

文章標題：{title}
推文數：{push}  噓文數：{boo}

回答 JSON（只回 JSON，不要其他文字）：
{{"is_sarcasm": true/false, "stance": "positive/negative/neutral", "confidence": 0.0-1.0}}"""

    try:
        r = httpx.post(OLLAMA_CHAT, json={
            "model": CHAT_MODEL,
            "stream": False,
            "options": {"temperature": 0.05},
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=60)
        r.raise_for_status()
        raw = r.json().get("message", {}).get("content", "")
        # 清理 think tags
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        # 找 JSON
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


# ── 主要流程 ──────────────────────────────────────────────

def fetch_articles(dim_key: str) -> list[dict]:
    """取 DB 文章。"""
    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    keywords = DIM_KEYWORDS.get(dim_key, [])
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
                "board": a.board,
                "push": a.push_count or 0,
                "boo": a.boo_count or 0,
                "day": (dt.date() - START.date()).days,
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="RAG 語境反串偵測")
    parser.add_argument("--dims", default="dim0,dim6,dim7", help="要處理的維度")
    parser.add_argument("--max-articles", type=int, default=0, help="每維度最大文章數")
    parser.add_argument("--output", default="results/rag_sarcasm.json")
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    dims = [d.strip() for d in args.dims.split(",")]

    logger.info("=" * 60)
    logger.info("  Station 3b：RAG 語境輔助反串偵測")
    logger.info(f"  維度：{dims}")
    logger.info("=" * 60)

    # Step 1: 建 ChromaDB
    logger.info("\nStep 1: 建立 ChromaDB 知識庫")
    collection = build_chroma_collection()

    # Step 2: 對每個維度分類
    all_results = {}
    for dim_key in dims:
        if dim_key not in CONTEXT_DOCS:
            logger.info(f"  跳過 {dim_key}（無知識文件）")
            continue

        logger.info(f"\n{'─'*50}")
        logger.info(f"  {dim_key} {CONTEXT_DOCS[dim_key]['name']}")

        articles = fetch_articles(dim_key)
        if args.max_articles > 0:
            articles = articles[:args.max_articles]
        logger.info(f"  文章數：{len(articles)}")

        genuine = []
        sarcasm = []
        for i, a in enumerate(articles):
            result = rag_classify(a["title"], a["push"], a["boo"], dim_key, collection)
            a["rag"] = result
            if result.get("is_sarcasm"):
                sarcasm.append(a)
            else:
                genuine.append(a)
            if (i + 1) % 20 == 0:
                logger.info(f"    {i+1}/{len(articles)} done")

        logger.info(f"  GENUINE: {len(genuine)}  SARCASM: {len(sarcasm)}")

        # 推噓比對比
        if genuine:
            gp = sum(a["push"] for a in genuine)
            gb = sum(a["boo"] for a in genuine)
            logger.info(f"  GENUINE push:boo = {gp}:{gb}")
        if sarcasm:
            sp = sum(a["push"] for a in sarcasm)
            sb = sum(a["boo"] for a in sarcasm)
            logger.info(f"  SARCASM push:boo = {sp}:{sb}")

        # 人工驗證抽樣
        import random
        random.seed(42)
        sample_s = random.sample(sarcasm, min(args.sample, len(sarcasm)))
        logger.info(f"\n  SARCASM 抽樣 ({len(sample_s)} 篇):")
        for j, a in enumerate(sample_s):
            r = a["rag"]
            logger.info(f"    [{j+1}] {a['title'][:50]}")
            logger.info(f"         推{a['push']} 噓{a['boo']}  "
                        f"sarcasm={r['is_sarcasm']}  stance={r['stance']}  "
                        f"conf={r['confidence']}")

        all_results[dim_key] = {
            "total": len(articles),
            "genuine": len(genuine),
            "sarcasm": len(sarcasm),
            "sarcasm_ratio": round(len(sarcasm) / max(len(articles), 1), 3),
            "genuine_urls": [a["url"] for a in genuine],
            "sarcasm_urls": [a["url"] for a in sarcasm],
        }

    # 輸出
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告：{args.output}")


if __name__ == "__main__":
    main()
