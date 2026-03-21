"""Bluesky 爬蟲 — AT Protocol 公開 API，抽取意見領袖互動關係。

用途：W 矩陣補充（weight_type = behavioral）
API 完全公開，不需要 API key。

帳號探勘策略：
  1. TW_KOL_HANDLES — 手動策展的台灣相關意見領袖
  2. discover_taiwan_accounts() — 用 searchActors + getProfiles 自動發現
  3. fetch_starter_pack_members() — 從 Starter Pack 批量取得帳號

⚠️ searchPosts API 在台灣被 CDN 403，所以用 searchActors 替代。
"""

import logging
import time
from collections import Counter

import httpx

logger = logging.getLogger(__name__)

BSKY_PUBLIC_API = "https://public.api.bsky.app/xrpc"

# ── 台灣重點追蹤帳號（手動策展） ─────────────────────────
# 篩選條件：(1) 台灣政治/安全/媒體相關 (2) 有活躍回覆互動
TW_KOL_HANDLES = [
    # 記者 / 媒體人
    "brianhioe.bsky.social",       # New Bloom 主編，台灣社運
    "emilyzfeng.bsky.social",      # NPR 駐中台記者
    "aliceysu.bsky.social",        # Economist 中台線記者
    "vivianwu.bsky.social",        # 大聲姐，YouTube 媒體
    "suika.bsky.social",           # Tokyo Review 編輯
    # 學者 / 智庫分析師
    "kuorum.bsky.social",          # Raymond Kuo 郭泓均，亞洲安全
    "chen-yenhan.bsky.social",     # 陳彥翰，Georgetown 台灣國防
    "lnachman32.bsky.social",      # Lev Nachman，台大政治學
    "bglaser.bsky.social",         # Bonnie Glaser，German Marshall Fund
    "kerim.one",                   # 傅可恩，台灣人類學家
    "elifriedman.bsky.social",     # Eli Friedman，Cornell 中國勞工
    # 科技 / 跨域分析
    "aisupremacy.bsky.social",     # Michael Spencer，在台科技分析師
    "lokman.org",                  # Lokman Tsui，科技與人權
    "elisewang.bsky.social",       # 中世紀法律史 + 陰謀論研究
    "sensehofstede.nl",            # Sense Hofstede，中國分析
]

# 搜尋關鍵字（用於 discover_taiwan_accounts）
_DISCOVERY_KEYWORDS = [
    "台灣", "Taiwan", "聯合報", "中央社", "ETtoday", "自由時報",
    "三立", "TVBS", "中時", "風傳媒", "報導者", "立委", "記者",
    "taiwan news", "taipei", "taiwan media", "taiwan politics",
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


# ── 帳號探勘 ──────────────────────────────────────────────

def discover_taiwan_accounts(
    keywords: list[str] | None = None,
    min_posts: int = 10,
    min_followers: int = 500,
) -> list[dict]:
    """用 searchActors + getProfiles 自動發現台灣相關帳號。

    Returns:
        [{"handle": ..., "name": ..., "followers": ..., "posts": ...}, ...]
    """
    if keywords is None:
        keywords = _DISCOVERY_KEYWORDS

    # Step 1: 用 searchActors 收集候選 handle
    candidates: set[str] = set()
    for kw in keywords:
        try:
            r = httpx.get(
                f"{BSKY_PUBLIC_API}/app.bsky.actor.searchActors",
                params={"q": kw, "limit": 25},
                timeout=10,
            )
            if r.status_code == 200:
                for a in r.json().get("actors", []):
                    h = a.get("handle", "")
                    if h:
                        candidates.add(h)
        except Exception:
            logger.debug("searchActors failed for keyword %s", kw)
        time.sleep(0.2)

    logger.info("discover: %d candidates from %d keywords", len(candidates), len(keywords))

    # Step 2: 批量 getProfiles（每次最多 25 個）
    results: list[dict] = []
    candidate_list = list(candidates)
    for i in range(0, len(candidate_list), 25):
        batch = candidate_list[i : i + 25]
        try:
            r = httpx.get(
                f"{BSKY_PUBLIC_API}/app.bsky.actor.getProfiles",
                params=[("actors", h) for h in batch],
                timeout=15,
            )
            if r.status_code == 200:
                for p in r.json().get("profiles", []):
                    pc = p.get("postsCount", 0) or 0
                    fc = p.get("followersCount", 0) or 0
                    if pc >= min_posts and fc >= min_followers:
                        results.append({
                            "handle": p.get("handle"),
                            "name": p.get("displayName", ""),
                            "followers": fc,
                            "posts": pc,
                            "description": (p.get("description") or "")[:100],
                        })
        except Exception:
            logger.debug("getProfiles failed for batch starting at %d", i)
        time.sleep(0.3)

    results.sort(key=lambda x: -x["followers"])
    logger.info("discover: %d accounts pass filters (posts>=%d, followers>=%d)",
                len(results), min_posts, min_followers)
    return results


def fetch_starter_pack_members(pack_uri: str) -> list[str]:
    """從 Starter Pack 取得成員帳號清單。

    pack_uri 格式: at://did:plc:xxx/app.bsky.graph.starterpack/xxx
    """
    try:
        r = httpx.get(
            f"{BSKY_PUBLIC_API}/app.bsky.graph.getStarterPack",
            params={"starterPack": pack_uri},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        items = (
            data.get("starterPack", {})
            .get("list", {})
            .get("items", [])
        )
        handles = [m.get("subject", {}).get("handle", "") for m in items]
        handles = [h for h in handles if h]
        logger.info("starter pack %s: %d members", pack_uri[:50], len(handles))
        return handles
    except Exception:
        logger.exception("failed to fetch starter pack %s", pack_uri)
        return []


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if "--discover" in sys.argv:
        # 探勘模式：自動發現台灣帳號
        accounts = discover_taiwan_accounts()
        print(f"\n{'='*70}")
        print(f"發現 {len(accounts)} 個台灣相關帳號（>=10 posts, >=500 followers）")
        print(f"{'='*70}")
        for a in accounts:
            print(
                f"  {a['handle']:50s}  "
                f"f={a['followers']:6d}  p={a['posts']:5d}  "
                f"{a['name']}"
            )
    else:
        # 正常 pipeline 模式
        edges = run_bluesky_pipeline()
        for e in edges:
            print(
                f"  {e['source']} → {e['target']}  "
                f"raw={e['weight_raw']}  w={e.get('weight', '?')}  "
                f"type={e.get('weight_type')}"
            )
