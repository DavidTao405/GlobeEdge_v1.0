"""EventAccumulator 驗證 — 持續危機 vs 一次性衝擊的信念演化比較。

用法:
    python scripts/test_accumulator.py

驗證:
    美伊戰爭的 6 個事件，3 天內連續發生 → 應觸發累積模式
    累積模式下經濟焦慮應持續上升（vs 回歸模式的震盪）
    比較兩者在 predictive_validation 合成資料上的方向準確率
"""

import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.core.psychology import (
    EventAccumulator,
    apply_forgetting,
    apply_forgetting_with_accumulator,
    apply_motivated_reasoning,
)
from globeedge.scenarios.iran_war import build as build_scenario
from scripts.predictive_validation import (
    IRAN_WAR_TIMELINE,
    VALIDATION_DIMS,
    generate_synthetic_ptt,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_with_mode(mode: str, scenario=None, horizon: int = 22) -> np.ndarray:
    """mode = 'normal' | 'accumulate'"""
    if scenario is None:
        scenario = build_scenario()

    B0 = scenario.belief_matrix()
    W = scenario.default_W()
    agent_types = scenario.agent_types()
    n_agents, n_dims = B0.shape
    alpha = scenario.alpha

    W_mod = apply_motivated_reasoning(W, B0)

    # 建立事件
    events = {}
    for evt in IRAN_WAR_TIMELINE:
        day = evt["day"]
        if day <= horizon:
            impact = np.zeros((n_agents, n_dims))
            for i in range(n_agents):
                impact[i] = evt["impact"]
            events[day] = impact

    accumulator = EventAccumulator() if mode == "accumulate" else None

    trajectory = []
    B = B0.copy()
    for t in range(horizon + 1):
        trajectory.append(B.copy())
        if t >= horizon:
            break

        B_next = alpha * W_mod @ B + (1 - alpha) * B0

        if t in events:
            raw_impact = events[t]
            if accumulator:
                # 用 Agent 0 的 impact 代表事件方向
                eff_impact_1d = accumulator.process_event(
                    day=t,
                    impact=raw_impact[0],
                    title=next((e["title"] for e in IRAN_WAR_TIMELINE if e["day"] == t), ""),
                )
                # 廣播到所有 Agent
                eff_impact = np.zeros_like(raw_impact)
                for i in range(n_agents):
                    eff_impact[i] = eff_impact_1d
                B_next = B_next + eff_impact
            else:
                B_next = B_next + raw_impact

        B_next = np.clip(B_next, -1.0, 1.0)

        if mode == "accumulate" and accumulator:
            B_next = apply_forgetting_with_accumulator(B_next, B0, agent_types, accumulator)
        else:
            B_next = apply_forgetting(B_next, B0, agent_types)

        B_next = np.clip(B_next, -1.0, 1.0)
        B = B_next

    return np.array(trajectory)


def compute_accuracy(traj: np.ndarray, actual: dict) -> tuple[float, dict]:
    """計算方向準確率。"""
    horizon = traj.shape[0] - 1
    results = {}
    for dim_idx, info in VALIDATION_DIMS.items():
        pred = [float(traj[t, :, dim_idx].mean()) for t in range(horizon + 1)]
        act = [actual.get(dim_idx, {}).get(t, 0.0) for t in range(horizon + 1)]

        pred_delta = pred[-1] - pred[0]
        act_delta = act[-1] - act[0]
        match = (pred_delta > 0.05 and act_delta > 0.05) or \
                (pred_delta < -0.05 and act_delta < -0.05) or \
                (abs(pred_delta) <= 0.05 and abs(act_delta) <= 0.05)

        results[info["name"]] = {
            "pred_delta": round(pred_delta, 4),
            "actual_delta": round(act_delta, 4),
            "match": match,
        }

    acc = sum(1 for r in results.values() if r["match"]) / len(results)
    return acc, results


def main():
    scenario = build_scenario()
    actual = generate_synthetic_ptt(horizon=22)

    logger.info("=" * 70)
    logger.info("  EventAccumulator 驗證：持續危機 vs 一次性衝擊")
    logger.info("=" * 70)

    # 測試累積判斷
    logger.info("\n--- 累積判斷測試 ---")
    acc = EventAccumulator()
    for evt in IRAN_WAR_TIMELINE:
        impact = np.array(evt["impact"])
        should = acc.should_accumulate(evt["day"], impact)
        eff = acc.process_event(evt["day"], impact, evt["title"])
        logger.info(
            f"  t={evt['day']:2d}  {evt['title']:30s}  "
            f"累積={'是' if should else '否'}  "
            f"crisis_len={acc.crisis_length}  "
            f"eff_dim3={eff[3]:+.3f}"
        )

    logger.info(f"  → 危機序列長度: {acc.crisis_length}")
    logger.info(f"  → 正處於危機: {acc.is_in_crisis}")

    # 跑兩個版本
    logger.info(f"\n{'='*70}")
    logger.info("  模式比較")
    logger.info("=" * 70)

    traj_normal = run_with_mode("normal", scenario)
    traj_accum = run_with_mode("accumulate", scenario)

    # 經濟焦慮度 (dim 3) 時序比較
    logger.info(f"\n  dim3 (經濟焦慮度) 時序比較:")
    logger.info(f"  {'t':>3s}  {'Normal':>8s}  {'Accumulate':>10s}  {'Actual':>8s}")
    for t in range(0, 23, 2):
        normal_val = float(traj_normal[t, :, 3].mean())
        accum_val = float(traj_accum[t, :, 3].mean())
        actual_val = actual.get(3, {}).get(t, 0.0)
        logger.info(f"  {t:3d}  {normal_val:+8.3f}  {accum_val:+10.3f}  {actual_val:+8.3f}")

    # 方向準確率比較
    logger.info(f"\n{'='*70}")
    logger.info("  方向準確率比較")
    logger.info("=" * 70)

    acc_normal, res_normal = compute_accuracy(traj_normal, actual)
    acc_accum, res_accum = compute_accuracy(traj_accum, actual)

    logger.info(f"\n  {'維度':15s}  {'Normal':>10s}  {'Accumulate':>12s}  {'Actual':>10s}")
    for dim_name in res_normal:
        rn = res_normal[dim_name]
        ra = res_accum[dim_name]
        icon_n = "✅" if rn["match"] else "❌"
        icon_a = "✅" if ra["match"] else "❌"
        logger.info(
            f"  {dim_name:15s}  "
            f"{icon_n} Δ={rn['pred_delta']:+.4f}  "
            f"{icon_a} Δ={ra['pred_delta']:+.4f}  "
            f"actual={rn['actual_delta']:+.4f}"
        )

    logger.info(f"\n  Normal 準確率:      {acc_normal*100:.0f}% ({int(acc_normal*4)}/4)")
    logger.info(f"  Accumulate 準確率:  {acc_accum*100:.0f}% ({int(acc_accum*4)}/4)")
    improvement = acc_accum - acc_normal
    logger.info(f"  改善: {improvement*100:+.0f}%")

    if improvement > 0:
        logger.info(f"\n  ✅ EventAccumulator 提升了預測準確率！")
        logger.info(f"     持續危機模式更符合真實輿論演化。")
    elif improvement == 0:
        logger.info(f"\n  ⚠️ 兩種模式準確率相同。")
    else:
        logger.info(f"\n  ❌ EventAccumulator 未改善準確率。")

    # 累積抑制遺忘的效果
    logger.info(f"\n{'='*70}")
    logger.info("  Ebbinghaus 抑制效果")
    logger.info("=" * 70)
    suppression = acc.get_suppression_mask()
    if suppression is not None:
        dims_suppressed = [i for i, s in enumerate(suppression) if s]
        logger.info(f"  抑制遺忘的維度: {dims_suppressed}")
        logger.info(f"  含義: 這些維度在持續危機中不會被 Ebbinghaus 拉回 b(0)")


if __name__ == "__main__":
    main()
