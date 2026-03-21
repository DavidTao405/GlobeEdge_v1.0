"""啟動 GlobeEdge 爬蟲 + 訊號排程。

用法：python scripts/start_crawlers.py
"""
import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("globeedge.launcher")

from globeedge.crawler.scheduler import init_scheduler, scheduler
from globeedge.signals.signal_scheduler import init_signal_scheduler, signal_scheduler

if __name__ == "__main__":
    logger.info("[GlobeEdge] Starting crawler scheduler...")
    init_scheduler()

    logger.info("[GlobeEdge] Starting signal scheduler...")
    init_signal_scheduler()

    logger.info("[GlobeEdge] All schedulers running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        signal_scheduler.shutdown()
        logger.info("[GlobeEdge] Schedulers stopped.")
