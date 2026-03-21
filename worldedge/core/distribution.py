"""SimulationDistribution — Monte Carlo 結果的統計封裝。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SimulationDistribution:
    """Monte Carlo 多次模擬的結果分佈。

    Attributes:
        trajectories: (n_runs, horizon+1, n_agents, n_dims)
    """

    trajectories: np.ndarray

    @property
    def n_runs(self) -> int:
        return self.trajectories.shape[0]

    @property
    def horizon(self) -> int:
        return self.trajectories.shape[1] - 1

    @property
    def n_agents(self) -> int:
        return self.trajectories.shape[2]

    @property
    def n_dims(self) -> int:
        return self.trajectories.shape[3]

    def mean(self) -> np.ndarray:
        """各時間步的平均信念 (horizon+1, n_agents, n_dims)。"""
        return self.trajectories.mean(axis=0)

    def std(self) -> np.ndarray:
        """各時間步的標準差 (horizon+1, n_agents, n_dims)。"""
        return self.trajectories.std(axis=0)

    def percentile(self, q: float) -> np.ndarray:
        """各時間步的百分位數 (horizon+1, n_agents, n_dims)。"""
        return np.percentile(self.trajectories, q, axis=0)

    def ci(self, level: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
        """信心區間。

        Args:
            level: 信心水準（預設 95%）

        Returns:
            (lower, upper) 各為 (horizon+1, n_agents, n_dims)
        """
        tail = (1 - level) / 2 * 100
        lower = np.percentile(self.trajectories, tail, axis=0)
        upper = np.percentile(self.trajectories, 100 - tail, axis=0)
        return lower, upper

    def variance_over_time(self) -> np.ndarray:
        """跨 run 的信念變異數隨時間變化 (horizon+1,)。

        EWS 指標：此值暴增代表信念開始震盪。
        """
        return self.trajectories.var(axis=(0, 2, 3))

    def lambda_max_series(self, W: np.ndarray) -> float:
        """W 矩陣最大特徵值（靜態指標，不隨 run 變化）。"""
        return float(np.max(np.linalg.eigvals(W).real))
