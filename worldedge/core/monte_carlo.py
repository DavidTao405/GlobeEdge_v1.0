"""MonteCarloRunner — 以 NumPy 批次執行 FJ Monte Carlo 模擬。

MoE 分層採樣：不同 Agent 類型使用不同噪聲分佈。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import numpy as np

from .distribution import SimulationDistribution
from .fj_engine import FJEngine


# ── MoE 噪聲 Profile ────────────────────────────────────
class AgentNoiseProfile(Enum):
    """不同 Agent 類型的噪聲特性。

    社會科學依據：
      媒體機構行為穩定 → 小噪聲 (σ=0.02)
      制度性行為者   → 小噪聲 (σ=0.02)
      KOL 易突然轉向 → Laplace 偏態分布 (σ=0.04)，尾部更重
      論壇群體共識弱 → 中等噪聲 (σ=0.06)
      一般民眾態度易變 → 大噪聲 (σ=0.08)
    """

    MEDIA       = ("normal",  0.02)
    INSTITUTION = ("normal",  0.02)
    KOL         = ("laplace", 0.04)
    FORUM       = ("normal",  0.06)
    DEMOGRAPHIC = ("normal",  0.08)
    DEFAULT     = ("normal",  0.05)


_TYPE_MAP: dict[str, AgentNoiseProfile] = {
    "media":       AgentNoiseProfile.MEDIA,
    "institution": AgentNoiseProfile.INSTITUTION,
    "kol":         AgentNoiseProfile.KOL,
    "forum":       AgentNoiseProfile.FORUM,
    "demographic": AgentNoiseProfile.DEMOGRAPHIC,
}


def _sample_noise(
    profile: AgentNoiseProfile,
    shape: tuple,
    scale_multiplier: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """依據 profile 採樣噪聲。"""
    dist, base_scale = profile.value
    scale = base_scale * scale_multiplier
    if dist == "laplace":
        return rng.laplace(0, scale, shape)
    return rng.normal(0, scale, shape)


class MonteCarloRunner:
    """CPU 版 Monte Carlo 模擬，跑 N 次 FJ 推演取分佈。

    Args:
        engine: FJEngine 實例
        n_runs: Monte Carlo 執行次數
        noise_level: 每步加的噪聲標準差
        seed: 隨機種子（可重現）
        agent_types: 每個 Agent 的類型列表，用於 MoE 分層採樣。
            可為 "media", "kol", "demographic", "forum", "institution"。
            None 或長度不符 n_agents 時 fallback 為均勻噪聲。
    """

    def __init__(
        self,
        engine: FJEngine,
        n_runs: int = 10_000,
        noise_level: float = 0.05,
        seed: Optional[int] = None,
        agent_types: Optional[list[str]] = None,
    ) -> None:
        self.engine = engine
        self.n_runs = n_runs
        self.noise_level = noise_level
        self.rng = np.random.default_rng(seed)
        self.agent_types = agent_types or []

    def _build_noise_for_B(
        self, shape: tuple, noise_level: float
    ) -> np.ndarray:
        """MoE 分層採樣：每個 Agent 使用對應的噪聲 profile。

        Args:
            shape: (n_agents, n_dims)
            noise_level: 全域噪聲倍率
        """
        n_agents, n_dims = shape

        if not self.agent_types or len(self.agent_types) != n_agents:
            # fallback：沒有類型資訊時，用原本的均勻噪聲
            return self.rng.normal(0, noise_level * 0.5, shape)

        noise = np.zeros(shape)
        for i, agent_type in enumerate(self.agent_types):
            profile = _TYPE_MAP.get(agent_type, AgentNoiseProfile.DEFAULT)
            noise[i] = _sample_noise(profile, (n_dims,), noise_level, self.rng)
        return noise

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

        # (n_runs, n_agents, n_dims) — MoE 分層初始微擾
        B_all = np.broadcast_to(B0, (self.n_runs, n_agents, n_dims)).copy()
        for r in range(self.n_runs):
            B_all[r] += self._build_noise_for_B(
                (n_agents, n_dims), self.noise_level
            )
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

            # 噪聲（MoE 分層）
            for r in range(self.n_runs):
                B_all[r] += self._build_noise_for_B(
                    (n_agents, n_dims), self.noise_level
                )

            # clip
            B_all = np.clip(B_all, -1.0, 1.0)

            all_B[:, t] = B_all

        return SimulationDistribution(trajectories=all_B)

    def run_gpu(
        self,
        B0: np.ndarray,
        W: np.ndarray,
        horizon: int,
        events: Optional[dict[int, np.ndarray]] = None,
    ) -> SimulationDistribution:
        """GPU 批次推演（torch.bmm）。

        完全在 GPU 上執行 FJ 更新，比 CPU 快 10-50x。
        RTX 4070 SUPER: 10,000 runs × 30 steps × 50 agents ≈ 0.5s

        自動 fallback：如果 CUDA 不可用，退回 CPU run()。
        """
        try:
            import torch
        except ImportError:
            return self.run(B0, W, horizon, events)

        if not torch.cuda.is_available():
            return self.run(B0, W, horizon, events)

        if events is None:
            events = {}

        device = torch.device("cuda")
        n_agents, n_dims = B0.shape
        alpha = self.engine.alpha

        # 初始信念 → GPU tensor (n_runs, n_agents, n_dims)
        B_t = torch.tensor(B0, dtype=torch.float32, device=device)
        B_t = B_t.unsqueeze(0).expand(self.n_runs, -1, -1).clone()
        B_t += torch.randn_like(B_t) * self.noise_level * 0.5
        B_t = torch.clamp(B_t, -1.0, 1.0)

        # W → GPU tensor (n_runs, n_agents, n_agents)
        W_t = torch.tensor(W, dtype=torch.float32, device=device)
        W_t = W_t.unsqueeze(0).expand(self.n_runs, -1, -1).clone()
        W_t += torch.randn_like(W_t) * self.noise_level * 0.2
        W_t = torch.clamp(W_t, 0, 1)
        # 行和正規化
        row_sums = W_t.sum(dim=2, keepdim=True)
        W_t = torch.where(row_sums > 1, W_t / row_sums, W_t)

        # b0 broadcast
        b0_t = torch.tensor(
            self.engine.b0, dtype=torch.float32, device=device
        ).unsqueeze(0).expand(self.n_runs, -1, -1)

        # 收集軌跡
        all_B_list = [B_t.cpu().numpy()]

        for t in range(1, horizon + 1):
            # FJ 更新：B = α * W @ B + (1-α) * b0（bmm 批次矩陣乘法）
            B_t = alpha * torch.bmm(W_t, B_t) + (1 - alpha) * b0_t

            # 外部事件注入
            event = events.get(t)
            if event is not None:
                B_t = B_t + torch.tensor(
                    event, dtype=torch.float32, device=device
                )

            # 噪聲
            B_t = B_t + torch.randn_like(B_t) * self.noise_level

            # clip
            B_t = torch.clamp(B_t, -1.0, 1.0)

            all_B_list.append(B_t.cpu().numpy())

        # (horizon+1, n_runs, n_agents, n_dims) → (n_runs, horizon+1, n_agents, n_dims)
        all_B = np.array(all_B_list).transpose(1, 0, 2, 3)

        return SimulationDistribution(trajectories=all_B)
