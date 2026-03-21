"""心理機制驗證實驗。

用能源政策的停電事件驗證：
1. Ebbinghaus: PTT 八卦板在停電後比 FJ 更快回到 b(0)
2. Motivated Reasoning: 反核/擁核 KOL 之間的 W 矩陣影響力趨近 0
3. ELM: 高 involvement Agent 信念更新更持久

用法：python scripts/test_psychology.py
"""

import sys
sys.path.insert(0, ".")

import numpy as np
from globeedge.core import FJEngine, PsychologyConfig
from globeedge.core.psychology import (
    apply_forgetting, apply_motivated_reasoning,
    compute_retention, compute_alpha_elm,
)
from globeedge.core.belief_state import BeliefState


def test_ebbinghaus():
    """驗證 H1: PTT 八卦板在停電事件後比 FJ 更快回到 b(0)。"""
    print("=" * 60)
    print("  Test 1: Ebbinghaus Forgetting")
    print("=" * 60)

    # 能源政策 Agent
    names = ["台電官方", "反核KOL", "擁核KOL", "一般家戶", "PTT八卦板"]
    types = ["institution", "kol", "kol", "demographic", "forum"]

    B0 = np.array([
        [0.2, 0.3, 0.0, 0.1, -0.3, 0.5, 0.2, 0.1],
        [0.0, 0.1, 0.2, 0.2, -0.8, 0.7, -0.1, 0.0],
        [-0.1, -0.1, -0.1, 0.3, 0.7, -0.2, -0.1, 0.3],
        [-0.2, -0.1, -0.3, 0.5, 0.0, 0.1, -0.1, 0.1],
        [-0.4, -0.3, -0.2, 0.3, 0.1, 0.0, -0.2, 0.2],
    ])
    W = np.full((5, 5), 0.1)
    np.fill_diagonal(W, 0)

    # 停電事件 impact
    event = np.zeros((5, 8))
    event[:, 3] = 0.8   # 經濟焦慮暴增
    event[:, 4] = 0.4   # 核電接受度上升

    engine_fj = FJEngine(alpha=0.3, b0=B0)
    engine_eb = FJEngine(alpha=0.3, b0=B0)

    initial = BeliefState(t=0, B=B0.copy(), W=W, timestamp=None)

    # Run FJ (無遺忘)
    traj_fj = engine_fj.run(initial, horizon=30, events={5: event})

    # Run FJ + Ebbinghaus
    traj_eb = engine_eb.run(initial, horizon=30, events={5: event},
                            use_forgetting=True, agent_types=types)

    # 比較 PTT 八卦板 (idx=4) 停電後的恢復
    ptt_idx = 4
    dim_anxiety = 3  # 經濟焦慮
    print(f"\n  PTT 八卦板 (S={compute_retention('forum'):.3f}) 經濟焦慮恢復：")
    print(f"  {'t':>4s}  {'FJ':>8s}  {'Ebbinghaus':>10s}  {'Δ':>8s}")
    for t in [4, 5, 6, 7, 8, 10, 15, 20, 30]:
        fj_val = traj_fj[t].B[ptt_idx, dim_anxiety]
        eb_val = traj_eb[t].B[ptt_idx, dim_anxiety]
        print(f"  {t:4d}  {fj_val:+.4f}  {eb_val:+.4f}  {eb_val - fj_val:+.4f}")

    # 驗證：Ebbinghaus 版本在 t=8 就應該比 FJ 更接近 b(0)
    b0_ptt = B0[ptt_idx, dim_anxiety]
    fj_dist = abs(traj_fj[8].B[ptt_idx, dim_anxiety] - b0_ptt)
    eb_dist = abs(traj_eb[8].B[ptt_idx, dim_anxiety] - b0_ptt)
    ok = eb_dist < fj_dist
    print(f"\n  t=8 距離 b(0): FJ={fj_dist:.4f}  Ebbinghaus={eb_dist:.4f}  EB更近={ok}")
    assert ok, "Ebbinghaus should recover faster than pure FJ"
    print("  ✅ PASSED")

    # 比較所有 Agent 的恢復速度
    print(f"\n  各 Agent t=15 距離 b(0):")
    for i, (name, atype) in enumerate(zip(names, types)):
        fj_d = np.linalg.norm(traj_fj[15].B[i] - B0[i])
        eb_d = np.linalg.norm(traj_eb[15].B[i] - B0[i])
        ret = compute_retention(atype)
        print(f"    {name:12s} ({atype:12s} R={ret:.3f})  FJ={fj_d:.4f}  EB={eb_d:.4f}")


def test_motivated_reasoning():
    """驗證 H2: 反核/擁核 KOL 之間的 W 影響力趨近 0。"""
    print(f"\n{'=' * 60}")
    print("  Test 2: Motivated Reasoning (Backfire Effect)")
    print("=" * 60)

    B0 = np.array([
        [0.0, 0.1, 0.2, 0.2, -0.8, 0.7, -0.1, 0.0],  # 反核 KOL
        [-0.1, -0.1, -0.1, 0.3, 0.7, -0.2, -0.1, 0.3],  # 擁核 KOL
        [-0.2, -0.1, -0.3, 0.5, 0.0, 0.1, -0.1, 0.1],  # 一般家戶
    ])
    W = np.array([
        [0.0, 0.15, 0.1],
        [0.15, 0.0, 0.1],
        [0.12, 0.12, 0.0],
    ])

    W_motivated = apply_motivated_reasoning(W, B0, identity_threshold=0.5, k=3.0)

    distance_01 = np.linalg.norm(B0[0] - B0[1])
    distance_02 = np.linalg.norm(B0[0] - B0[2])

    print(f"\n  反核↔擁核 距離: {distance_01:.3f}")
    print(f"  反核↔家戶 距離: {distance_02:.3f}")
    print(f"\n  W[反核][擁核]: {W[0,1]:.3f} → {W_motivated[0,1]:.3f}")
    print(f"  W[擁核][反核]: {W[1,0]:.3f} → {W_motivated[1,0]:.3f}")
    print(f"  W[家戶][反核]: {W[2,0]:.3f} → {W_motivated[2,0]:.3f}")
    print(f"  W[家戶][擁核]: {W[2,1]:.3f} → {W_motivated[2,1]:.3f}")

    # 驗證：反核↔擁核的影響力應該大幅降低
    ok = W_motivated[0, 1] < W[0, 1] * 0.5
    print(f"\n  反核→擁核影響力降幅: {(1 - W_motivated[0,1]/W[0,1])*100:.1f}%  >50%={ok}")
    assert ok, "Motivated reasoning should reduce cross-camp influence by >50%"
    print("  ✅ PASSED")


def test_elm():
    """驗證 H3: ELM 雙路徑 — 高 involvement 更持久。"""
    print(f"\n{'=' * 60}")
    print("  Test 3: ELM Dual Pathway")
    print("=" * 60)

    # 兩個 Agent：高 involvement vs 低 involvement
    names = ["科技業從業者", "一般家戶"]
    involvements = [0.8, 0.2]

    for name, inv in zip(names, involvements):
        alpha_eff, decay = compute_alpha_elm(0.3, inv)
        route = "Central" if inv > 0.5 else "Peripheral"
        print(f"  {name:12s} involvement={inv}  → {route:10s} alpha_eff={alpha_eff:.2f} decay={decay:.2f}")

    # 高 involvement 的 decay 應該更小
    _, d_high = compute_alpha_elm(0.3, 0.8)
    _, d_low = compute_alpha_elm(0.3, 0.2)
    ok = d_high < d_low
    print(f"\n  High involvement decay={d_high:.2f} < Low involvement decay={d_low:.2f}  correct={ok}")
    assert ok, "High involvement should have lower decay (more persistent)"
    print("  ✅ PASSED")


def test_combined():
    """驗證 H4: 同時啟用遺忘 + 動機性推理。"""
    print(f"\n{'=' * 60}")
    print("  Test 4: Combined (Forgetting + Motivated Reasoning)")
    print("=" * 60)

    B0 = np.array([
        [0.0, 0.1, 0.2, 0.2, -0.8, 0.7, -0.1, 0.0],  # 反核 KOL
        [-0.1, -0.1, -0.1, 0.3, 0.7, -0.2, -0.1, 0.3],  # 擁核 KOL
        [-0.4, -0.3, -0.2, 0.3, 0.1, 0.0, -0.2, 0.2],  # PTT
    ])
    W = np.full((3, 3), 0.12)
    np.fill_diagonal(W, 0)
    types = ["kol", "kol", "forum"]

    # 先做動機性推理修正 W
    W_motivated = apply_motivated_reasoning(W, B0)

    # 跑仿真
    engine = FJEngine(alpha=0.3, b0=B0)
    event = np.zeros((3, 8))
    event[:, 3] = 0.6
    initial = BeliefState(t=0, B=B0.copy(), W=W_motivated, timestamp=None)

    traj = engine.run(initial, horizon=20, events={3: event},
                      use_forgetting=True, agent_types=types)

    # PTT 應該恢復最快（forum S=2）
    ptt_d = np.linalg.norm(traj[10].B[2] - B0[2])
    kol_d = np.linalg.norm(traj[10].B[0] - B0[0])
    print(f"  t=10: PTT dist={ptt_d:.4f}  KOL dist={kol_d:.4f}")
    ok = ptt_d < kol_d
    print(f"  PTT recovers faster than KOL: {ok}")
    assert ok
    print("  ✅ PASSED")


if __name__ == "__main__":
    test_ebbinghaus()
    test_motivated_reasoning()
    test_elm()
    test_combined()
    print(f"\n{'=' * 60}")
    print("  ALL PSYCHOLOGY TESTS PASSED ✅")
    print(f"{'=' * 60}")
