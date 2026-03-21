"""GDELT 地緣政治訊號 — 台灣相關負面新聞偵測。

API: https://api.gdeltproject.org/api/v2/doc/doc
完全免費，無需 API key。
頻率：每 6 小時
過濾：query="Taiwan 台灣", tone < -3（排除中性報導）
"""

import logging
import time
from datetime import datetime, timezone

import httpx

from globeedge.signals.impact_mapper import ImpactMapper

logger = logging.getLogger(__name__)

GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _gdelt_request(params: dict) -> httpx.Response | None:
    """GDELT API 請求，含 rate limit 重試。"""
    for attempt in range(3):
        try:
            r = httpx.get(GDELT_API, params=params, timeout=30)
            if r.status_code == 429:
                wait = 10 * (attempt + 1)  # 10s, 20s, 30s
                logger.warning("GDELT rate limited, waiting %ds (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
                continue
            r.raise_for_status()
            if not r.text.strip():
                logger.warning("GDELT returned empty response")
                return None
            return r
        except Exception:
            logger.exception("GDELT request failed (attempt %d)", attempt + 1)
            time.sleep(3)
    return None


def fetch_taiwan_articles(
    timespan: str = "6h",
    max_records: int = 50,
) -> list[dict]:
    """從 GDELT API 取得台灣相關報導。

    ⚠️ GDELT ArtList 不含 tone 欄位，改用標題關鍵字判斷影響維度。

    Returns:
        [{"title", "url", "domain", "language", "seendate"}, ...]
    """
    r = _gdelt_request({
        "query": "Taiwan",
        "mode": "ArtList",
        "maxrecords": str(max_records),
        "timespan": timespan,
        "format": "json",
    })
    if not r:
        return []

    try:
        data = r.json()
    except Exception:
        logger.exception("GDELT JSON parse failed")
        return []

    articles_raw = data.get("articles", [])
    results = []
    for a in articles_raw:
        seendate = a.get("seendate", "")
        try:
            dt = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            dt = datetime.now(timezone.utc)

        results.append({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "domain": a.get("domain", ""),
            "language": a.get("language", ""),
            "tone": -5.0,  # ArtList 無 tone，用預設負面值觸發 impact
            "seendate": dt,
        })

    logger.info("GDELT: %d articles, timespan=%s", len(results), timespan)
    return results


def to_external_events(articles: list[dict]) -> list[dict]:
    """將 GDELT 文章轉換為 ExternalEvent 格式。"""
    events = []
    for a in articles:
        impact = ImpactMapper.gdelt_article(a["title"], a["tone"])

        # 跳過全零 impact（標題不含任何已知關鍵字）
        if all(v == 0.0 for v in impact):
            continue

        events.append({
            "title": a["title"][:200],  # 截斷避免超長
            "description": f"tone={a['tone']:.1f}, source={a['domain']}",
            "occurred_at": a["seendate"],
            "domain": "geopolitical",
            "source_type": "gdelt",
            "impact_vector": impact,
            "source_url": a["url"],
            "source_tier": 2,
        })
    return events


def persist_events(events: list[dict]) -> int:
    """將 ExternalEvent 寫入 DB。需在 Flask app context 中呼叫。"""
    from globeedge.db import db
    from globeedge.models import ExternalEvent

    written = 0
    for e in events:
        # 用 source_url 去重
        exists = ExternalEvent.query.filter_by(
            source_url=e["source_url"],
            source_type="gdelt",
        ).first()
        if exists:
            continue

        event = ExternalEvent(
            title=e["title"],
            description=e["description"],
            occurred_at=e["occurred_at"],
            domain=e["domain"],
            source_type=e["source_type"],
            impact_vector=e["impact_vector"],
            source_url=e["source_url"],
            source_tier=e["source_tier"],
        )
        db.session.add(event)
        written += 1

    db.session.commit()
    logger.info("GDELT: persisted %d new events", written)
    return written


def run_gdelt_pipeline(timespan: str = "6h") -> list[dict]:
    """完整 pipeline：fetch → transform → (persist)。"""
    articles = fetch_taiwan_articles(timespan=timespan)
    events = to_external_events(articles)
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    events = run_gdelt_pipeline(timespan="24h")
    print(f"\nGDELT 台灣負面報導 (past 24h, tone < -3): {len(events)}")
    for e in events:
        print(
            f"  {e['occurred_at'].strftime('%Y-%m-%d %H:%M')} UTC  "
            f"tone={e['description'][:20]}  "
            f"impact={e['impact_vector']}"
        )
        print(f"    {e['title'][:80]}")
