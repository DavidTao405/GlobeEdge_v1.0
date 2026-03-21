"""BeliefState — 不可變信念快照。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass(frozen=True)
class BeliefState:
    """一個時間步的完整系統狀態。

    Attributes:
        t: 時間步索引
        B: 信念矩陣 (n_agents, n_dims)，值域 [-1, 1]
        W: 影響力矩陣 (n_agents, n_agents)，行和 ≤ 1
        timestamp: 此狀態產生的時間
    """

    t: int
    B: np.ndarray
    W: np.ndarray
    timestamp: datetime

    def lambda_max(self) -> float:
        """W 矩陣最大特徵值（實部）。趨近 1 代表系統接近臨界。"""
        return float(np.max(np.linalg.eigvals(self.W).real))

    def variance(self) -> float:
        """信念矩陣整體變異數。暴增代表信念開始震盪。"""
        return float(self.B.var())

    @property
    def n_agents(self) -> int:
        return self.B.shape[0]

    @property
    def n_dims(self) -> int:
        return self.B.shape[1]
