"""爬蟲排程 — APScheduler。

排程總覽：
  news_crawler_daily  每天 02:00  Crawl4AI 爬取新聞首頁引用關係
  rss_crawler_6h      每 6 小時   RSS 快速引用關係
  ptt_crawler_8h      每 8 小時   PTT 八卦/政黑板推噓（主力資料源）
  bluesky_daily       每天 03:00  Bluesky KOL 互動關係
  financial_daily     每天 04:00  金融文件 LLM 解析（有成本上限）

⚠️ AIS 連線由 signal_scheduler.py 管理，確保單一實例。
"""

import asyncio
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Taipei")

# ── AIS 單一實例守護 ─────────────────────────────────────
_ais_lock = threading.Lock()
_ais_running = False


def is_ais_running() -> bool:
    """檢查 AIS WebSocket 是否正在執行（供 signal_scheduler 使用）。"""
    return _ais_running


def set_ais_running(state: bool) -> None:
    """設定 AIS 執行狀態（thread-safe）。"""
    global _ais_running
    with _ais_lock:
        _ais_running = state


# ── Job wrappers ─────────────────────────────────────────
def _run_news_crawler():
    """同步 wrapper，在排程 thread 中執行 async pipeline。"""
    from globeedge.crawler.news_crawler import run_pipeline

    logger.info("[scheduler] starting news_crawler pipeline")
    edges = asyncio.run(run_pipeline())
    logger.info("[scheduler] news_crawler done, %d edges", len(edges))


def _run_rss_crawler():
    """RSS 爬蟲：比 Crawl4AI 快、更穩定。"""
    from globeedge.crawler.news_crawler import run_rss_pipeline

    logger.info("[scheduler] starting RSS pipeline")
    edges = run_rss_pipeline()
    logger.info("[scheduler] RSS done, %d edges", len(edges))


def _should_deep_crawl() -> bool:
    """檢查是否應觸發深度爬取（重大事件發生）。"""
    try:
        from globeedge.app import create_app
        from globeedge.models import ExternalEvent
        from datetime import datetime, timezone, timedelta

        app = create_app()
        with app.app_context():
            cutoff = datetime.now(timezone.utc) - timedelta(hours=8)
            # GDELT 高衝擊事件
            recent = ExternalEvent.query.filter(
                ExternalEvent.occurred_at >= cutoff,
            ).all()
            for e in recent:
                if e.impact_vector and e.source_type == "usgs":
                    # M5.5+ 地震
                    mag_impact = abs(e.impact_vector[3]) if len(e.impact_vector) > 3 else 0
                    if mag_impact >= 0.3:
                        logger.info("[scheduler] deep crawl triggered by earthquake: %s", e.title)
                        return True
            return False
    except Exception:
        return False


def _run_ptt_crawler():
    """PTT 八卦/政黑板推噓分析（主力資料源），含 DB 持久化。"""
    from globeedge.crawler.ptt_crawler import run_ptt_pipeline

    deep = _should_deep_crawl()
    mode = "DEEP (30 pages)" if deep else "normal"
    logger.info("[scheduler] starting PTT pipeline (%s)", mode)

    # 需要 Flask app context 才能寫 DB
    try:
        from globeedge.app import create_app
        app = create_app()
        with app.app_context():
            edges = run_ptt_pipeline(
                boards=["Gossiping", "HatePolitics"],
                min_interactions=3,
                persist_to_db=True,
                include_hot=True,
                deep_mode=deep,
            )
            logger.info("[scheduler] PTT done, %d edges, articles persisted", len(edges))
    except Exception:
        logger.exception("[scheduler] PTT pipeline failed")


def _run_bluesky_crawler():
    """Bluesky KOL 互動關係爬蟲。"""
    from globeedge.crawler.bluesky_crawler import run_bluesky_pipeline

    logger.info("[scheduler] starting bluesky pipeline")
    edges = run_bluesky_pipeline()
    logger.info("[scheduler] bluesky done, %d edges", len(edges))


def _run_financial_crawler():
    """金融文件 LLM 解析（有成本上限）。"""
    from globeedge.crawler.financial_crawler import (
        get_cost_summary,
        reset_call_counter,
    )

    reset_call_counter()
    logger.info("[scheduler] starting financial crawler")

    # TODO Phase 3：實作金融文件爬取 + extract_belief_from_doc
    # 目前只是佔位，確保排程架構可用

    summary = get_cost_summary()
    logger.info("[scheduler] financial done, cost: %s", summary)


# ── 排程初始化 ────────────────────────────────────────────
def init_scheduler():
    """註冊所有 crawler jobs 並啟動排程。"""
    # 新聞首頁 — Crawl4AI
    scheduler.add_job(
        _run_news_crawler,
        trigger=CronTrigger(hour=2, minute=0),
        id="news_crawler_daily",
        name="每天凌晨 2:00 Crawl4AI 爬取新聞首頁引用關係",
        replace_existing=True,
    )
    # RSS — 每 6 小時
    scheduler.add_job(
        _run_rss_crawler,
        trigger=IntervalTrigger(hours=6),
        id="rss_crawler_6h",
        name="每 6 小時 RSS 爬取引用關係",
        replace_existing=True,
    )
    # PTT — 每 8 小時（主力資料源）
    scheduler.add_job(
        _run_ptt_crawler,
        trigger=IntervalTrigger(hours=8),
        id="ptt_crawler_8h",
        name="每 8 小時 PTT 八卦/政黑板推噓",
        replace_existing=True,
    )
    # Bluesky — 每天凌晨 3:00
    scheduler.add_job(
        _run_bluesky_crawler,
        trigger=CronTrigger(hour=3, minute=0),
        id="bluesky_daily",
        name="每天凌晨 3:00 Bluesky KOL 互動關係",
        replace_existing=True,
    )
    # 金融 LLM — 每天凌晨 4:00
    scheduler.add_job(
        _run_financial_crawler,
        trigger=CronTrigger(hour=4, minute=0),
        id="financial_daily",
        name="每天凌晨 4:00 金融文件 LLM 解析",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[scheduler] started, jobs: %s", scheduler.get_jobs())


def shutdown_scheduler():
    """關閉排程。"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] shutdown")
