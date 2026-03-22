"""啟動 GlobeEdge 爬蟲 + 訊號排程（長期背景運行）。

用法:
    python scripts/start_crawlers.py

啟動後背景運行：
  PTT 八卦/政黑   每 8 小時  → ptt_articles + influence_edges
  USGS 台灣地震    每 1 小時  → external_events
  GDELT 台灣新聞   每 6 小時  → external_events
  RSS 引用關係     每 6 小時
  Bluesky KOL    每天 03:00

Ctrl+C 優雅關閉。
"""

import logging
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("globeedge.launcher")


def main():
    from globeedge.crawler.scheduler import init_scheduler, shutdown_scheduler, scheduler
    from globeedge.signals.signal_scheduler import (
        init_signal_scheduler,
        shutdown_signal_scheduler,
        signal_scheduler as sig_sched,
    )

    logger.info("=" * 50)
    logger.info("  GlobeEdge Crawler + Signal Scheduler")
    logger.info("=" * 50)

    init_scheduler()
    init_signal_scheduler()

    for job in scheduler.get_jobs():
        logger.info(f"  [crawler] {job.id}: next={job.next_run_time}")
    for job in sig_sched.get_jobs():
        logger.info(f"  [signal]  {job.id}: next={job.next_run_time}")

    logger.info("")
    logger.info("All schedulers running. Press Ctrl+C to stop.")

    def handle_shutdown(signum, frame):
        logger.info("Shutting down...")
        shutdown_scheduler()
        shutdown_signal_scheduler()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        handle_shutdown(None, None)


if __name__ == "__main__":
    main()
