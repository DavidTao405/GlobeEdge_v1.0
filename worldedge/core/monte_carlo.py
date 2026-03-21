"""MonteCarloRunner — 以 NumPy 批次執行 FJ Monte Carlo 模擬。"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .distribution import SimulationDistribution
from .fj_engine import FJEngine


class MonteCarloRunner:
    """CPU 版 Monte Carlo 模擬，跑 N 次 FJ 推演取分佈。

    Args:
        engine: FJEngine 實例
        n_runs: Monte Carlo 執行次數
        noise_level: 每步加的噪聲標準差
        seed: 隨機種子（可重現）
    """

    def __init__(
        self,
        engine: FJEngine,
        n_runs: int = 10_000,
        noise_level: float = 0.05,
        seed: Optional[int] = None,
    ) -> None:
        self.engine = engine
        self.n_runs = n_runs
        self.noise_level = noise_level
        self.rng = np.random.default_rng(seed)

    def run(
        self,
        B0: np.ndarray,
        W: np.ndarray,
        horizon: int,
        events: Optional[dict[int, np.ndarray]] = None,
    ) -> SimulationDistribution:
        """批次推演。

        以向量化方式同時跑 n_runs 次 FJ，
        每次給 W 和 B0 加入不同的微擾。

        Args:
            B0: 初始信念矩陣 (n_agents, n_dims)
            W: 影響力矩陣 (n_agents, n_agents)
            horizon: 推演步數
            events: {時間步: 衝擊向量} 字典

        Returns:
            SimulationDistribution 包含所有軌跡
        """
        if events is None:
            events = {}

        n_agents, n_dims = B0.shape
        alpha = self.engine.alpha
        b0 = self.engine.b0

        # (n_runs, n_agents, n_dims) — 每個 run 的初始信念加微擾
        B_all = np.broadcast_to(B0, (self.n_runs, n_agents, n_dims)).copy()
        B_all += self.rng.normal(0, self.noise_level * 0.5, B_all.shape)
        B_all = np.clip(B_all, -1.0, 1.0)

        # (n_runs, n_agents, n_agents) — 每個 run 的 W 加微擾
        W_all = np.broadcast_to(W, (self.n_runs, n_agents, n_agents)).copy()
        W_all += self.rng.normal(0, self.noise_level * 0.2, W_all.shape)
        W_all = np.clip(W_all, 0, 1)
        # 行和正規化：確保每行和 ≤ 1
        row_sums = W_all.sum(axis=2, keepdims=True)
        mask = row_sums > 1
        W_all = np.where(mask, W_all / row_sums, W_all)

        # b0 broadcast
        b0_broad = np.broadcast_to(b0, (self.n_runs, n_agents, n_dims))

        # 收集軌跡 (n_runs, horizon+1, n_agents, n_dims)
        all_B = np.empty((self.n_runs, horizon + 1, n_agents, n_dims))
        all_B[:, 0] = B_all

        for t in range(1, horizon + 1):
            # FJ 更新：B = α * W @ B + (1-α) * b0
            B_all = alpha * np.matmul(W_all, B_all) + (1 - alpha) * b0_broad

            # 外部事件注入
            event = events.get(t)
            if event is not None:
                B_all = B_all + event

            # 噪聲
            B_all = B_all + self.rng.normal(0, self.noise_level, B_all.shape)

            # clip
            B_all = np.clip(B_all, -1.0, 1.0)

            all_B[:, t] = B_all

        return SimulationDistribution(trajectories=all_B)
