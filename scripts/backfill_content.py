"""補抓 PTT 文章內文 + 推文串。

對已在 DB 的 ptt_articles，逐一訪問 URL 抓取完整內容。

用法：
    python scripts/backfill_content.py
    python scripts/backfill_content.py --limit 100
    python scripts/backfill_content.py --hot-first     # 優先熱門文章
"""

import argparse
import json
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

from curl_cffi import requests as cffi_requests

REQUEST_DELAY = 0.5

# 解析 regex
_RE_META = re.compile(r'<span class="article-meta-value">([^<]+)</span>')
_RE_PUSH = re.compile(
    r'<span class="hl push-tag">(推|噓|→)\s*</span>'
    r'<span class="f3 hl push-userid">([^<]+)</span>'
    r'<span class="f3 push-content">: ([^<]*)</span>'
    r'<span class="push-ipdatetime">\s*([^<]*)</span>'
)


def fetch_article_content(url: str) -> dict | None:
    """抓取單篇 PTT 文章的完整內容。"""
    try:
        r = cffi_requests.get(
            url,
            cookies={"over18": "1"},
            impersonate="chrome",
            timeout=15,
        )
        if r.status_code == 404:
            return {"status": "404"}
        if r.status_code != 200:
            return None
        html = r.text
    except Exception as e:
        logger.debug(f"Fetch error: {e}")
        return None

    # 提取本文（在 meta 之後、push 之前）
    # 找到最後一個 meta-value 的位置
    meta_matches = list(_RE_META.finditer(html))
    if meta_matches:
        content_start = meta_matches[-1].end()
    else:
        content_start = 0

    # 找第一個 push div 的位置
    push_start = html.find('<div class="push">')
    if push_start == -1:
        push_start = len(html)

    # 本文 HTML → 純文字
    content_html = html[content_start:push_start]
    content = re.sub(r'<[^>]+>', '', content_html)
    content = re.sub(r'\s+', ' ', content).strip()
    # 截斷（避免超長文章）
    content = content[:5000]

    # 推文串
    comments = []
    for m in _RE_PUSH.finditer(html):
        comments.append({
            "type": m.group(1),
            "author": m.group(2).strip(),
            "content": m.group(3).strip(),
            "time": m.group(4).strip(),
        })

    return {
        "status": "ok",
        "content": content,
        "comments": comments,
    }


def main():
    parser = argparse.ArgumentParser(description="補抓 PTT 文章內文")
    parser.add_argument("--limit", type=int, default=0, help="最多抓幾篇（0=全部）")
    parser.add_argument("--hot-first", action="store_true", help="優先熱門文章")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    app = create_app()
    with app.app_context():
        # 取未補抓的文章
        q = PttArticle.query.filter(
            db.or_(
                PttArticle.content_crawled == False,
                PttArticle.content_crawled == None,
            )
        )
        if args.hot_first:
            q = q.order_by(
                (PttArticle.push_count + PttArticle.boo_count + PttArticle.arrow_count).desc()
            )
        else:
            q = q.order_by(PttArticle.created_at.desc())

        if args.limit > 0:
            q = q.limit(args.limit)

        articles = q.all()
        total = len(articles)
        logger.info(f"待補抓：{total} 篇")

        success = 0
        deleted = 0
        failed = 0

        for i, a in enumerate(articles):
            time.sleep(REQUEST_DELAY)
            result = fetch_article_content(a.url)

            if result is None:
                failed += 1
                continue

            if result["status"] == "404":
                a.content_crawled = True
                a.content = None
                deleted += 1
            else:
                a.content = result["content"]
                a.push_comments = result["comments"]
                a.content_crawled = True
                success += 1

            # 批次 commit
            if (i + 1) % args.batch_size == 0:
                db.session.commit()
                logger.info(
                    f"  {i+1}/{total}  ok={success} 404={deleted} fail={failed}"
                )

        db.session.commit()
        logger.info(f"\n完成：ok={success} 404={deleted} fail={failed} total={total}")

        # 統計
        stats = db.session.execute(db.text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN content_crawled = TRUE THEN 1 END) as crawled,
                COUNT(CASE WHEN content IS NOT NULL AND content != '' THEN 1 END) as has_content,
                COUNT(CASE WHEN content IS NULL AND content_crawled = TRUE THEN 1 END) as deleted_404,
                ROUND(AVG(LENGTH(content))::numeric, 0) as avg_len
            FROM ptt_articles
        """)).fetchone()
        logger.info(f"\nDB 統計：")
        logger.info(f"  total={stats[0]}  crawled={stats[1]}  "
                     f"has_content={stats[2]}  404={stats[3]}  avg_len={stats[4]}")


if __name__ == "__main__":
    main()
