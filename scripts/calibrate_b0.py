"""Station 4：b(0) 真實校準。

用 PTT 推噓訊號校準 geopolitics scenario 的 Agent b(0)。
只校準訊號可靠的維度（dim5/dim6/dim7），dim0/dim1 保持先驗。

公式：b(0)_final = α × b(0)_ptt + (1-α) × b(0)_prior
      α = min(篇數 / 100, 0.8)

用法：
    python scripts/calibrate_b0.py
    python scripts/calibrate_b0.py --apply   # 更新 scenario 檔案
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)

# 只校準這些維度（PTT 訊號可靠）
CALIBRATE_DIMS = {
    5: {"name": "政治改革意願", "keywords": ["罷免", "民主", "改革", "青鳥"]},
    6: {"name": "群體凝聚度",   "keywords": ["黃國昌", "民眾黨", "李貞秀", "黨籍", "開除"]},
    7: {"name": "外部威脅感知", "keywords": ["鄭習會", "鄭麗文", "習近平", "兩岸", "訪中"]},
}

# 不校準（記錄原因）
SKIP_DIMS = {
    0: "PTT 推噓比語意反轉（推=同意批評=不信任），需 Pol.is 結構化資料",
    1: "資料太稀疏（僅 4 天有效），且語意與 dim0 混淆",
}

# Agent 類型對應的看板
AGENT_BOARD_MAP = {
    "forum_hatepolitics": "HatePolitics",
    "forum_gossiping": "Gossiping",
}


def fetch_ptt_stance_by_board(dim_idx: int, keywords: list[str]) -> dict[str, dict]:
    """按看板分組計算 PTT 立場訊號。

    Returns:
        {"HatePolitics": {"articles": N, "push_ratio": R, "signal": S}, ...}
    """
    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    app = create_app()
    with app.app_context():
        filters = [PttArticle.title.contains(kw) for kw in keywords]
        arts = PttArticle.query.filter(db.or_(*filters)).all()

        by_board: dict[str, dict] = defaultdict(lambda: {
            "articles": 0, "push": 0, "boo": 0, "arrow": 0
        })

        for a in arts:
            m = re.search(r"M\.(\d+)\.A", a.url)
            if not m:
                continue
            dt = datetime.fromtimestamp(int(m.group(1)))
            if not (START <= dt < END):
                continue
            by_board[a.board]["articles"] += 1
            by_board[a.board]["push"] += (a.push_count or 0)
            by_board[a.board]["boo"] += (a.boo_count or 0)
            by_board[a.board]["arrow"] += (a.arrow_count or 0)

    results = {}
    for board, stats in by_board.items():
        total_pb = stats["push"] + stats["boo"]
        push_ratio = stats["push"] / total_pb if total_pb > 0 else 0.5
        signal = (push_ratio - 0.5) * 2  # [-1, +1]
        results[board] = {
            "articles": stats["articles"],
            "push": stats["push"],
            "boo": stats["boo"],
            "push_ratio": round(push_ratio, 3),
            "signal": round(signal, 3),
        }
    return results


def calibrate_b0(
    prior: float,
    ptt_signal: float,
    n_articles: int,
    min_articles: int = 10,
) -> tuple[float, float, float]:
    """校準 b(0)。

    Returns:
        (calibrated_b0, alpha_calibrate, delta)
    """
    if n_articles < min_articles:
        return prior, 0.0, 0.0

    alpha = min(n_articles / 100, 0.8)
    calibrated = alpha * ptt_signal + (1 - alpha) * prior
    calibrated = float(np.clip(calibrated, -1.0, 1.0))
    delta = calibrated - prior
    return calibrated, round(alpha, 3), round(delta, 3)


def main():
    parser = argparse.ArgumentParser(description="b(0) 真實校準")
    parser.add_argument("--apply", action="store_true", help="實際更新 scenario 設定")
    parser.add_argument("--output", default="results/b0_calibration.json")
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    from globeedge.scenarios.geopolitics import build as build_scenario
    scenario = build_scenario()
    agents = scenario.agents
    B0_prior = scenario.belief_matrix()

    logger.info("=" * 60)
    logger.info("  Station 4：b(0) 真實校準")
    logger.info("=" * 60)

    # 記錄跳過的維度
    logger.info("\n跳過校準（保持先驗）：")
    for dim_idx, reason in SKIP_DIMS.items():
        logger.info(f"  dim{dim_idx}: {reason}")

    # 校準每個維度
    calibration_log = []

    for dim_idx, info in CALIBRATE_DIMS.items():
        logger.info(f"\n{'─'*50}")
        logger.info(f"dim{dim_idx} {info['name']}")
        logger.info(f"  keywords: {info['keywords']}")

        board_data = fetch_ptt_stance_by_board(dim_idx, info["keywords"])
        for board, stats in board_data.items():
            logger.info(f"  {board}: {stats['articles']} 篇, "
                        f"push={stats['push_ratio']:.1%}, signal={stats['signal']:+.3f}")

        # 對每個 Agent 校準
        for i, agent in enumerate(agents):
            prior = float(B0_prior[i, dim_idx])

            # 決定用哪個看板的訊號
            if agent.type == "forum":
                if "政黑" in agent.name or "HatePolitics" in agent.name.lower():
                    board_key = "HatePolitics"
                elif "八卦" in agent.name or "Gossiping" in agent.name.lower():
                    board_key = "Gossiping"
                else:
                    board_key = "HatePolitics"  # default
            elif agent.type in ("kol", "demographic"):
                # KOL/demographic 用兩板加權平均
                total_arts = sum(d["articles"] for d in board_data.values())
                if total_arts > 0:
                    weighted_signal = sum(
                        d["signal"] * d["articles"] / total_arts
                        for d in board_data.values()
                    )
                else:
                    weighted_signal = 0.0
                calibrated, alpha, delta = calibrate_b0(
                    prior, weighted_signal, total_arts
                )
                if abs(delta) > 0.01:
                    logger.info(f"    {agent.name:20s} dim{dim_idx}: "
                                f"{prior:+.3f} → {calibrated:+.3f} "
                                f"(Δ={delta:+.3f}, α={alpha:.2f})")
                    calibration_log.append({
                        "agent": agent.name, "agent_type": agent.type,
                        "dim": dim_idx, "dim_name": info["name"],
                        "prior": prior, "calibrated": calibrated,
                        "delta": delta, "alpha": alpha,
                        "articles": total_arts, "source": "weighted_avg",
                    })
                continue
            else:
                # media/institution → 不用 PTT 校準（保持先驗）
                continue

            stats = board_data.get(board_key, {})
            n = stats.get("articles", 0)
            signal = stats.get("signal", 0.0)

            calibrated, alpha, delta = calibrate_b0(prior, signal, n)
            if abs(delta) > 0.01:
                logger.info(f"    {agent.name:20s} dim{dim_idx}: "
                            f"{prior:+.3f} → {calibrated:+.3f} "
                            f"(Δ={delta:+.3f}, α={alpha:.2f}, n={n})")
                calibration_log.append({
                    "agent": agent.name, "agent_type": agent.type,
                    "dim": dim_idx, "dim_name": info["name"],
                    "prior": prior, "calibrated": calibrated,
                    "delta": delta, "alpha": alpha,
                    "articles": n, "source": board_key,
                })

    # 摘要
    logger.info(f"\n{'='*60}")
    logger.info(f"  校準摘要：{len(calibration_log)} 個 Agent×dim 被更新")
    logger.info(f"{'='*60}")
    for entry in sorted(calibration_log, key=lambda x: -abs(x["delta"])):
        logger.info(f"  {entry['agent']:20s} dim{entry['dim']}({entry['dim_name']}) "
                     f"Δ={entry['delta']:+.3f} (α={entry['alpha']:.2f})")

    # 輸出
    output = {
        "calibrated_dims": list(CALIBRATE_DIMS.keys()),
        "skipped_dims": {str(k): v for k, v in SKIP_DIMS.items()},
        "calibration_log": calibration_log,
        "total_updates": len(calibration_log),
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告：{args.output}")

    if not args.apply:
        logger.info("\n（預覽模式。加 --apply 更新 scenario。）")
    else:
        _apply_to_scenario(calibration_log)


def _apply_to_scenario(log: list[dict]):
    """把校準結果寫入 geopolitics scenario。"""
    from globeedge.scenarios.geopolitics import build as build_scenario
    scenario = build_scenario()
    B0 = scenario.belief_matrix()
    agents = scenario.agents

    agent_name_to_idx = {a.name: i for i, a in enumerate(agents)}
    for entry in log:
        idx = agent_name_to_idx.get(entry["agent"])
        if idx is not None:
            B0[idx, entry["dim"]] = entry["calibrated"]

    logger.info(f"\n已更新 {len(log)} 個 b(0) 值（記憶體中）")
    logger.info("注意：scenario .py 檔案未修改，需手動更新或下次 session 重設")


if __name__ == "__main__":
    main()
