"""跨議題耦合仿真 — 2026-03 台灣三議題並行。

用法:
    python scripts/run_cross_topic.py
    python scripts/run_cross_topic.py --no-wbc     # 不注入 WBC 事件
    python scripts/run_cross_topic.py --no-coupling # 關閉耦合（對照組）

三個議題同時跑：
    美伊戰爭（議題 5）→ 經濟焦慮 + 外部威脅
    大罷免潮（議題 6）→ 政治極化 + 群體凝聚
    能源政策（議題 1）→ 核電/再生爭議

核心觀察：
    1. WBC 對罷免動員的注意力稀釋效果
    2. 美伊戰爭的經濟焦慮如何滲透到能源政策
    3. 三議題並發時哪個被犧牲
"""

import argparse
import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.core.cross_topic import (
    AttentionBudget,
    CrossTopicEngine,
    CrossTopicEvent,
    OIL_PRICE_SPIKE,
    TopicState,
    WBC_TEAMTAIWAN,
)
from globeedge.scenarios.energy import build as build_energy
from globeedge.scenarios.iran_war import build as build_iran
from globeedge.scenarios.recall import build as build_recall

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def scenario_to_topic_state(scenario, topic_id: str) -> TopicState:
    """把 Scenario 轉成 TopicState。"""
    B0 = scenario.belief_matrix()
    W = scenario.default_W()
    agent_types = scenario.agent_types()

    # 建立事件 dict
    events = {}
    for i, evt in enumerate(scenario.events):
        t = i * 4 + 3  # 每個事件間隔 4 步
        impact = np.zeros_like(B0)
        for j in range(B0.shape[0]):
            impact[j] = evt.impact_vector
        events[t] = impact

    return TopicState(
        topic_id=topic_id,
        B=B0.copy(),
        B0=B0,
        W=W,
        agent_types=agent_types,
        alpha=scenario.alpha,
        events=events,
    )


def find_shared_agents(scenarios: dict) -> dict[str, dict[str, int]]:
    """找出跨議題的共享 Agent（名稱匹配）。"""
    # 收集所有 Agent 名稱
    all_names: dict[str, dict[str, int]] = {}

    for topic_id, scenario in scenarios.items():
        for i, agent in enumerate(scenario.agents):
            name = agent.name
            if name not in all_names:
                all_names[name] = {}
            all_names[name][topic_id] = i

    # 只保留出現在 ≥2 個議題的 Agent
    shared = {
        name: indices
        for name, indices in all_names.items()
        if len(indices) >= 2
    }
    return shared


def main():
    parser = argparse.ArgumentParser(description="GlobeEdge 跨議題耦合仿真")
    parser.add_argument("--no-wbc", action="store_true", help="不注入 WBC 事件")
    parser.add_argument("--no-coupling", action="store_true", help="關閉耦合（對照組）")
    parser.add_argument("--horizon", type=int, default=30)
    args = parser.parse_args()

    # 建立三個議題
    scenarios = {
        "energy": build_energy(),
        "iran_war": build_iran(),
        "recall": build_recall(),
    }

    # 轉換成 TopicState
    topics = {
        tid: scenario_to_topic_state(s, tid)
        for tid, s in scenarios.items()
    }

    # 找共享 Agent
    shared = find_shared_agents(scenarios)

    logger.info("=" * 70)
    logger.info("  GlobeEdge 跨議題耦合仿真")
    logger.info("=" * 70)
    logger.info(f"  議題: {list(topics.keys())}")
    logger.info(f"  共享 Agent: {len(shared)}")
    for name, indices in shared.items():
        logger.info(f"    {name}: {list(indices.keys())}")
    logger.info(f"  耦合: {'關閉' if args.no_coupling else '開啟'}")
    logger.info(f"  WBC 事件: {'無' if args.no_wbc else '注入 t=15'}")
    logger.info(f"  Horizon: {args.horizon}")

    # 跨議題事件
    cross_events = []
    if not args.no_wbc:
        cross_events.append(WBC_TEAMTAIWAN)
    cross_events.append(OIL_PRICE_SPIKE)

    # 跑耦合仿真
    engine = CrossTopicEngine(
        topics=topics,
        shared_agent_map=shared if not args.no_coupling else {},
        bleed_rate=0.15 if not args.no_coupling else 0.0,
        base_salience={"energy": 0.25, "iran_war": 0.35, "recall": 0.25},
    )

    results = engine.run(horizon=args.horizon, cross_events=cross_events)

    # 分析結果
    logger.info(f"\n{'='*70}")
    logger.info("  結果分析")
    logger.info("=" * 70)

    for tid in results:
        traj = results[tid]
        scenario = scenarios[tid]
        agent_names = [a.name for a in scenario.agents]
        B0 = scenario.belief_matrix()

        # 每個議題的維度變化
        logger.info(f"\n  ── {scenario.name} ({tid}) ──")
        for dim_idx in [0, 3, 6, 7]:
            dim_label = scenario.dimensions[dim_idx].label if dim_idx < len(scenario.dimensions) else f"dim_{dim_idx}"
            initial_mean = float(traj[0, :, dim_idx].mean())
            final_mean = float(traj[-1, :, dim_idx].mean())
            delta = final_mean - initial_mean
            logger.info(
                f"    dim{dim_idx} ({dim_label:15s}): "
                f"init={initial_mean:+.3f}  final={final_mean:+.3f}  "
                f"Δ={delta:+.4f}"
            )

    # WBC 注意力稀釋效果分析
    if not args.no_wbc:
        logger.info(f"\n{'='*70}")
        logger.info("  WBC 注意力稀釋效果")
        logger.info("=" * 70)

        recall_traj = results["recall"]
        # dim 6 = 群體凝聚度（WBC 應該短暫提升）
        pre_wbc = float(recall_traj[14, :, 6].mean())
        at_wbc = float(recall_traj[16, :, 6].mean())
        post_wbc = float(recall_traj[20, :, 6].mean())
        logger.info(f"  罷免-群體凝聚度: pre={pre_wbc:+.3f}  @WBC={at_wbc:+.3f}  post={post_wbc:+.3f}")

        # dim 4 = 罷免認同度（WBC 應該暫時降低）
        pre_4 = float(recall_traj[14, :, 4].mean())
        at_4 = float(recall_traj[16, :, 4].mean())
        logger.info(f"  罷免-政治改革意願: pre={pre_4:+.3f}  @WBC={at_4:+.3f}  Δ={at_4-pre_4:+.4f}")

    # 跨議題經濟焦慮滲透
    logger.info(f"\n{'='*70}")
    logger.info("  跨議題經濟焦慮 (dim3) 滲透分析")
    logger.info("=" * 70)

    for tid in results:
        traj = results[tid]
        dim3_init = float(traj[0, :, 3].mean())
        dim3_final = float(traj[-1, :, 3].mean())
        logger.info(f"  {tid:12s}: init={dim3_init:+.3f}  final={dim3_final:+.3f}  Δ={dim3_final-dim3_init:+.4f}")

    # 哪個議題被犧牲？
    logger.info(f"\n{'='*70}")
    logger.info("  注意力競爭結果（哪個議題被犧牲？）")
    logger.info("=" * 70)

    topic_impact = {}
    for tid in results:
        traj = results[tid]
        B0 = scenarios[tid].belief_matrix()
        total_drift = float(np.mean(np.abs(traj[-1] - B0)))
        topic_impact[tid] = total_drift
        logger.info(f"  {tid:12s}: 總偏移量={total_drift:.4f}")

    sacrificed = min(topic_impact, key=topic_impact.get)
    logger.info(f"\n  → 被犧牲的議題: {sacrificed} (最小偏移量={topic_impact[sacrificed]:.4f})")
    logger.info(f"    解讀: {sacrificed} 在三議題並發時，信念更新最少")

    # λ_max 比較
    logger.info(f"\n{'='*70}")
    logger.info("  λ_max 跨議題比較")
    logger.info("=" * 70)
    for tid in topics:
        ts = topics[tid]
        eigenvalues = np.linalg.eigvals(ts.W)
        lmax = float(np.max(np.abs(eigenvalues)))
        logger.info(f"  {tid:12s}: λ_max={lmax:.4f}")


if __name__ == "__main__":
    main()
