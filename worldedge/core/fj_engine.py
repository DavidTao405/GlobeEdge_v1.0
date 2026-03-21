"""Friedkin-Johnsen 信念更新引擎。

核心公式：b(t+1) = α * W @ b(t) + (1 - α) * b(0)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

from .belief_state import BeliefState


class FJEngine:
    """Friedkin-Johnsen 單步 / 多步推演。

    Args:
        alpha: 社會影響力權重，必須在 (0, 1) 之間。
               越大代表 agent 越受鄰居影響。
        b0: 初始信念矩陣 (n_agents, n_dims)，agent 的錨定信念。
    """

    def __init__(self, alpha: float, b0: np.ndarray) -> None:
        if not (0 < alpha < 1):
            raise ValueError(f"alpha 必須在 (0, 1) 之間，收到 {alpha}")
        self.alpha = alpha
        self.b0 = b0.copy()

    def step(
        self,
        state: BeliefState,
        event: Optional[np.ndarray] = None,
        noise: float = 0.0,
    ) -> BeliefState:
        """單步更新。

        Args:
            state: 當前信念狀態
            event: 外部事件衝擊向量 (n_agents, n_dims)，可選
            noise: 高斯噪聲標準差
        """
        B_next = self.alpha * (state.W @ state.B) + (1 - self.alpha) * self.b0

        if event is not None:
            B_next = B_next + event

        if noise > 0:
            B_next = B_next + np.random.normal(0, noise, B_next.shape)

        return BeliefState(
            t=state.t + 1,
            B=np.clip(B_next, -1.0, 1.0),
            W=state.W,
            timestamp=datetime.now(),
        )

    def run(
        self,
        initial: BeliefState,
        horizon: int,
        events: Optional[dict[int, np.ndarray]] = None,
        noise: float = 0.0,
    ) -> list[BeliefState]:
        """多步推演，回傳完整軌跡。

        Args:
            initial: 初始狀態
            horizon: 推演步數
            events: {時間步: 衝擊向量} 字典
            noise: 高斯噪聲標準差
        """
        if events is None:
            events = {}
        trajectory = [initial]
        state = initial
        for t in range(1, horizon + 1):
            state = self.step(state, event=events.get(t), noise=noise)
            trajectory.append(state)
        return trajectory
