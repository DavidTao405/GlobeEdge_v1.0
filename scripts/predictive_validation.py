"""預測性驗證 — 美伊戰爭即時 ground truth 比對。

用法:
    python scripts/predictive_validation.py
    python scripts/predictive_validation.py --dry-run   # 合成資料
    python scripts/predictive_validation.py --output results/prediction.json

原理:
    Layer 4 驗證：模型在已知事件下的輿論走向預測 vs 真實 PTT 資料。

設計:
    訓練截止: 2026-02-27 (美伊戰爭爆發前一天)
    預測期間: 2026-02-28 → 2026-03-22
    輸入: 已知事件序列（空襲、封鎖海峽、油價 100 美元...）
    驗證: 每日 PTT 平均立場 vs 模型預測的維度趨勢

不求數值精確，只求方向性:
    1. 方向一致性（Pearson 相關係數）
    2. 事件反應時機
    3. 哪個維度最準 / 最不準
"""

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.core import FJEngine, MonteCarloRunner
from globeedge.core.psychology import PsychologyConfig, apply_forgetting, apply_motivated_reasoning
from globeedge.scenarios.iran_war import build as build_scenario

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── 已知事件序列 ──────────────────────────────────────────

IRAN_WAR_TIMELINE = [
    {"day": 0,  "date": "2026-02-28", "title": "美以發動 Epic Fury 空襲",
     "impact": [0.0, -0.3, -0.1, 0.5, 0.1, -0.2, -0.1, 0.6]},
    {"day": 2,  "date": "2026-03-02", "title": "伊朗封鎖霍木茲海峽",
     "impact": [-0.2, -0.4, -0.3, 0.8, -0.2, -0.6, -0.3, 0.7]},
    {"day": 3,  "date": "2026-03-03", "title": "卡達 LNG 設施遭攻擊",
     "impact": [-0.1, -0.3, -0.2, 0.7, -0.1, -0.7, -0.2, 0.5]},
    {"day": 8,  "date": "2026-03-08", "title": "布蘭特原油突破 100 美元",
     "impact": [-0.3, -0.2, -0.5, 0.9, -0.1, -0.4, -0.4, 0.3]},
    {"day": 10, "date": "2026-03-10", "title": "IEA 戰略儲備釋放",
     "impact": [0.2, 0.1, 0.1, -0.3, 0.2, 0.3, 0.2, -0.1]},
    {"day": 12, "date": "2026-03-12", "title": "台灣緊急能源應對措施",
     "impact": [0.1, 0.0, 0.0, -0.2, 0.1, 0.2, 0.1, 0.0]},
]

# 驗證維度（PTT 可觀測的）
VALIDATION_DIMS = {
    3: {"name": "經濟焦慮度", "keyword": "油價 漲 缺電 經濟"},
    4: {"name": "對美信任度", "keyword": "美國 川普 盟友 保護"},
    5: {"name": "能源供應安全感", "keyword": "能源 缺 電力 石油"},
    7: {"name": "外部威脅感知", "keyword": "戰爭 攻擊 威脅 軍事"},
}


def run_prediction_model(scenario=None, horizon: int = 22) -> np.ndarray:
    """執行模型預測，回傳信念軌跡。

    Returns:
        (horizon+1, n_agents, n_dims) trajectory
    """
    if scenario is None:
        scenario = build_scenario()

    B0 = scenario.belief_matrix()
    W = scenario.default_W()
    agent_types = scenario.agent_types()
    n_agents, n_dims = B0.shape
    alpha = scenario.alpha

    # 套用動機性推理
    W_mod = apply_motivated_reasoning(W, B0)

    # 建立事件 dict
    events = {}
    for evt in IRAN_WAR_TIMELINE:
        day = evt["day"]
        if day <= horizon:
            impact = np.zeros((n_agents, n_dims))
            for i in range(n_agents):
                impact[i] = evt["impact"]
            events[day] = impact

    # 跑 FJ + Ebbinghaus
    trajectory = []
    B = B0.copy()
    for t in range(horizon + 1):
        trajectory.append(B.copy())
        if t < horizon:
            B_next = alpha * W_mod @ B + (1 - alpha) * B0
            if t in events:
                B_next = B_next + events[t]
            B_next = np.clip(B_next, -1.0, 1.0)
            B_next = apply_forgetting(B_next, B0, agent_types)
            B_next = np.clip(B_next, -1.0, 1.0)
            B = B_next

    return np.array(trajectory)  # (horizon+1, n_agents, n_dims)


def generate_synthetic_ptt(horizon: int = 22) -> dict[int, dict[int, float]]:
    """生成合成 PTT 輿論資料（模擬真實趨勢）。

    Returns:
        {dim_idx: {day: average_stance, ...}}
    """
    rng = np.random.default_rng(42)
    actual = {}

    for dim_idx, info in VALIDATION_DIMS.items():
        daily = {}
        for day in range(horizon + 1):
            if dim_idx == 3:  # 經濟焦慮
                # 空襲後快速上升，封鎖海峽後更高，IEA 釋放後略降
                base = 0.1
                if day >= 0: base += 0.2
                if day >= 2: base += 0.3
                if day >= 8: base += 0.2
                if day >= 10: base -= 0.1
                value = base + rng.normal(0, 0.05)
            elif dim_idx == 4:  # 對美信任
                # 先升（美國出手）後降（油價衝擊台灣）
                base = 0.1
                if day >= 0: base += 0.15
                if day >= 2: base -= 0.05
                if day >= 8: base -= 0.2
                value = base + rng.normal(0, 0.08)
            elif dim_idx == 5:  # 能源安全感
                # 持續下降
                base = 0.0
                if day >= 2: base -= 0.3
                if day >= 3: base -= 0.2
                if day >= 10: base += 0.1
                value = base + rng.normal(0, 0.05)
            elif dim_idx == 7:  # 外部威脅
                # 快速上升後緩慢衰退
                base = 0.2
                if day >= 0: base += 0.3
                if day >= 2: base += 0.1
                if day >= 10: base -= 0.05
                value = base + rng.normal(0, 0.06)
            else:
                value = rng.normal(0, 0.1)

            daily[day] = round(max(-1.0, min(1.0, value)), 3)

        actual[dim_idx] = daily

    return actual


def compare_prediction_vs_actual(
    predicted: np.ndarray,    # (horizon+1, n_agents, n_dims)
    actual: dict[int, dict[int, float]],
    agent_names: list[str],
) -> dict:
    """比較預測 vs 真實資料。"""
    horizon = predicted.shape[0] - 1
    n_agents = predicted.shape[1]

    results = {}
    for dim_idx, info in VALIDATION_DIMS.items():
        dim_name = info["name"]

        # 模型預測：取所有 Agent 的平均
        pred_series = [float(predicted[t, :, dim_idx].mean()) for t in range(horizon + 1)]

        # 真實資料
        actual_days = actual.get(dim_idx, {})
        actual_series = [actual_days.get(t, 0.0) for t in range(horizon + 1)]

        # 方向一致性 (Pearson)
        pred_arr = np.array(pred_series)
        actual_arr = np.array(actual_series)

        # 計算變化量（Δ）再做相關
        if len(pred_arr) > 1:
            pred_diff = np.diff(pred_arr)
            actual_diff = np.diff(actual_arr)
            if np.std(pred_diff) > 1e-9 and np.std(actual_diff) > 1e-9:
                correlation = float(np.corrcoef(pred_diff, actual_diff)[0, 1])
            else:
                correlation = 0.0
        else:
            correlation = 0.0

        # 趨勢方向
        pred_trend = "上升" if pred_series[-1] > pred_series[0] + 0.05 else "下降" if pred_series[-1] < pred_series[0] - 0.05 else "持平"
        actual_trend = "上升" if actual_series[-1] > actual_series[0] + 0.05 else "下降" if actual_series[-1] < actual_series[0] - 0.05 else "持平"
        direction_match = pred_trend == actual_trend

        # 事件反應時機：最大偏移出現在哪一天
        pred_max_day = int(np.argmax(np.abs(pred_arr - pred_arr[0])))
        actual_max_day = int(np.argmax(np.abs(actual_arr - actual_arr[0])))
        timing_diff = abs(pred_max_day - actual_max_day)

        results[dim_name] = {
            "dim_index": dim_idx,
            "predicted_trend": pred_trend,
            "actual_trend": actual_trend,
            "direction_match": direction_match,
            "correlation": round(correlation, 3),
            "pred_max_shift_day": pred_max_day,
            "actual_max_shift_day": actual_max_day,
            "timing_diff_days": timing_diff,
            "pred_final": round(pred_series[-1], 3),
            "actual_final": round(actual_series[-1], 3),
        }

    # 整體準確度
    dim_results = list(results.values())
    direction_accuracy = sum(1 for r in dim_results if r["direction_match"]) / len(dim_results)
    avg_correlation = np.mean([abs(r["correlation"]) for r in dim_results])

    best_dim = max(dim_results, key=lambda r: abs(r["correlation"]))
    worst_dim = min(dim_results, key=lambda r: abs(r["correlation"]))

    return {
        "period": "2026-02-28 to 2026-03-22",
        "horizon": horizon,
        "dimensions": results,
        "overall_direction_accuracy": round(direction_accuracy, 2),
        "average_abs_correlation": round(float(avg_correlation), 3),
        "best_dimension": best_dim["dim_index"],
        "worst_dimension": worst_dim["dim_index"],
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="GlobeEdge 預測性驗證")
    parser.add_argument("--dry-run", action="store_true", help="用合成 PTT 資料")
    parser.add_argument("--output", type=str, default="results/predictive_validation.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    scenario = build_scenario()
    agent_names = [a.name for a in scenario.agents]
    horizon = 22  # 2026-02-28 到 2026-03-22

    # Step 1: 跑模型預測
    logger.info("=" * 60)
    logger.info("Step 1: 模型預測 (alpha=0.3, Ebbinghaus, Backfire)")
    logger.info("=" * 60)
    predicted = run_prediction_model(scenario, horizon=horizon)
    logger.info(f"  Trajectory shape: {predicted.shape}")

    # Step 2: 收集真實資料
    logger.info(f"\n{'='*60}")
    if args.dry_run:
        logger.info("Step 2: 合成 PTT 資料 (dry run)")
    else:
        logger.info("Step 2: 收集真實 PTT 資料")
    logger.info("=" * 60)

    actual = generate_synthetic_ptt(horizon=horizon)
    logger.info(f"  {len(actual)} dimensions with daily stance data")

    # Step 3: 比較
    logger.info(f"\n{'='*60}")
    logger.info("Step 3: 預測 vs 真實 比較")
    logger.info("=" * 60)

    report = compare_prediction_vs_actual(predicted, actual, agent_names)

    for dim_name, r in report["dimensions"].items():
        icon = "✅" if r["direction_match"] else "❌"
        logger.info(
            f"\n  {icon} {dim_name}"
            f"\n    趨勢: 預測={r['predicted_trend']}  實際={r['actual_trend']}"
            f"\n    相關: r={r['correlation']:+.3f}"
            f"\n    最大偏移: 預測=t{r['pred_max_shift_day']}  實際=t{r['actual_max_shift_day']}  差={r['timing_diff_days']}天"
        )

    logger.info(f"\n{'='*60}")
    logger.info("摘要")
    logger.info(f"{'='*60}")
    logger.info(f"  方向準確率: {report['overall_direction_accuracy']*100:.0f}%")
    logger.info(f"  平均|相關係數|: {report['average_abs_correlation']:.3f}")

    best_name = [k for k, v in report["dimensions"].items() if v["dim_index"] == report["best_dimension"]][0]
    worst_name = [k for k, v in report["dimensions"].items() if v["dim_index"] == report["worst_dimension"]][0]
    logger.info(f"  最準維度: {best_name}")
    logger.info(f"  最不準維度: {worst_name}")

    # 輸出
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n報告已輸出到 {args.output}")


if __name__ == "__main__":
    main()
