"""PTT 爬蟲 — 八卦板 / 政黑板推噓分析，抽取輿論互動關係。

用途：W 矩陣核心（weight_type = behavioral / structural）
台灣本土輿論的最重要資料源。

⚠️ 已知坑：
  1. over18 cookie — 八卦板必須帶 cookies={"over18": "1"}
  2. 刪除文章 — 列表頁有 "(本文已被刪除)" 要過濾
  3. TLS fingerprint — PTT 擋 httpx/requests，需用 curl_cffi impersonate='chrome'
  4. 爬取頻率 — 每次請求間隔 0.5s，避免被封鎖
"""

import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

PTT_BASE = "https://www.ptt.cc"

# 目標看板
TARGET_BOARDS = {
    "Gossiping":    "八卦板（主力）",
    "HatePolitics": "政黑板（政治輿論）",
    "Military":     "軍事板（台海信號）",
    "Stock":        "股票板（金融情緒）",
}

# 請求間隔（秒）
REQUEST_DELAY = 0.5

# ── 解析 regex ────────────────────────────────────────────
_RE_ARTICLE_LINK = re.compile(r'href="(/bbs/\w+/M\.\d+\.A\.\w+\.html)"')
_RE_DELETED = re.compile(r"(已被刪除|本文已被)")
_RE_NREC = re.compile(r'<span class="hl f\d">(\d+)</span>')
_RE_TITLE_TAG = re.compile(
    r'<div class="title">\s*(?:<a[^>]+>(.+?)</a>|(.+?))\s*</div>', re.DOTALL
)
_RE_META = re.compile(r'<span class="article-meta-value">([^<]+)</span>')
_RE_PUSH = re.compile(
    r'<span class="hl push-tag">(推|噓|→)\s*</span>'
    r'<span class="f3 hl push-userid">([^<]+)</span>'
    r'<span class="f3 push-content">: ([^<]*)</span>'
)
_RE_PREV_PAGE = re.compile(r'href="/bbs/\w+/index(\d+)\.html"[^>]*>.*?上頁', re.DOTALL)


@dataclass
class PttArticle:
    """PTT 文章解析結果。"""
    url: str
    board: str
    author: str
    title: str
    date: str
    pushes: list[tuple[str, str, str]]  # (tag, userid, content)
    push_count: int  # 推
    boo_count: int   # 噓
    arrow_count: int # →

    @property
    def net_score(self) -> int:
        return self.push_count - self.boo_count

    @property
    def total_interactions(self) -> int:
        return self.push_count + self.boo_count + self.arrow_count


def _fetch(url: str) -> str | None:
    """用 curl_cffi 模擬 Chrome TLS 發送請求。"""
    try:
        r = cffi_requests.get(
            url,
            cookies={"over18": "1"},
            impersonate="chrome",
            timeout=15,
        )
        if r.status_code == 200:
            return r.text
        logger.warning("HTTP %d for %s", r.status_code, url)
        return None
    except Exception:
        logger.exception("failed to fetch %s", url)
        return None


def fetch_article_list(
    board: str, pages: int = 3
) -> list[dict]:
    """爬取看板最新 N 頁的文章列表。

    Returns:
        [{"url": ..., "title": ..., "nrec": ...}, ...]
    """
    articles = []
    # 先取最新頁
    html = _fetch(f"{PTT_BASE}/bbs/{board}/index.html")
    if not html:
        return articles

    current_page = None
    prev_match = _RE_PREV_PAGE.search(html)
    if prev_match:
        current_page = int(prev_match.group(1)) + 1

    pages_to_fetch = [html]
    if current_page and pages > 1:
        for i in range(1, pages):
            page_idx = current_page - i
            if page_idx < 1:
                break
            time.sleep(REQUEST_DELAY)
            page_html = _fetch(f"{PTT_BASE}/bbs/{board}/index{page_idx}.html")
            if page_html:
                pages_to_fetch.append(page_html)

    for page_html in pages_to_fetch:
        links = _RE_ARTICLE_LINK.findall(page_html)
        nrecs = _RE_NREC.findall(page_html)

        for i, link in enumerate(links):
            # 跳過已刪除文章
            articles.append({
                "url": f"{PTT_BASE}{link}",
                "board": board,
                "nrec": int(nrecs[i]) if i < len(nrecs) else 0,
            })

    logger.info("board %s: %d articles from %d pages", board, len(articles), len(pages_to_fetch))
    return articles


def parse_article(url: str, board: str = "") -> PttArticle | None:
    """解析單篇 PTT 文章，抽取推噓資料。"""
    html = _fetch(url)
    if not html:
        return None

    # 元資料
    meta = _RE_META.findall(html)
    author = meta[0] if len(meta) >= 1 else "unknown"
    title = meta[2] if len(meta) >= 3 else "unknown"
    date = meta[3] if len(meta) >= 4 else ""

    # 清理 author（去掉暱稱部分 "userid (nickname)"）
    author = author.split("(")[0].strip()

    # 推噓
    pushes = _RE_PUSH.findall(html)
    c = Counter(tag for tag, _, _ in pushes)

    return PttArticle(
        url=url,
        board=board or (meta[1] if len(meta) >= 2 else ""),
        author=author,
        title=title,
        date=date,
        pushes=[(tag, uid.strip(), content) for tag, uid, content in pushes],
        push_count=c.get("推", 0),
        boo_count=c.get("噓", 0),
        arrow_count=c.get("→", 0),
    )


def extract_influence_edges(articles: list[PttArticle]) -> list[dict]:
    """從推噓關係抽取 W 矩陣邊。

    邏輯：
      - 推文者 → 原 PO 作者：推文者受原 PO 影響
        source = 原 PO (影響者)，target = 推文者 (被影響者)
      - 同一篇文章多人推 → 這些推文者彼此也有弱互動
      - 噓文反向：噓文者對原 PO 的觀點持反對態度，但仍然是互動

    weight_type:
      - 推 → behavioral（正向互動）
      - 噓 → behavioral（負向互動，weight 為負）
    """
    # 聚合 (source_author, target_user) → {push: N, boo: N}
    pair_data: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"push": 0, "boo": 0, "arrow": 0}
    )

    for article in articles:
        if article.total_interactions == 0:
            continue
        op = article.author
        for tag, uid, _ in article.pushes:
            if uid == op:
                continue  # 自推不算
            if tag == "推":
                pair_data[(op, uid)]["push"] += 1
            elif tag == "噓":
                pair_data[(op, uid)]["boo"] += 1
            else:
                pair_data[(op, uid)]["arrow"] += 1

    edges = []
    for (source, target), counts in pair_data.items():
        # 淨互動：推 - 噓（可以是負的）
        net = counts["push"] - counts["boo"]
        raw = counts["push"] + counts["boo"] + counts["arrow"]
        edges.append({
            "source": source,       # 原 PO（影響者）
            "target": target,       # 推噓者（被影響者）
            "weight_raw": raw,
            "weight_net": net,       # 正=推為主 負=噓為主
            "weight_type": "behavioral",
            "push": counts["push"],
            "boo": counts["boo"],
        })

    return edges


def normalize_weights(edges: list[dict]) -> list[dict]:
    """正規化 weight_raw → weight [0, 1]，保留正負號。"""
    if not edges:
        return edges
    max_w = max(e["weight_raw"] for e in edges)
    if max_w == 0:
        return edges
    for e in edges:
        magnitude = e["weight_raw"] / max_w
        sign = 1 if e["weight_net"] >= 0 else -1
        e["weight"] = round(sign * magnitude, 4)
    return edges


def persist_edges(edges: list[dict], project_id: str) -> int:
    """將 PTT behavioral edges 寫入 influence_edges 表。

    PTT user ID → Agent.name 比對。
    需在 Flask app context 中呼叫。
    """
    from globeedge.db import db
    from globeedge.models import Agent, InfluenceEdge

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
            confidence=0.6,  # PTT 推噓是明確互動，信心較高
        )
        db.session.add(edge)
        written += 1

    db.session.commit()
    return written


def run_ptt_pipeline(
    boards: list[str] | None = None,
    pages_per_board: int = 3,
    min_interactions: int = 5,
    project_id: str | None = None,
) -> list[dict]:
    """完整 pipeline：爬取看板 → 解析文章 → 抽取邊 → 正規化 → (寫入 DB)。

    Args:
        boards: 要爬的看板，預設 Gossiping + HatePolitics
        pages_per_board: 每個看板爬幾頁
        min_interactions: 最少互動數才解析單篇
        project_id: 如有提供，寫入 DB
    """
    if boards is None:
        boards = ["Gossiping", "HatePolitics"]

    all_articles: list[PttArticle] = []

    for board in boards:
        article_list = fetch_article_list(board, pages=pages_per_board)

        # 只解析有足夠互動的文章
        worth_parsing = [a for a in article_list if a.get("nrec", 0) >= min_interactions]
        logger.info(
            "board %s: %d articles, %d worth parsing (nrec >= %d)",
            board, len(article_list), len(worth_parsing), min_interactions,
        )

        for article_info in worth_parsing:
            time.sleep(REQUEST_DELAY)
            article = parse_article(article_info["url"], board)
            if article and article.total_interactions > 0:
                all_articles.append(article)
                logger.debug(
                    "  %s: %d interactions (推%d 噓%d →%d)",
                    article.title[:30], article.total_interactions,
                    article.push_count, article.boo_count, article.arrow_count,
                )

    logger.info("total parsed articles: %d", len(all_articles))

    # 抽取邊
    all_edges = extract_influence_edges(all_articles)
    all_edges = normalize_weights(all_edges)
    logger.info("ptt total edges: %d", len(all_edges))

    if project_id:
        n = persist_edges(all_edges, project_id)
        logger.info("ptt persisted %d edges to DB", n)

    return all_edges


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    boards = sys.argv[1:] if len(sys.argv) > 1 else ["HatePolitics"]

    print(f"爬取看板: {boards}")
    edges = run_ptt_pipeline(boards=boards, pages_per_board=2, min_interactions=3)

    # 摘要
    print(f"\n{'='*70}")
    print(f"共 {len(edges)} 條邊")
    print(f"{'='*70}")

    # Top edges by weight_raw
    edges.sort(key=lambda e: -e["weight_raw"])
    for e in edges[:20]:
        sign = "+" if e.get("weight_net", 0) >= 0 else "-"
        print(
            f"  {e['source']:15s} → {e['target']:15s}  "
            f"raw={e['weight_raw']:2d}  net={sign}{abs(e.get('weight_net', 0)):2d}  "
            f"w={e.get('weight', '?'):+.4f}  "
            f"推={e.get('push', 0)} 噓={e.get('boo', 0)}"
        )
