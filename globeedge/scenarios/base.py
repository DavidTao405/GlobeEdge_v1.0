"""議題情境基礎類 — 所有 scenario 的共用結構。

每個 scenario 定義：
  1. 8 個維度的議題特定語義
  2. Agent 清單（核心 + 邊緣）
  3. ExternalEvent 清單
  4. 預設仿真參數
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# Phase 7 校準結果：台灣社會最佳參數
PROJECT_DEFAULTS = {
    "alpha": 0.3,
    "mc_runs": 10_000,
    "sim_horizon": 30,
    "noise_level": 0.05,
}


@dataclass
class DimensionDef:
    """單一維度的語義定義。"""
    index: int
    name: str               # 通用名（對應 issue_dimensions）
    label: str               # 議題特定標籤
    description: str = ""


@dataclass
class AgentDef:
    """Agent 定義。"""
    name: str
    type: str                # media | forum | kol | demographic | institution
    domain: str              # news | social | financial | government
    belief_init: list[float] # len=8
    description: str = ""
    is_core: bool = True     # True=核心節點, False=邊緣群組


@dataclass
class EventDef:
    """ExternalEvent 定義。"""
    title: str
    impact_vector: list[float]  # len=8
    domain: str = "domestic"
    description: str = ""
    metadata: dict = field(default_factory=dict)  # PTT 驗證資料等額外資訊


@dataclass
class Scenario:
    """完整議題情境。"""
    id: str
    name: str
    description: str
    dimensions: list[DimensionDef]
    agents: list[AgentDef]
    events: list[EventDef]
    alpha: float = PROJECT_DEFAULTS["alpha"]
    mc_runs: int = PROJECT_DEFAULTS["mc_runs"]
    sim_horizon: int = PROJECT_DEFAULTS["sim_horizon"]
    noise_level: float = PROJECT_DEFAULTS["noise_level"]
    expected_findings: list[str] = field(default_factory=list)

    @property
    def n_agents(self) -> int:
        return len(self.agents)

    @property
    def n_dims(self) -> int:
        return len(self.dimensions)

    @property
    def core_agents(self) -> list[AgentDef]:
        return [a for a in self.agents if a.is_core]

    @property
    def edge_agents(self) -> list[AgentDef]:
        return [a for a in self.agents if not a.is_core]

    def belief_matrix(self) -> np.ndarray:
        """建立 B0 矩陣 (n_agents, n_dims)。"""
        return np.array([a.belief_init for a in self.agents])

    def agent_types(self) -> list[str]:
        """回傳 agent type 清單（供 MoE 噪聲用）。"""
        return [a.type for a in self.agents]

    def default_W(self) -> np.ndarray:
        """建立預設 W 矩陣（均勻弱連結，同類型稍強）。"""
        n = self.n_agents
        W = np.full((n, n), 0.05)

        for i in range(n):
            for j in range(n):
                if i == j:
                    W[i, j] = 0.0
                    continue
                ai, aj = self.agents[i], self.agents[j]
                # 同類型 Agent 影響力較強
                if ai.type == aj.type:
                    W[i, j] = 0.12
                # media → demographic 影響力強
                if aj.type == "media" and ai.type == "demographic":
                    W[i, j] = 0.18
                # kol → forum 影響力強
                if aj.type == "kol" and ai.type == "forum":
                    W[i, j] = 0.15
                # institution → media 影響力強
                if aj.type == "institution" and ai.type == "media":
                    W[i, j] = 0.14

        # 行和正規化（確保 ≤ 1）
        row_sums = W.sum(axis=1, keepdims=True)
        mask = row_sums > 1
        W = np.where(mask, W / row_sums, W)
        return W

    def summary(self) -> str:
        """情境摘要。"""
        lines = [
            f"{'='*60}",
            f"  {self.name}  ({self.id})",
            f"{'='*60}",
            f"  Agents: {self.n_agents} ({len(self.core_agents)} core + {len(self.edge_agents)} edge)",
            f"  Events: {len(self.events)}",
            f"  Alpha:  {self.alpha}  MC runs: {self.mc_runs}  Horizon: {self.sim_horizon}",
            f"",
            f"  Dimensions:",
        ]
        for d in self.dimensions:
            lines.append(f"    [{d.index}] {d.label:20s}  ({d.name})")
        lines.append(f"\n  Core Agents:")
        for a in self.core_agents:
            lines.append(f"    {a.name:20s}  type={a.type:12s}  b0={a.belief_init}")
        lines.append(f"\n  Edge Agents:")
        for a in self.edge_agents:
            lines.append(f"    {a.name:20s}  type={a.type:12s}  b0={a.belief_init}")
        lines.append(f"\n  Events:")
        for e in self.events:
            lines.append(f"    {e.title}")
        return "\n".join(lines)
