"""新聞媒體引用關係爬蟲 — W 矩陣骨架（weight_type = structural）。

用 Crawl4AI + BM25ContentFilter 爬取新聞首頁，
抽取引用了哪些其他媒體名稱，產出 citation edges。
"""

import asyncio
import logging
import re
from collections import Counter

import feedparser
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

logger = logging.getLogger(__name__)

# ── 媒體清單 ──────────────────────────────────────────────
NEWS_SOURCES = {
    "聯合報":   "https://udn.com/news/breaknews/1",
    "自由時報": "https://news.ltn.com.tw",
    "中央社":   "https://www.cna.com.tw",
    "商業周刊": "https://www.businessweekly.com.tw",
    "天下雜誌": "https://www.cw.com.tw",
    "ETtoday":  "https://www.ettoday.net",
    "三立新聞": "https://www.setn.com",
    "TVBS":     "https://news.tvbs.com.tw",
}

# 用來比對內文中出現的媒體名稱（排除自身後）
MEDIA_PATTERNS: dict[str, re.Pattern] = {
    name: re.compile(re.escape(name))
    for name in NEWS_SOURCES
}
# 補充常見別名
_ALIASES = {
    "聯合新聞網": "聯合報",
    "聯合晚報": "聯合報",
    "UDN": "聯合報",
    "udn": "聯合報",
    "LTN": "自由時報",
    "CNA": "中央社",
    "中央通訊社": "中央社",
    "東森新聞": "ETtoday",
    "ettoday": "ETtoday",
    "SETN": "三立新聞",
    "三立": "三立新聞",
    "setn": "三立新聞",
    "天下": "天下雜誌",
    "商周": "商業周刊",
    "tvbs": "TVBS",
}


async def crawl_one(source_name: str, url: str) -> list[dict]:
    """爬取單一媒體首頁，回傳引用邊清單。"""
    config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=BM25ContentFilter(
                user_query="引用 報導 轉載 據 根據 指出 來源",
                bm25_threshold=1.0,
            )
        ),
        exclude_external_links=False,
        wait_until="domcontentloaded",
        page_timeout=30000,
        verbose=False,
    )
    browser_config = BrowserConfig(
        headless=True,
        chrome_channel="chrome",
        extra_args=["--no-sandbox", "--disable-gpu"],
        verbose=False,
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=config)
            if not result.success:
                logger.warning("crawl failed for %s: %s", source_name, result.error_message)
                return []
            md = result.markdown.raw_markdown or ""
            return _extract_citations(source_name, md)
    except Exception:
        logger.exception("crawl error for %s", source_name)
        return []


def _extract_citations(source_name: str, text: str) -> list[dict]:
    """從 markdown 文字中計算引用了哪些其他媒體。"""
    counts: Counter = Counter()

    for media_name in NEWS_SOURCES:
        if media_name == source_name:
            continue
        counts[media_name] += len(MEDIA_PATTERNS[media_name].findall(text))

    # 別名合併
    for alias, canonical in _ALIASES.items():
        if canonical == source_name:
            continue
        found = len(re.findall(re.escape(alias), text))
        if found:
            counts[canonical] += found

    edges = []
    for target, weight_raw in counts.items():
        if weight_raw > 0:
            edges.append({
                "source": source_name,
                "target": target,
                "weight_raw": weight_raw,
            })

    return edges


async def crawl_all_citations() -> list[dict]:
    """爬取所有媒體，回傳全部 citation edges。"""
    all_edges: list[dict] = []
    for name, url in NEWS_SOURCES.items():
        logger.info("crawling %s ...", name)
        edges = await crawl_one(name, url)
        logger.info("  → %d edges found", len(edges))
        all_edges.extend(edges)
    return all_edges


def normalize_weights(edges: list[dict]) -> list[dict]:
    """將 weight_raw（引用次數）正規化到 [0, 1]。"""
    if not edges:
        return edges
    max_w = max(e["weight_raw"] for e in edges)
    if max_w == 0:
        return edges
    for e in edges:
        e["weight"] = round(e["weight_raw"] / max_w, 4)
    return edges


# ── 寫入 DB ─────────────────────────────────────────────
def persist_edges(edges: list[dict], project_id: str) -> int:
    """將 citation edges 寫入 influence_edges 表。

    回傳寫入筆數。需在 Flask app context 中呼叫。
    """
    from worldedge.db import db
    from worldedge.models import Agent, InfluenceEdge

    # 取得 project 下所有 agent 的 name → id 對應
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
            weight_type="structural",
            confidence=0.5,
        )
        db.session.add(edge)
        written += 1

    db.session.commit()
    return written


# ── RSS 快速通道 ─────────────────────────────────────────
# 不需要 headless browser，速度快 10x，也不踩 Windows cp950 問題

RSS_FEEDS = {
    "ETtoday":  {"ettoday_main": "https://feeds.feedburner.com/ettoday/realtime"},
    "中央社":   {"cna_politics": "https://feeds.feedburner.com/rsscna/politics"},
    "自由時報": {"ltn_all": "https://news.ltn.com.tw/rss/all.xml"},
    "聯合報":   {"udn_news": "https://udn.com/rssfeed/news/2/6638?ch=news"},
}


def fetch_rss(source_name: str, feed_key: str | None = None) -> list[dict]:
    """抓取指定媒體的 RSS，回傳文章清單。"""
    feeds = RSS_FEEDS.get(source_name, {})
    if not feeds:
        logger.warning("no RSS feeds for %s", source_name)
        return []

    if feed_key:
        feeds = {feed_key: feeds[feed_key]}

    articles = []
    for fk, url in feeds.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            articles.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "source": source_name,
                "feed_key": fk,
            })
    logger.info("RSS %s: %d articles", source_name, len(articles))
    return articles


def extract_citations_from_rss(articles: list[dict], source_name: str) -> list[dict]:
    """從 RSS 文章的 title + summary 抽取引用關係。"""
    counts: Counter = Counter()

    for article in articles:
        text = article["title"] + " " + article["summary"]

        for media_name in NEWS_SOURCES:
            if media_name == source_name:
                continue
            counts[media_name] += len(MEDIA_PATTERNS[media_name].findall(text))

        for alias, canonical in _ALIASES.items():
            if canonical == source_name:
                continue
            found = len(re.findall(re.escape(alias), text))
            if found:
                counts[canonical] += found

    edges = []
    for target, weight_raw in counts.items():
        if weight_raw > 0:
            edges.append({
                "source": source_name,
                "target": target,
                "weight_raw": weight_raw,
            })
    return edges


def run_rss_pipeline(project_id: str | None = None) -> list[dict]:
    """所有 RSS 來源的 pipeline：抓取 → 解析引用 → 正規化 → (寫入 DB)。"""
    all_edges: list[dict] = []
    for source_name in RSS_FEEDS:
        articles = fetch_rss(source_name)
        edges = extract_citations_from_rss(articles, source_name)
        all_edges.extend(edges)

    all_edges = normalize_weights(all_edges)
    logger.info("RSS total edges: %d", len(all_edges))

    if project_id:
        n = persist_edges(all_edges, project_id)
        logger.info("RSS persisted %d edges to DB", n)

    return all_edges


# ── CLI 入口 ─────────────────────────────────────────────
async def run_pipeline(project_id: str | None = None) -> list[dict]:
    """完整 pipeline：爬取 → 正規化 → (選擇性寫入 DB)。"""
    raw_edges = await crawl_all_citations()
    edges = normalize_weights(raw_edges)
    logger.info("total edges: %d", len(edges))

    if project_id:
        n = persist_edges(edges, project_id)
        logger.info("persisted %d edges to DB", n)

    return edges


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    edges = asyncio.run(run_pipeline())
    for e in edges:
        print(f"  {e['source']} → {e['target']}  raw={e['weight_raw']}  w={e.get('weight', '?')}")
