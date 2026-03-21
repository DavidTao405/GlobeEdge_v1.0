"""Friedkin-Johnsen 信念更新引擎。

核心公式：b(t+1) = α * W @ b(t) + (1 - α) * b(0)

心理機制擴展（可選，預設關閉，向後相容）：
  use_forgetting: Ebbinghaus 遺忘曲線
  use_motivated_reasoning: Backfire Effect W 矩陣修正
  use_elm: ELM 雙路徑說服（透過 agent_involvements）
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
        *,
        use_forgetting: bool = False,
        use_elm: bool = False,
        use_dual_process: bool = False,
        agent_types: list[str] | None = None,
        agent_involvements: list[float] | None = None,
        message_emotionality: float = 0.5,
    ) -> BeliefState:
        """單步更新。

        Args:
            state: 當前信念狀態
            event: 外部事件衝擊向量 (n_agents, n_dims)，可選
            noise: 高斯噪聲標準差
            use_forgetting: 啟用 Ebbinghaus 遺忘曲線
            use_elm: 啟用 ELM 雙路徑更新
            use_dual_process: 啟用 System 1/2 雙歷程整合
            agent_types: Agent 類型清單（遺忘/雙歷程用）
            agent_involvements: Agent 議題投入度清單（ELM 用）
            message_emotionality: 訊息情緒性 0-1（ELM 用）
        """
        B_next = self.alpha * (state.W @ state.B) + (1 - self.alpha) * self.b0

        if event is not None:
            B_next = B_next + event

        if noise > 0:
            B_next = B_next + np.random.normal(0, noise, B_next.shape)

        B_next = np.clip(B_next, -1.0, 1.0)

        # Layer 1: Ebbinghaus 遺忘修正
        if use_forgetting and agent_types:
            from .psychology import apply_forgetting
            B_next = apply_forgetting(B_next, self.b0, agent_types)
            B_next = np.clip(B_next, -1.0, 1.0)

        # Layer 2: ELM 雙路徑修正
        if use_elm and agent_involvements:
            from .psychology import apply_elm_update
            B_next = apply_elm_update(
                B_next, self.b0, self.alpha,
                agent_involvements, message_emotionality,
            )
            B_next = np.clip(B_next, -1.0, 1.0)

        # Layer 4: System 1/2 雙歷程整合
        if use_dual_process and agent_types:
            from .psychology import dual_process_update
            social_influence = state.W @ state.B
            B_next = dual_process_update(
                B_next, self.b0, social_influence,
                agent_types, message_emotionality,
            )

        return BeliefState(
            t=state.t + 1,
            B=B_next,
            W=state.W,
            timestamp=datetime.now(),
        )

    def run(
        self,
        initial: BeliefState,
        horizon: int,
        events: Optional[dict[int, np.ndarray]] = None,
        noise: float = 0.0,
        *,
        use_forgetting: bool = False,
        use_elm: bool = False,
        use_dual_process: bool = False,
        agent_types: list[str] | None = None,
        agent_involvements: list[float] | None = None,
        message_emotionality: float | dict[int, float] = 0.5,
    ) -> list[BeliefState]:
        """多步推演，回傳完整軌跡。

        Args:
            initial: 初始狀態
            horizon: 推演步數
            events: {時間步: 衝擊向量} 字典
            noise: 高斯噪聲標準差
            use_forgetting: 啟用 Ebbinghaus 遺忘
            use_elm: 啟用 ELM 雙路徑
            use_dual_process: 啟用 System 1/2
            agent_types: Agent 類型清單
            agent_involvements: Agent 投入度清單
            message_emotionality: 訊息情緒性 (固定值 或 {時步: 值} 字典)
        """
        if events is None:
            events = {}
        trajectory = [initial]
        state = initial
        for t in range(1, horizon + 1):
            # 支持時變 emotionality（從爬蟲即時資料）
            emo = (message_emotionality.get(t, 0.5)
                   if isinstance(message_emotionality, dict)
                   else message_emotionality)
            state = self.step(
                state, event=events.get(t), noise=noise,
                use_forgetting=use_forgetting,
                use_elm=use_elm,
                use_dual_process=use_dual_process,
                agent_types=agent_types,
                agent_involvements=agent_involvements,
                message_emotionality=emo,
            )
            trajectory.append(state)
        return trajectory
