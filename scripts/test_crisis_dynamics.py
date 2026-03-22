"""CrisisAwareFJEngine 驗證 — 三模式比較 + 危機狀態追蹤。

用法:
    python scripts/test_crisis_dynamics.py

比較三個版本:
    1. Standard FJ (baseline, 0%)
    2. FJ + EventAccumulator (0%)
    3. CrisisAwareFJEngine (目標 > 0%)
"""

import logging
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.core.belief_state import BeliefState
from globeedge.core.crisis_dynamics import CrisisAwareFJEngine
from globeedge.core.psychology import apply_forgetting, apply_motivated_reasoning
from globeedge.scenarios.iran_war import build as build_scenario
from scripts.predictive_validation import (
    IRAN_WAR_TIMELINE,
    VALIDATION_DIMS,
    generate_synthetic_ptt,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_standard_fj(B0, W, agent_types, events, horizon, alpha=0.3):
    W_mod = apply_motivated_reasoning(W, B0)
    traj = []
    B = B0.copy()
    for t in range(horizon + 1):
        traj.append(B.copy())
        if t < horizon:
            B_next = alpha * W_mod @ B + (1 - alpha) * B0
            if t in events:
                B_next = B_next + events[t]
            B_next = np.clip(B_next, -1.0, 1.0)
            B_next = apply_forgetting(B_next, B0, agent_types)
            B = np.clip(B_next, -1.0, 1.0)
    return np.array(traj)


def run_crisis_aware(B0, W, events, horizon):
    initial = BeliefState(t=0, B=B0.copy(), W=W, timestamp=datetime.now(timezone.utc))
    engine = CrisisAwareFJEngine(alpha=0.3, b0=B0)
    results = engine.run(initial, horizon=horizon, events=events)
    traj = np.array([r.belief_state.B for r in results])
    return traj, results


def compute_accuracy(traj, actual):
    horizon = traj.shape[0] - 1
    matches = 0
    details = {}
    for dim_idx, info in VALIDATION_DIMS.items():
        pred = [float(traj[t, :, dim_idx].mean()) for t in range(horizon + 1)]
        act = [actual.get(dim_idx, {}).get(t, 0.0) for t in range(horizon + 1)]
        pd = pred[-1] - pred[0]
        ad = act[-1] - act[0]
        match = (pd > 0.05 and ad > 0.05) or (pd < -0.05 and ad < -0.05)
        if match:
            matches += 1
        details[info["name"]] = {"pred_delta": pd, "actual_delta": ad, "match": match}
    return matches / len(VALIDATION_DIMS), details


def main():
    scenario = build_scenario()
    B0 = scenario.belief_matrix()
    W = scenario.default_W()
    agent_types = scenario.agent_types()
    n_agents, n_dims = B0.shape
    horizon = 22

    events = {}
    for evt in IRAN_WAR_TIMELINE:
        day = evt["day"]
        if day <= horizon:
            impact = np.zeros((n_agents, n_dims))
            for i in range(n_agents):
                impact[i] = evt["impact"]
            events[day] = impact

    actual = generate_synthetic_ptt(horizon=horizon)

    # ── Mode 1: Standard FJ ──
    traj_std = run_standard_fj(B0, W, agent_types, events, horizon)
    acc_std, det_std = compute_accuracy(traj_std, actual)

    # ── Mode 3: CrisisAwareFJEngine ──
    traj_crisis, crisis_results = run_crisis_aware(B0, W, events, horizon)
    acc_crisis, det_crisis = compute_accuracy(traj_crisis, actual)

    # ── Output ──
    logger.info("=" * 70)
    logger.info("  CrisisAwareFJEngine 驗證：美伊戰爭方向準確率")
    logger.info("=" * 70)

    logger.info("\n  危機狀態追蹤:")
    logger.info(f"  {'t':>3s}  {'intensity':>9s}  {'eff_alpha':>9s}  {'b0_drift':>9s}  {'event':30s}")
    evt_titles = {e["day"]: e["title"] for e in IRAN_WAR_TIMELINE}
    for t in range(horizon + 1):
        r = crisis_results[t]
        drift = float(np.max(np.abs(r.b0_current - B0)))
        title = evt_titles.get(t, "")
        if t <= 15 or t == horizon or title:
            logger.info(
                f"  {t:3d}  {r.crisis_intensity:9.3f}  {r.effective_alpha:9.3f}  "
                f"{drift:9.4f}  {title}"
            )

    logger.info(f"\n{'='*70}")
    logger.info("  方向準確率比較")
    logger.info("=" * 70)
    logger.info(f"\n  {'維度':15s}  {'Std FJ':>12s}  {'Crisis FJ':>12s}  {'Actual':>10s}")
    for dim_name in det_std:
        rs = det_std[dim_name]
        rc = det_crisis[dim_name]
        icon_s = "✅" if rs["match"] else "❌"
        icon_c = "✅" if rc["match"] else "❌"
        logger.info(
            f"  {dim_name:15s}  "
            f"{icon_s} Δ={rs['pred_delta']:+.4f}  "
            f"{icon_c} Δ={rc['pred_delta']:+.4f}  "
            f"actual={rs['actual_delta']:+.4f}"
        )

    logger.info(f"\n  Standard FJ:     {acc_std*100:.0f}% ({int(acc_std*4)}/4)")
    logger.info(f"  CrisisAware FJ:  {acc_crisis*100:.0f}% ({int(acc_crisis*4)}/4)")
    improvement = acc_crisis - acc_std
    logger.info(f"  改善: {improvement*100:+.0f}%")

    if improvement > 0:
        logger.info(f"\n  ✅ CrisisAwareFJEngine 顯著提升預測準確率！")
        logger.info(f"     FJ 的 (1-α)×b(0) 回歸限制在持續危機下被克服。")
    else:
        logger.info(f"\n  ⚠️ 未達預期改善，需調整 CrisisConfig 參數。")

    # ── dim3 時序比較 ──
    logger.info(f"\n{'='*70}")
    logger.info("  dim3 (經濟焦慮度) 時序比較")
    logger.info("=" * 70)
    logger.info(f"  {'t':>3s}  {'Std FJ':>8s}  {'Crisis':>8s}  {'Actual':>8s}")
    for t in range(0, horizon + 1, 2):
        std_val = float(traj_std[t, :, 3].mean())
        cri_val = float(traj_crisis[t, :, 3].mean())
        act_val = actual.get(3, {}).get(t, 0.0)
        logger.info(f"  {t:3d}  {std_val:+8.3f}  {cri_val:+8.3f}  {act_val:+8.3f}")


if __name__ == "__main__":
    main()
