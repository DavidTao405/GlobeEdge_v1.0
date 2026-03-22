"""心理機制參數校準 — 用 PTT 真實資料估計 Ebbinghaus S 值。

用法:
    python scripts/calibrate_psychology.py \
        --board Gossiping --keyword "核電 能源 台電" --days 90
    python scripts/calibrate_psychology.py --dry-run   # 用合成資料測試

原理:
    1. 從 PTT 爬蟲取出活躍用戶的發文時間序列
    2. 用 Qwen3.5 標記每篇文章的立場分數
    3. 用 curve_fit 擬合 b(t) = b_steady + A * exp(-t/S)
    4. 按 Agent 類型分組，估計 S 的分佈

需要:
    PTT 爬蟲歷史資料（DB 或本地爬取）
    Ollama qwen3.5:9b（立場標記）
"""

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
from scipy.optimize import curve_fit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── 立場標記 ──────────────────────────────────────────────

# Redis 快取 key prefix
STANCE_CACHE_PREFIX = "stance:"

# 立場標記 LLM prompt
STANCE_SYSTEM_PROMPT = """/no_think
判斷以下 PTT 文章對【{topic}】的立場。
+1.0 = 非常支持
-1.0 = 非常反對
0.0 = 中立或無關
只回傳一個小數，不要任何說明。"""


def tag_stance_single(text: str, topic: str = "核電政策") -> float | None:
    """用 Ollama qwen3.5:9b 標記單篇文章立場。"""
    try:
        import httpx
        r = httpx.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "qwen3.5:9b",
                "stream": False,
                "options": {"temperature": 0.1, "top_p": 0.9},
                "messages": [
                    {"role": "system", "content": STANCE_SYSTEM_PROMPT.format(topic=topic)},
                    {"role": "user", "content": text[:500]},  # 截斷避免 context 過長
                ],
            },
            timeout=30,
        )
        r.raise_for_status()
        content = r.json().get("message", {}).get("content", "0").strip()
        # 清理 think tags
        if "<think>" in content:
            content = content.split("</think>")[-1].strip()
        return float(content)
    except Exception as e:
        logger.debug("stance tagging failed: %s", e)
        return None


def tag_stance_batch(
    articles: list[dict],
    topic: str = "核電政策",
    batch_size: int = 20,
) -> list[dict]:
    """批次標記立場分數。"""
    results = []
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        for article in batch:
            text = article.get("title", "") + " " + article.get("text", "")
            stance = tag_stance_single(text, topic)
            if stance is not None:
                article["stance"] = max(-1.0, min(1.0, stance))
                results.append(article)
        logger.info(
            f"  tagged {min(i + batch_size, len(articles))}/{len(articles)} articles"
        )
    return results


# ── PTT 資料收集 ──────────────────────────────────────────

def collect_from_ptt_live(
    board: str,
    keywords: list[str],
    days: int = 90,
    min_articles: int = 5,
) -> dict[str, list[dict]]:
    """從 PTT 即時爬取活躍用戶的發文歷史。

    Returns:
        {user_id: [{"date": str, "title": str, "text": str, "stance": None}, ...]}
    """
    from globeedge.crawler.ptt_crawler import fetch_article_list, parse_article

    import time

    logger.info(f"Crawling PTT {board} (past {days} days, keywords={keywords})")

    # 估計需要的頁數（每頁 ~20 篇，每天 ~100 篇 Gossiping）
    pages_needed = min(days * 5, 200)  # 安全上限

    articles_list = fetch_article_list(board, pages=pages_needed)
    logger.info(f"  {len(articles_list)} articles found")

    # 按 author 分組
    user_articles: dict[str, list[dict]] = defaultdict(list)
    parsed = 0

    for article_info in articles_list:
        if parsed >= 500:  # 安全上限
            break
        time.sleep(0.5)

        article = parse_article(article_info["url"], board)
        if not article:
            continue
        parsed += 1

        # 關鍵字過濾
        title_lower = article.title.lower()
        if not any(kw in title_lower for kw in keywords):
            continue

        user_articles[article.author].append({
            "date": article.date,
            "title": article.title,
            "text": "",  # 內文需要額外解析
            "stance": None,
        })

    # 只保留活躍用戶
    active_users = {
        uid: arts for uid, arts in user_articles.items()
        if len(arts) >= min_articles
    }
    logger.info(
        f"  {len(user_articles)} unique users, "
        f"{len(active_users)} active (>= {min_articles} articles)"
    )
    return active_users


def generate_synthetic_data(n_users: int = 30, n_points: int = 20) -> dict[str, list[dict]]:
    """生成合成用戶資料（測試用）。"""
    rng = np.random.default_rng(42)
    users = {}

    agent_types = ["forum"] * 15 + ["demographic"] * 10 + ["kol"] * 5
    S_values = {"forum": 2.0, "demographic": 5.0, "kol": 15.0}

    for i in range(n_users):
        atype = agent_types[i]
        S_true = S_values[atype] * rng.uniform(0.7, 1.3)  # 加噪聲
        b_steady = rng.uniform(-0.3, 0.3)
        A = rng.uniform(0.3, 0.7) * rng.choice([-1, 1])

        articles = []
        for t in range(n_points):
            stance = b_steady + A * np.exp(-t / S_true) + rng.normal(0, 0.05)
            stance = max(-1.0, min(1.0, stance))
            articles.append({
                "date": (datetime.now() - timedelta(days=n_points - t)).strftime("%Y-%m-%d"),
                "title": f"synthetic_{i}_{t}",
                "text": "",
                "stance": round(stance, 3),
                "agent_type": atype,
            })

        users[f"user_{i:03d}_{atype}"] = articles

    return users


# ── 遺忘曲線擬合 ──────────────────────────────────────────

def _forgetting_model(t, b_steady, A, S):
    """b(t) = b_steady + A * exp(-t/S)"""
    return b_steady + A * np.exp(-t / S)


def fit_forgetting_curve(stances: list[tuple[int, float]]) -> dict | None:
    """擬合單一用戶的遺忘曲線。

    Args:
        stances: [(day_offset, stance_score), ...]

    Returns:
        {"S": float, "A": float, "b_steady": float, "r_squared": float}
        或 None（擬合失敗）
    """
    if len(stances) < 5:
        return None

    t_data = np.array([s[0] for s in stances], dtype=float)
    y_data = np.array([s[1] for s in stances])

    # 正規化 t 到從 0 開始
    t_data = t_data - t_data.min()

    try:
        popt, _ = curve_fit(
            _forgetting_model,
            t_data,
            y_data,
            p0=[y_data[-1], y_data[0] - y_data[-1], 5.0],  # 初始猜測
            bounds=(
                [-1.0, -2.0, 0.1],   # 下界
                [1.0, 2.0, 50.0],    # 上界
            ),
            maxfev=5000,
        )
        b_steady, A, S = popt

        # R²
        y_pred = _forgetting_model(t_data, *popt)
        ss_res = np.sum((y_data - y_pred) ** 2)
        ss_tot = np.sum((y_data - np.mean(y_data)) ** 2)
        r_squared = 1 - (ss_res / max(ss_tot, 1e-9))

        return {
            "S": round(float(S), 2),
            "A": round(float(A), 3),
            "b_steady": round(float(b_steady), 3),
            "r_squared": round(float(r_squared), 3),
        }
    except Exception as e:
        logger.debug("curve_fit failed: %s", e)
        return None


def calibrate_memory_stability(user_data: dict[str, list[dict]]) -> dict:
    """按 Agent 類型分組，計算 S 的中位數。"""
    from globeedge.core.psychology import MEMORY_STABILITY

    # 分類用戶
    type_S_values: dict[str, list[float]] = defaultdict(list)

    for uid, articles in user_data.items():
        # 推斷 agent_type
        if articles and "agent_type" in articles[0]:
            atype = articles[0]["agent_type"]
        elif "PTT" in uid or "ptt" in uid:
            atype = "forum"
        else:
            atype = "demographic"

        # 準備 (day, stance) 資料
        stances = []
        for i, a in enumerate(articles):
            if a.get("stance") is not None:
                stances.append((i, a["stance"]))

        if len(stances) < 5:
            continue

        result = fit_forgetting_curve(stances)
        if result and result["r_squared"] > 0.3:
            type_S_values[atype].append(result["S"])

    # 計算統計
    calibrated = {}
    for atype, S_list in type_S_values.items():
        if not S_list:
            continue
        calibrated[atype] = {
            "n_users": len(S_list),
            "S_median": round(float(np.median(S_list)), 2),
            "S_mean": round(float(np.mean(S_list)), 2),
            "S_std": round(float(np.std(S_list)), 2),
            "S_min": round(float(np.min(S_list)), 2),
            "S_max": round(float(np.max(S_list)), 2),
            "current_setting": MEMORY_STABILITY.get(atype, 10.0),
        }

    # 偏差分析
    for atype, stats in calibrated.items():
        deviation = abs(stats["S_median"] - stats["current_setting"])
        pct = deviation / max(stats["current_setting"], 0.01) * 100
        stats["deviation_pct"] = round(pct, 1)
        stats["verdict"] = (
            "✅ accurate" if pct < 20 else
            "⚠️ needs adjustment" if pct < 50 else
            "❌ significantly off"
        )

    return calibrated


def main():
    import argparse

    parser = argparse.ArgumentParser(description="GlobeEdge 心理機制參數校準")
    parser.add_argument("--board", type=str, default="Gossiping")
    parser.add_argument("--keyword", type=str, default="核電 能源 台電")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--topic", type=str, default="核電政策")
    parser.add_argument("--dry-run", action="store_true", help="用合成資料測試")
    parser.add_argument("--output", type=str, default="results/psychology_calibration.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    if args.dry_run:
        logger.info("=== Dry Run: 合成資料測試 ===")
        user_data = generate_synthetic_data(n_users=30, n_points=20)
        logger.info(f"Generated {len(user_data)} synthetic users")
    else:
        keywords = args.keyword.split()
        logger.info(f"=== PTT {args.board} 立場校準 ===")
        logger.info(f"  Keywords: {keywords}")
        logger.info(f"  Days: {args.days}")

        user_data = collect_from_ptt_live(
            board=args.board,
            keywords=keywords,
            days=args.days,
        )

        if not user_data:
            logger.error("No active users found. Try --dry-run first.")
            sys.exit(1)

        # LLM 立場標記
        logger.info(f"\nTagging stances with Qwen3.5:9b...")
        for uid, articles in user_data.items():
            tagged = tag_stance_batch(articles, topic=args.topic)
            user_data[uid] = tagged

    # 擬合遺忘曲線
    logger.info(f"\n{'='*60}")
    logger.info("Fitting forgetting curves...")
    logger.info(f"{'='*60}")

    fit_count = 0
    fit_success = 0
    for uid, articles in user_data.items():
        stances = [(i, a["stance"]) for i, a in enumerate(articles) if a.get("stance") is not None]
        result = fit_forgetting_curve(stances)
        fit_count += 1
        if result and result["r_squared"] > 0.3:
            fit_success += 1
            logger.info(f"  {uid}: S={result['S']:.1f} A={result['A']:+.3f} R²={result['r_squared']:.3f}")

    logger.info(f"\n  Fitted: {fit_success}/{fit_count} (R² > 0.3)")

    # 校準
    logger.info(f"\n{'='*60}")
    logger.info("Calibrating MEMORY_STABILITY...")
    logger.info(f"{'='*60}")

    calibrated = calibrate_memory_stability(user_data)

    for atype, stats in calibrated.items():
        logger.info(
            f"\n  {atype:15s}  "
            f"n={stats['n_users']:3d}  "
            f"S_median={stats['S_median']:5.1f}  "
            f"current={stats['current_setting']:5.1f}  "
            f"deviation={stats['deviation_pct']:5.1f}%  "
            f"{stats['verdict']}"
        )

    # 輸出
    output = {
        "timestamp": datetime.now().isoformat(),
        "mode": "dry_run" if args.dry_run else "live",
        "n_users": len(user_data),
        "fit_success_rate": f"{fit_success}/{fit_count}",
        "calibration": calibrated,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"\n結果已輸出到 {args.output}")


if __name__ == "__main__":
    main()
