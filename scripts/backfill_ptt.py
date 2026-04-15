"""PTT 回補爬蟲 — 手動補抓特定時間段 / 關鍵字的文章。

用法：
    python scripts/backfill_ptt.py \
        --board HatePolitics \
        --pages 50 \
        --keywords "柯文哲,京華城,判決,17年,民眾黨"

    python scripts/backfill_ptt.py \
        --board Gossiping \
        --pages 30 \
        --keywords "伊朗,油價,戰爭,美伊,中東"

    python scripts/backfill_ptt.py --board HatePolitics --pages 20
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("backfill")


def main():
    parser = argparse.ArgumentParser(description="PTT 回補爬蟲")
    parser.add_argument("--board", type=str, default="HatePolitics")
    parser.add_argument("--pages", type=int, default=50)
    parser.add_argument("--keywords", type=str, default="",
                        help="逗號分隔的關鍵字，例：柯文哲,京華城")
    parser.add_argument("--min-interactions", type=int, default=1,
                        help="最少互動數（backfill 預設 1，盡量多抓）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只抓不寫 DB")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] or None

    logger.info("Backfill: board=%s pages=%d keywords=%s",
                args.board, args.pages, keywords)

    from globeedge.crawler.ptt_crawler import run_ptt_pipeline

    if args.dry_run:
        edges = run_ptt_pipeline(
            boards=[args.board],
            pages_per_board=args.pages,
            min_interactions=args.min_interactions,
            persist_to_db=False,
            include_hot=True,
            keywords=keywords,
        )
        logger.info("Dry run: %d edges (not persisted)", len(edges))
    else:
        from dotenv import load_dotenv
        load_dotenv()
        from globeedge.app import create_app

        app = create_app()
        with app.app_context():
            edges = run_ptt_pipeline(
                boards=[args.board],
                pages_per_board=args.pages,
                min_interactions=args.min_interactions,
                persist_to_db=True,
                include_hot=True,
                keywords=keywords,
            )
            logger.info("Backfill complete: %d edges, articles persisted", len(edges))

            # 統計
            from globeedge.models import PttArticle
            total = PttArticle.query.count()
            board_count = PttArticle.query.filter_by(board=args.board).count()
            logger.info("DB total: %d articles (%s: %d)", total, args.board, board_count)

            if keywords:
                for kw in keywords:
                    c = PttArticle.query.filter(
                        PttArticle.title.contains(kw)
                    ).count()
                    logger.info("  keyword '%s': %d articles in DB", kw, c)


if __name__ == "__main__":
    main()
