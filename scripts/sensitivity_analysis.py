"""敏感度分析 — 心理機制參數的結論穩健性檢驗。

用法:
    python scripts/sensitivity_analysis.py
    python scripts/sensitivity_analysis.py --output results/sensitivity.csv

目的:
    在 PTT 真實資料累積之前，先確認：
    「在合理參數範圍內，結論是否 robust？」
    如果結論不變 → 即使 S 值不精確，結論仍可信。

掃描維度:
    Layer 1 (Ebbinghaus): S_forum in [1, 2, 3, 5, 8, 15]
    Layer 3 (動機性推理): threshold in [0.3, 0.4, 0.5, 0.6, 0.7]
                          k in [1.0, 2.0, 3.0, 5.0]

輸出指標:
    - PTT 恢復時步（停電後回到 b(0) ± 0.05 的步數）
    - 最終 spread（反核 vs 擁核 KOL 的信念距離）
    - λ_max
    - 反核↔擁核 KOL 殘餘影響力（W_motivated 值）
"""

import csv
import json
import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.core import FJEngine, MonteCarloRunner
from globeedge.core.psychology import (
    MEMORY_STABILITY,
    PsychologyConfig,
    apply_forgetting,
    apply_motivated_reasoning,
)
from globeedge.scenarios.energy import build as build_scenario

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_single(
    S_forum: float,
    threshold: float,
    k: float,
    scenario=None,
) -> dict:
    """跑一次能源政策仿真，回傳指標。"""
    if scenario is None:
        scenario = build_scenario()

    B0 = scenario.belief_matrix()
    W = scenario.default_W()
    agent_types = scenario.agent_types()
    agent_names = [a.name for a in scenario.agents]
    n_agents = scenario.n_agents
    n_dims = 8
    horizon = scenario.sim_horizon
    alpha = scenario.alpha

    # 找關鍵 Agent index
    ptt_idx = next((i for i, a in enumerate(scenario.agents) if "PTT" in a.name), None)
    antinuke_idx = next((i for i, a in enumerate(scenario.agents) if "反核" in a.name), None)
    pronuke_idx = next((i for i, a in enumerate(scenario.agents) if "擁核" in a.name), None)

    # 覆蓋 S_forum
    memory_override = dict(MEMORY_STABILITY)
    memory_override["forum"] = S_forum

    # 套用動機性推理
    W_mod = apply_motivated_reasoning(W, B0, identity_threshold=threshold, k=k)

    # 計算反核↔擁核殘餘影響力
    residual_influence = 0.0
    if antinuke_idx is not None and pronuke_idx is not None:
        residual_influence = (
            W_mod[antinuke_idx, pronuke_idx] + W_mod[pronuke_idx, antinuke_idx]
        ) / 2

    # λ_max
    eigenvalues = np.linalg.eigvals(W_mod)
    lambda_max = float(np.max(np.abs(eigenvalues)))

    # 跑 FJ + Ebbinghaus
    engine = FJEngine(alpha=alpha, b0=B0)
    # 停電事件在 t=12
    event_impact = np.zeros((n_agents, n_dims))
    event_impact[:, 3] = 0.6   # 經濟焦慮 ↑
    event_impact[:, 1] = -0.4  # 安全感 ↓
    events = {12: event_impact}

    trajectory = []
    B = B0.copy()
    for t in range(horizon + 1):
        trajectory.append(B.copy())
        if t < horizon:
            # FJ step
            B_next = alpha * W_mod @ B + (1 - alpha) * B0

            # 事件注入
            if t in events:
                B_next = B_next + events[t]

            B_next = np.clip(B_next, -1.0, 1.0)

            # Ebbinghaus 遺忘（用覆蓋值）
            for i, atype in enumerate(agent_types):
                S = memory_override.get(atype, 10.0)
                retention = float(np.exp(-1 / S))
                B_next[i] = B0[i] + retention * (B_next[i] - B0[i])

            B_next = np.clip(B_next, -1.0, 1.0)
            B = B_next

    trajectory = np.array(trajectory)  # (horizon+1, n_agents, n_dims)

    # PTT 恢復時步（停電後回到 b(0) ± 0.05）
    ptt_recovery = horizon  # 預設：未恢復
    if ptt_idx is not None:
        for t in range(13, horizon + 1):
            diff = float(np.max(np.abs(trajectory[t, ptt_idx] - B0[ptt_idx])))
            if diff < 0.05:
                ptt_recovery = t - 12  # 相對於事件的步數
                break

    # 最終 spread（反核 vs 擁核 KOL）
    final_spread = 0.0
    if antinuke_idx is not None and pronuke_idx is not None:
        final_spread = float(
            np.linalg.norm(trajectory[-1, antinuke_idx] - trajectory[-1, pronuke_idx])
        )

    return {
        "S_forum": S_forum,
        "threshold": threshold,
        "k": k,
        "lambda_max": round(lambda_max, 4),
        "ptt_recovery_steps": ptt_recovery,
        "final_spread": round(final_spread, 4),
        "residual_influence": round(residual_influence, 6),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="GlobeEdge 心理機制敏感度分析")
    parser.add_argument("--output", type=str, default="results/sensitivity.csv")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    scenario = build_scenario()

    # 參數掃描範圍
    S_forum_range = [1, 2, 3, 5, 8, 15]
    threshold_range = [0.3, 0.4, 0.5, 0.6, 0.7]
    k_range = [1.0, 2.0, 3.0, 5.0]

    # Layer 1 掃描（固定 threshold=0.5, k=3.0）
    logger.info("=" * 60)
    logger.info("Layer 1 (Ebbinghaus) 敏感度：S_forum 掃描")
    logger.info("=" * 60)

    results = []
    for S in S_forum_range:
        r = run_single(S_forum=S, threshold=0.5, k=3.0, scenario=scenario)
        results.append(r)
        logger.info(
            f"  S_forum={S:2d}  "
            f"recovery={r['ptt_recovery_steps']:2d} steps  "
            f"spread={r['final_spread']:.4f}  "
            f"λ_max={r['lambda_max']:.4f}"
        )

    # 找結論反轉點
    base_recovery = next(r["ptt_recovery_steps"] for r in results if r["S_forum"] == 2)
    for r in results:
        if r["ptt_recovery_steps"] > base_recovery * 3:
            logger.info(
                f"\n  ⚠️  反轉點：S_forum={r['S_forum']} 時，"
                f"PTT 恢復速度顯著變慢（{r['ptt_recovery_steps']} vs {base_recovery} steps）"
            )

    # Layer 3 掃描（固定 S_forum=2）
    logger.info(f"\n{'='*60}")
    logger.info("Layer 3 (動機性推理) 敏感度：threshold × k 掃描")
    logger.info("=" * 60)

    logger.info(f"\n  {'threshold':>10s} {'k':>5s} {'spread':>8s} {'residual':>10s} {'λ_max':>8s}")
    for threshold in threshold_range:
        for k_val in k_range:
            r = run_single(S_forum=2, threshold=threshold, k=k_val, scenario=scenario)
            results.append(r)
            logger.info(
                f"  {threshold:10.1f} {k_val:5.1f} "
                f"{r['final_spread']:8.4f} "
                f"{r['residual_influence']:10.6f} "
                f"{r['lambda_max']:8.4f}"
            )

    # 找 Backfire 反轉點
    logger.info(f"\n  反轉點分析：")
    for r in results:
        if r["residual_influence"] > 0.01 and r.get("threshold", 0) > 0:
            logger.info(
                f"    threshold={r['threshold']}, k={r['k']}: "
                f"殘餘影響力={r['residual_influence']:.4f} > 0.01 "
                f"→ Backfire 效應不足以完全阻斷影響"
            )

    # 輸出 CSV
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"\n結果已輸出到 {args.output}")
    logger.info(f"共 {len(results)} 個參數組合")

    # 摘要
    logger.info(f"\n{'='*60}")
    logger.info("摘要")
    logger.info(f"{'='*60}")

    spreads = [r["final_spread"] for r in results]
    recoveries = [r["ptt_recovery_steps"] for r in results]
    logger.info(f"  Spread 範圍: [{min(spreads):.4f}, {max(spreads):.4f}]")
    logger.info(f"  Recovery 範圍: [{min(recoveries)}, {max(recoveries)}] steps")

    # Robust 判定
    spread_stable = (max(spreads) - min(spreads)) / max(max(spreads), 0.001) < 0.3
    logger.info(
        f"\n  Spread 穩健性: {'✅ ROBUST' if spread_stable else '⚠️ SENSITIVE'} "
        f"(變異 {(max(spreads)-min(spreads))/max(max(spreads),0.001)*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
