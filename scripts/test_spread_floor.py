"""Spread Floor 測試 — 找出 alpha 崩潰臨界 + 驗證保護機制。

用法:
    PYTHONPATH=. python scripts/test_spread_floor.py

目標：
  1. 找出 alpha 在什麼值讓信念向量收斂到同質（spread < 0.1 = 崩潰）
  2. 驗證 spread floor 保護機制能否防止崩潰
  3. 確認 alpha=0.3（現有校準值）在安全範圍內

輸出：results/spread_floor_test.json
"""

import json
import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def compute_spread(B: np.ndarray) -> float:
    """所有 Agent 信念向量的標準差均值。

    spread < 0.1 定義為崩潰（信念同質化）。
    """
    # B shape: (n_agents, n_dims)
    return float(np.mean(np.std(B, axis=0)))


def run_fj_no_events(B0, W, b0, alpha, horizon):
    """原始 FJ，無外部事件，無保護。"""
    B = B0.copy()
    spreads = [compute_spread(B)]

    for t in range(horizon):
        B = alpha * W @ B + (1 - alpha) * b0
        B = np.clip(B, -1.0, 1.0)
        spreads.append(compute_spread(B))

    return B, spreads


def run_fj_with_floor(B0, W, b0, alpha, horizon, min_spread=0.15):
    """FJ + spread floor 保護。

    當 spread 低於 min_spread 時，動態降低 alpha 阻止收斂。
    """
    B = B0.copy()
    spreads = [compute_spread(B)]
    alpha_history = [alpha]

    for t in range(horizon):
        b_next = alpha * W @ B + (1 - alpha) * b0
        current_spread = compute_spread(b_next)

        if current_spread < min_spread:
            # 動態降低 alpha，減少社會影響力的收斂壓力
            ratio = current_spread / min_spread
            alpha_adj = alpha * ratio
            b_next = alpha_adj * W @ B + (1 - alpha_adj) * b0
            alpha_history.append(alpha_adj)
        else:
            alpha_history.append(alpha)

        B = np.clip(b_next, -1.0, 1.0)
        spreads.append(compute_spread(B))

    return B, spreads, alpha_history


def main():
    from globeedge.scenarios.energy import build

    scenario = build()
    B0 = scenario.belief_matrix()
    W = scenario.default_W()
    b0 = B0.copy()  # FJ 固有信念 = 初始信念
    horizon = 30
    n_agents, n_dims = B0.shape

    initial_spread = compute_spread(B0)

    logger.info("=" * 70)
    logger.info("  GlobeEdge Spread Floor Test — 能源政策議題")
    logger.info("=" * 70)
    logger.info(f"  Agents: {n_agents}  Dims: {n_dims}  Horizon: {horizon}")
    logger.info(f"  Initial spread: {initial_spread:.4f}")
    logger.info("")

    # ── Step 1: Alpha 掃描（無保護）────────────────────────
    logger.info("Step 1: Alpha 掃描（無保護）")
    logger.info("-" * 60)

    alphas = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    results_no_protection = {}
    collapse_alpha = None

    for alpha in alphas:
        B_final, spreads = run_fj_no_events(B0, W, b0, alpha, horizon)
        final_spread = spreads[-1]
        min_spread_seen = min(spreads)
        collapsed = final_spread < 0.1
        status = "COLLAPSE" if collapsed else "OK"

        if collapsed and collapse_alpha is None:
            collapse_alpha = alpha

        results_no_protection[alpha] = {
            "final_spread": round(final_spread, 4),
            "min_spread": round(min_spread_seen, 4),
            "initial_spread": round(spreads[0], 4),
            "collapsed": collapsed,
        }

        bar = "█" * int(final_spread * 50)
        logger.info(
            f"  alpha={alpha:.1f}  spread={final_spread:.4f}  "
            f"min={min_spread_seen:.4f}  [{status:8s}]  {bar}"
        )

    if collapse_alpha:
        logger.info(f"\n  ⚠️  崩潰臨界 alpha = {collapse_alpha}")
    else:
        logger.info(f"\n  ✅  在 alpha=[0.1, 0.9] 範圍內無崩潰")

    # ── Step 2: Spread Floor 保護 ─────────────────────────
    logger.info("")
    logger.info("Step 2: Spread Floor 保護 (min_spread=0.15)")
    logger.info("-" * 60)

    min_spread_threshold = 0.15
    results_with_protection = {}

    for alpha in alphas:
        B_final, spreads, alpha_hist = run_fj_with_floor(
            B0, W, b0, alpha, horizon, min_spread_threshold
        )
        final_spread = spreads[-1]
        collapsed = final_spread < 0.1
        alpha_reductions = sum(1 for a in alpha_hist if a < alpha)
        status = "COLLAPSE" if collapsed else "PROTECTED" if alpha_reductions > 0 else "OK"

        results_with_protection[alpha] = {
            "final_spread": round(final_spread, 4),
            "collapsed": collapsed,
            "alpha_reductions": alpha_reductions,
            "min_alpha_used": round(min(alpha_hist), 4),
        }

        bar = "█" * int(final_spread * 50)
        logger.info(
            f"  alpha={alpha:.1f}  spread={final_spread:.4f}  "
            f"reductions={alpha_reductions:2d}  [{status:10s}]  {bar}"
        )

    # ── Step 3: 比較表 ─────────────────────────────────────
    logger.info("")
    logger.info("Step 3: 比較表")
    logger.info("-" * 60)
    logger.info(
        f"  {'alpha':>5s} | {'spread 無保護':>14s} | {'spread 有保護':>14s} | "
        f"{'Δ':>8s} | {'崩潰?':>6s}"
    )
    logger.info(f"  {'-'*5}-+-{'-'*14}-+-{'-'*14}-+-{'-'*8}-+-{'-'*6}")

    for alpha in alphas:
        s_no = results_no_protection[alpha]["final_spread"]
        s_yes = results_with_protection[alpha]["final_spread"]
        delta = s_yes - s_no
        collapsed_no = results_no_protection[alpha]["collapsed"]
        collapsed_yes = results_with_protection[alpha]["collapsed"]

        if collapsed_no and not collapsed_yes:
            status = "✅ 救回"
        elif collapsed_no and collapsed_yes:
            status = "❌ 失敗"
        else:
            status = "── 安全"

        marker = " ← 現有校準值" if alpha == 0.3 else ""
        logger.info(
            f"  {alpha:5.1f} | {s_no:14.4f} | {s_yes:14.4f} | "
            f"{delta:+8.4f} | {status}{marker}"
        )

    # ── Step 4: 結論 ───────────────────────────────────────
    logger.info("")
    logger.info("結論:")
    logger.info("-" * 60)

    alpha_03_spread = results_no_protection[0.3]["final_spread"]
    alpha_03_safe = not results_no_protection[0.3]["collapsed"]

    if alpha_03_safe:
        logger.info(f"  ✅ alpha=0.3 在安全範圍內 (spread={alpha_03_spread:.4f} > 0.1)")
    else:
        logger.info(f"  ⚠️ alpha=0.3 已經崩潰！(spread={alpha_03_spread:.4f})")

    if collapse_alpha:
        logger.info(f"  ⚠️ 崩潰臨界 alpha = {collapse_alpha}")
        logger.info(f"     alpha > {collapse_alpha} 時需要 spread floor 保護")

        # 驗證保護有效性
        all_protected = all(
            not results_with_protection[a]["collapsed"]
            for a in alphas
        )
        if all_protected:
            logger.info(f"  ✅ spread floor 在所有 alpha 值都有效防止崩潰")
        else:
            failed = [a for a in alphas if results_with_protection[a]["collapsed"]]
            logger.info(f"  ⚠️ spread floor 在 alpha={failed} 仍然崩潰")
    else:
        logger.info(f"  能源政策議題在 alpha=[0.1, 0.9] 範圍內不會崩潰")
        logger.info(f"  spread floor 為額外保護層，不影響正常運作")

    # ── 輸出 JSON ─────────────────────────────────────────
    os.makedirs("results", exist_ok=True)
    report = {
        "scenario": "energy_policy",
        "n_agents": n_agents,
        "n_dims": n_dims,
        "horizon": horizon,
        "initial_spread": round(initial_spread, 4),
        "collapse_alpha": collapse_alpha,
        "alpha_03_safe": alpha_03_safe,
        "alpha_03_spread": round(alpha_03_spread, 4),
        "min_spread_threshold": min_spread_threshold,
        "no_protection": {str(k): v for k, v in results_no_protection.items()},
        "with_protection": {str(k): v for k, v in results_with_protection.items()},
    }

    with open("results/spread_floor_test.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n  輸出：results/spread_floor_test.json")


if __name__ == "__main__":
    main()
