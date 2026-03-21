"""USGS 地震訊號 — 台灣範圍地震偵測。

API: https://earthquake.usgs.gov/fdsnws/event/1/query
完全免費，無需 API key。
頻率：每小時
過濾：台灣範圍 (lat 21-26, lon 119-123) + magnitude >= 4.5
"""

import logging
from datetime import datetime, timezone, timedelta

import httpx

from worldedge.signals.impact_mapper import ImpactMapper

logger = logging.getLogger(__name__)

USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# 台灣地震範圍
TW_BOUNDS = {
    "minlatitude": 21.0,
    "maxlatitude": 26.0,
    "minlongitude": 119.0,
    "maxlongitude": 123.0,
}

MIN_MAGNITUDE = 4.5


def fetch_taiwan_earthquakes(
    hours: int = 168,  # 預設 7 天
    min_mag: float = MIN_MAGNITUDE,
) -> list[dict]:
    """從 USGS API 取得台灣範圍地震。

    Returns:
        [{"id", "title", "magnitude", "place", "time", "lat", "lon", "url"}, ...]
    """
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": min_mag,
        **TW_BOUNDS,
        "orderby": "time",
    }

    try:
        r = httpx.get(USGS_API, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        logger.exception("USGS API request failed")
        return []

    features = data.get("features", [])
    results = []
    for f in features:
        props = f.get("properties", {})
        coords = f.get("geometry", {}).get("coordinates", [0, 0, 0])
        results.append({
            "id": f.get("id", ""),
            "title": props.get("title", ""),
            "magnitude": props.get("mag", 0),
            "place": props.get("place", ""),
            "time": datetime.fromtimestamp(
                props.get("time", 0) / 1000, tz=timezone.utc
            ),
            "lat": coords[1],
            "lon": coords[0],
            "depth_km": coords[2],
            "url": props.get("url", ""),
        })

    logger.info("USGS: %d earthquakes (>= M%.1f) in Taiwan region, past %dh",
                len(results), min_mag, hours)
    return results


def to_external_events(earthquakes: list[dict]) -> list[dict]:
    """將地震資料轉換為 ExternalEvent 格式。"""
    events = []
    for eq in earthquakes:
        impact = ImpactMapper.earthquake(eq["magnitude"])
        events.append({
            "title": eq["title"],
            "description": (
                f"M{eq['magnitude']} at {eq['place']}, "
                f"depth {eq['depth_km']:.1f}km"
            ),
            "occurred_at": eq["time"],
            "domain": "natural",
            "source_type": "usgs",
            "impact_vector": impact,
            "source_url": eq["url"],
            "source_tier": 1,  # 官方資料，最高信賴
        })
    return events


def persist_events(events: list[dict]) -> int:
    """將 ExternalEvent 寫入 DB。需在 Flask app context 中呼叫。"""
    from worldedge.db import db
    from worldedge.models import ExternalEvent

    written = 0
    for e in events:
        # 用 title + occurred_at 去重
        exists = ExternalEvent.query.filter_by(
            title=e["title"],
            source_type="usgs",
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
    logger.info("USGS: persisted %d new events", written)
    return written


def run_usgs_pipeline(hours: int = 168) -> list[dict]:
    """完整 pipeline：fetch → transform → (persist)。"""
    earthquakes = fetch_taiwan_earthquakes(hours=hours)
    events = to_external_events(earthquakes)
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    events = run_usgs_pipeline(hours=168)
    print(f"\n台灣地震 (past 7 days, >= M{MIN_MAGNITUDE}): {len(events)}")
    for e in events:
        print(
            f"  {e['occurred_at'].strftime('%Y-%m-%d %H:%M')} UTC  "
            f"{e['title']}  "
            f"impact={e['impact_vector']}"
        )
