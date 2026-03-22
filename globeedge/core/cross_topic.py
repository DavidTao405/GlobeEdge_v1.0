"""跨議題耦合引擎 — Multi-topic Opinion Dynamics。

解決 GlobeEdge 最大架構盲點：
  現況：每個議題獨立仿真，Agent 不跨議題
  現實：同一個人同時被多個議題拉扯，且議題間互相影響

兩個核心機制：
  1. 共享維度滲透 (cross_topic_bleed)
     一個議題的信念漂移，透過共享維度影響另一個議題
     例：美伊戰爭 economic_anxiety ↑ → 能源議題 economic_anxiety 也 ↑

  2. 注意力資源競爭 (AttentionBudget)
     人的注意力有限，議題間競爭
     例：WBC 佔用注意力 → 罷免議題 effective_alpha 下降
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .psychology import apply_forgetting, apply_motivated_reasoning


# ── 共享維度定義 ──────────────────────────────────────────

# 跨議題共享的通用維度（index → 語義）
# 這些維度的信念變化會在議題之間滲透
SHARED_DIMS = {
    0: "gov_trust",           # 政府信任度（所有議題共享）
    3: "economic_anxiety",    # 經濟焦慮度（能源/貿易/美伊都影響）
    6: "group_cohesion",      # 群體凝聚度（政治/娛樂事件都影響）
    7: "external_threat",     # 外部威脅感知（地緣/軍事事件共享）
}

# 維度 4, 5 是議題專屬，不跨議題滲透
NON_SHARED_DIMS = {4, 5}


# ── 注意力預算 ────────────────────────────────────────────

@dataclass
class AttentionBudget:
    """注意力資源分配器。

    人的總注意力 = 1.0，議題依顯著性 (salience) 分配。
    高顯著性議題擠壓低顯著性議題的有效 alpha。
    """

    def allocate(
        self,
        salience: dict[str, float],
    ) -> dict[str, float]:
        """根據議題顯著性分配注意力權重。

        Args:
            salience: {topic_id: salience_score}

        Returns:
            {topic_id: attention_weight}  所有值加總 = 1.0
        """
        total = sum(salience.values())
        if total <= 0:
            n = len(salience)
            return {k: 1.0 / n for k in salience}
        return {
            topic: s / total
            for topic, s in salience.items()
        }

    def effective_alpha(
        self,
        base_alpha: float,
        attention_weight: float,
    ) -> float:
        """計算某議題在注意力競爭下的有效 alpha。

        attention_weight 越低 → alpha 越低 → 該議題的影響力更新越慢
        但不會降到 0（最低保留 10% base_alpha）
        """
        return max(base_alpha * attention_weight * len(SHARED_DIMS), base_alpha * 0.1)


# ── 跨議題事件 ────────────────────────────────────────────

@dataclass
class CrossTopicEvent:
    """跨議題事件（如 WBC、大規模天災）。

    同時影響多個議題的 impact + 注意力分配。
    """
    title: str
    day: int
    topic_impacts: dict[str, np.ndarray]   # {topic_id: impact_vector (n_dims,)}
    salience_override: dict[str, float]    # {topic_id: new_salience}
    meme_dynamics: dict = field(default_factory=dict)
    # meme_dynamics: {"reach_multiplier": 3.0, "decay_rate": 0.8, "backfire_resistant": True}


# ── 跨議題仿真引擎 ────────────────────────────────────────

@dataclass
class TopicState:
    """單一議題在某時步的狀態。"""
    topic_id: str
    B: np.ndarray            # (n_agents, n_dims)
    B0: np.ndarray           # 初始信念
    W: np.ndarray            # 影響力矩陣
    agent_types: list[str]
    alpha: float
    events: dict[int, np.ndarray]  # {timestep: impact_matrix}


class CrossTopicEngine:
    """跨議題耦合仿真引擎。

    用法:
        engine = CrossTopicEngine(
            topics={
                "energy": TopicState(...),
                "iran_war": TopicState(...),
                "recall": TopicState(...),
            },
            shared_agent_map={"科技業從業者": [0, 2, 1]},  # agent index in each topic
            bleed_rate=0.2,
        )
        results = engine.run(horizon=30, cross_events=[wbc_event])
    """

    def __init__(
        self,
        topics: dict[str, TopicState],
        shared_agent_map: dict[str, dict[str, int]],
        bleed_rate: float = 0.15,
        base_salience: dict[str, float] | None = None,
    ):
        """
        Args:
            topics: {topic_id: TopicState}
            shared_agent_map: {agent_name: {topic_id: agent_index}}
                跨議題的共享 Agent 及其在各議題中的 index
            bleed_rate: 共享維度的滲透率 (0-1)
            base_salience: 各議題的基礎顯著性
        """
        self.topics = topics
        self.shared_agent_map = shared_agent_map
        self.bleed_rate = bleed_rate
        self.attention = AttentionBudget()

        self.base_salience = base_salience or {
            tid: 1.0 / len(topics) for tid in topics
        }

        # 對每個議題預先套用動機性推理
        for ts in self.topics.values():
            ts.W = apply_motivated_reasoning(ts.W, ts.B0)

    def run(
        self,
        horizon: int = 30,
        cross_events: list[CrossTopicEvent] | None = None,
    ) -> dict[str, np.ndarray]:
        """跨議題耦合仿真。

        Returns:
            {topic_id: trajectory (horizon+1, n_agents, n_dims)}
        """
        cross_events = cross_events or []
        ce_by_day = {e.day: e for e in cross_events}

        trajectories: dict[str, list[np.ndarray]] = {
            tid: [] for tid in self.topics
        }

        current_salience = dict(self.base_salience)

        for t in range(horizon + 1):
            # 記錄當前狀態
            for tid, ts in self.topics.items():
                trajectories[tid].append(ts.B.copy())

            if t >= horizon:
                break

            # 處理跨議題事件（salience 覆蓋 + 多議題 impact）
            if t in ce_by_day:
                ce = ce_by_day[t]
                current_salience.update(ce.salience_override)

            # 計算注意力分配
            attention_weights = self.attention.allocate(current_salience)

            # 每個議題獨立 FJ step + 注意力調整
            for tid, ts in self.topics.items():
                eff_alpha = self.attention.effective_alpha(
                    ts.alpha, attention_weights.get(tid, 0.25)
                )

                # FJ 核心
                B_next = eff_alpha * ts.W @ ts.B + (1 - eff_alpha) * ts.B0

                # 議題內事件
                if t in ts.events:
                    B_next = B_next + ts.events[t]

                # 跨議題事件
                if t in ce_by_day:
                    ce = ce_by_day[t]
                    if tid in ce.topic_impacts:
                        impact = ce.topic_impacts[tid]
                        # 迷因動態：reach_multiplier
                        multiplier = ce.meme_dynamics.get("reach_multiplier", 1.0)
                        n_agents = B_next.shape[0]
                        for i in range(n_agents):
                            B_next[i] += impact * multiplier

                B_next = np.clip(B_next, -1.0, 1.0)

                # Ebbinghaus 遺忘
                B_next = apply_forgetting(B_next, ts.B0, ts.agent_types)
                B_next = np.clip(B_next, -1.0, 1.0)

                ts.B = B_next

            # 跨議題共享維度滲透
            self._cross_topic_bleed()

            # Salience 自然衰減（事件效果逐步消退）
            for tid in current_salience:
                base = self.base_salience.get(tid, 0.25)
                current_salience[tid] = base + 0.9 * (current_salience[tid] - base)

        return {
            tid: np.array(traj) for tid, traj in trajectories.items()
        }

    def _cross_topic_bleed(self):
        """共享維度滲透：共享 Agent 在不同議題間的信念互相影響。"""
        if not self.shared_agent_map:
            return

        for agent_name, topic_indices in self.shared_agent_map.items():
            topics_involved = [
                tid for tid in topic_indices if tid in self.topics
            ]
            if len(topics_involved) < 2:
                continue

            # 對每個共享維度，計算跨議題的加權平均
            for dim_idx in SHARED_DIMS:
                # 收集該 Agent 在所有議題的該維度信念
                beliefs = {}
                for tid in topics_involved:
                    agent_idx = topic_indices[tid]
                    ts = self.topics[tid]
                    if agent_idx < ts.B.shape[0]:
                        beliefs[tid] = ts.B[agent_idx, dim_idx]

                if len(beliefs) < 2:
                    continue

                # 計算平均信念
                mean_belief = sum(beliefs.values()) / len(beliefs)

                # 向平均信念滲透
                for tid in topics_involved:
                    agent_idx = topic_indices[tid]
                    ts = self.topics[tid]
                    if agent_idx < ts.B.shape[0]:
                        old = ts.B[agent_idx, dim_idx]
                        ts.B[agent_idx, dim_idx] = (
                            (1 - self.bleed_rate) * old +
                            self.bleed_rate * mean_belief
                        )


# ── 預定義跨議題事件 ──────────────────────────────────────

WBC_TEAMTAIWAN = CrossTopicEvent(
    title="WBC Team Taiwan + 島嶼天光哏化",
    day=15,
    topic_impacts={
        "recall": np.array([0.0, 0.0, 0.0, 0.0, -0.1, 0.0, 0.3, 0.0]),
        "energy": np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0]),
        "iran_war": np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, -0.1]),
    },
    salience_override={
        "recall": 0.15,    # 注意力被搶走
        "energy": 0.1,
        "iran_war": 0.15,
        "wbc": 0.6,        # WBC 佔據主要注意力
    },
    meme_dynamics={
        "reach_multiplier": 2.0,
        "decay_rate": 0.8,
        "backfire_resistant": True,
    },
)

OIL_PRICE_SPIKE = CrossTopicEvent(
    title="布蘭特原油突破 $126 歷史新高",
    day=18,
    topic_impacts={
        "iran_war": np.array([0.0, 0.0, -0.2, 0.4, -0.1, -0.3, -0.1, 0.2]),
        "energy": np.array([0.0, 0.0, -0.3, 0.5, 0.2, -0.2, -0.2, 0.1]),
        "recall": np.array([0.0, 0.0, 0.0, 0.2, 0.0, 0.0, -0.1, 0.0]),
    },
    salience_override={
        "iran_war": 0.4,
        "energy": 0.35,
        "recall": 0.15,
    },
)
