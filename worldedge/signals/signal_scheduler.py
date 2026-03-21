"""地緣政治訊號排程 — 與 crawler/scheduler.py 分離。

排程總覽：
  usgs_hourly     每 1 小時   台灣地震偵測
  gdelt_6h        每 6 小時   台灣相關負面新聞

⚠️ AIS WebSocket 需要獨立管理（長連線），不在此排程中。
    用 crawler/scheduler.py 的 is_ais_running() 檢查。
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

signal_scheduler = BackgroundScheduler(timezone="Asia/Taipei")


def _run_usgs():
    """USGS 地震偵測。"""
    from worldedge.signals.usgs_signal import run_usgs_pipeline

    logger.info("[signal] starting USGS pipeline")
    events = run_usgs_pipeline(hours=2)  # 只查最近 2 小時，避免重複
    logger.info("[signal] USGS done, %d events", len(events))


def _run_gdelt():
    """GDELT 台灣負面新聞。"""
    from worldedge.signals.gdelt_signal import run_gdelt_pipeline

    logger.info("[signal] starting GDELT pipeline")
    events = run_gdelt_pipeline(timespan="6h")
    logger.info("[signal] GDELT done, %d events", len(events))


def init_signal_scheduler():
    """註冊所有 signal jobs 並啟動排程。"""
    signal_scheduler.add_job(
        _run_usgs,
        trigger=IntervalTrigger(hours=1),
        id="usgs_hourly",
        name="每小時 USGS 台灣地震偵測",
        replace_existing=True,
    )
    signal_scheduler.add_job(
        _run_gdelt,
        trigger=IntervalTrigger(hours=6),
        id="gdelt_6h",
        name="每 6 小時 GDELT 台灣負面新聞",
        replace_existing=True,
    )

    signal_scheduler.start()
    logger.info("[signal] scheduler started, jobs: %s",
                signal_scheduler.get_jobs())


def shutdown_signal_scheduler():
    """關閉排程。"""
    if signal_scheduler.running:
        signal_scheduler.shutdown(wait=False)
        logger.info("[signal] scheduler shutdown")
