"""Bluesky 爬蟲 — AT Protocol 公開 API，抽取意見領袖互動關係。

用途：W 矩陣補充（weight_type = behavioral）
API 完全公開，不需要 API key。
"""

import logging
from collections import Counter

import httpx

logger = logging.getLogger(__name__)

BSKY_PUBLIC_API = "https://public.api.bsky.app/xrpc"

# 台灣重點追蹤帳號（KOL 節點）
TW_KOL_HANDLES = [
    "bsky.app",            # Bluesky 官方（測試用）
    "jay.bsky.team",       # Bluesky 團隊（測試用，有大量 replies）
    # 台灣帳號（有貼文的）
    "udn.bsky.social",
    "ltn.bsky.social",
    # 在此擴充台灣媒體人、立委、意見領袖 handle
]


def fetch_kol_posts(handle: str, limit: int = 50) -> list[dict]:
    """爬取特定帳號的貼文（含 replies），回傳 feed items。"""
    try:
        r = httpx.get(
            f"{BSKY_PUBLIC_API}/app.bsky.feed.getAuthorFeed",
            params={"actor": handle, "limit": limit},
            timeout=15,
        )
        r.raise_for_status()
        feed = r.json().get("feed", [])
        logger.info("fetched %d posts from %s", len(feed), handle)
        return feed
    except Exception:
        logger.exception("failed to fetch posts for %s", handle)
        return []


def resolve_author_handle(uri: str) -> str | None:
    """從 AT URI (at://did:plc:xxx/app.bsky.feed.post/yyy) 解析出 handle。"""
    if not uri or not uri.startswith("at://"):
        return None
    did = uri.split("/")[2]
    try:
        r = httpx.get(
            f"{BSKY_PUBLIC_API}/app.bsky.actor.getProfile",
            params={"actor": did},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("handle")
    except Exception:
        return None


def extract_influence_edges(feed: list[dict]) -> list[dict]:
    """從回覆和轉發關係抽取 W 矩陣邊。

    A 回覆 B → B 是 source（影響者），A 是 target（被影響者）
    """
    # 先收集所有 reply 關係，聚合同一對 (source, target) 的次數
    pair_counts: Counter = Counter()
    # 用 dict 暫存 parent URI → handle 的解析結果（避免重複 API 呼叫）
    uri_cache: dict[str, str | None] = {}

    for item in feed:
        post = item.get("post", {})
        record = post.get("record", {})
        reply_ref = record.get("reply")

        if not reply_ref:
            continue

        # A (replier) 的 handle
        target_handle = post.get("author", {}).get("handle")
        if not target_handle:
            continue

        # B (被回覆者) 的 parent URI
        parent_uri = reply_ref.get("parent", {}).get("uri", "")

        # 嘗試從 reply 的 parent post 中取得 author
        # 先看 feed 中有沒有 reply.parent 附帶的資料
        reply_parent = item.get("reply", {}).get("parent", {})
        source_handle = reply_parent.get("author", {}).get("handle")

        if not source_handle and parent_uri:
            # 用 URI cache 避免重複解析
            if parent_uri not in uri_cache:
                uri_cache[parent_uri] = resolve_author_handle(parent_uri)
            source_handle = uri_cache[parent_uri]

        if not source_handle or source_handle == target_handle:
            continue

        pair_counts[(source_handle, target_handle)] += 1

    edges = []
    for (source, target), count in pair_counts.items():
        edges.append({
            "source": source,
            "target": target,
            "weight_raw": count,
            "weight_type": "behavioral",
        })

    return edges


def normalize_weights(edges: list[dict]) -> list[dict]:
    """正規化 weight_raw → weight [0, 1]。"""
    if not edges:
        return edges
    max_w = max(e["weight_raw"] for e in edges)
    if max_w == 0:
        return edges
    for e in edges:
        e["weight"] = round(e["weight_raw"] / max_w, 4)
    return edges


def persist_edges(edges: list[dict], project_id: str) -> int:
    """將 behavioral edges 寫入 influence_edges 表。

    source/target 用 handle 比對 Agent.name。
    需在 Flask app context 中呼叫。
    """
    from worldedge.db import db
    from worldedge.models import Agent, InfluenceEdge

    agents = Agent.query.filter_by(project_id=project_id).all()
    name_to_id = {a.name: a.id for a in agents}

    written = 0
    for e in edges:
        src_id = name_to_id.get(e["source"])
        tgt_id = name_to_id.get(e["target"])
        if not src_id or not tgt_id:
            continue
        edge = InfluenceEdge(
            project_id=project_id,
            source_id=src_id,
            target_id=tgt_id,
            weight=e.get("weight", e["weight_raw"] / 10),
            weight_type="behavioral",
            confidence=0.4,  # behavioral 比 structural 信心低
        )
        db.session.add(edge)
        written += 1

    db.session.commit()
    return written


def run_bluesky_pipeline(
    handles: list[str] | None = None,
    project_id: str | None = None,
) -> list[dict]:
    """完整 pipeline：爬取 KOL 貼文 → 抽取邊 → 正規化 → (寫入 DB)。"""
    if handles is None:
        handles = TW_KOL_HANDLES

    all_edges: list[dict] = []
    for handle in handles:
        feed = fetch_kol_posts(handle)
        edges = extract_influence_edges(feed)
        all_edges.extend(edges)
        logger.info("%s: %d edges", handle, len(edges))

    all_edges = normalize_weights(all_edges)
    logger.info("bluesky total edges: %d", len(all_edges))

    if project_id:
        n = persist_edges(all_edges, project_id)
        logger.info("bluesky persisted %d edges to DB", n)

    return all_edges


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    edges = run_bluesky_pipeline()
    for e in edges:
        print(
            f"  {e['source']} → {e['target']}  "
            f"raw={e['weight_raw']}  w={e.get('weight', '?')}  "
            f"type={e.get('weight_type')}"
        )
