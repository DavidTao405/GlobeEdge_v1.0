"""CrisisAwareFJEngine — 持續危機下的 FJ 模型擴展。

解決 FJ 核心公式 b(t+1) = α×W@b(t) + (1-α)×b(0) 的結構性限制：
  (1-α)×b(0) 每步都把信念拉回固定錨點。
  一次性衝擊（地震）→ 合理（事件後回歸）
  持續危機（戰爭）→ 導致 0% 方向準確率

兩個結構性修正：
  1. Dynamic alpha：危機中 α 升高（錨定感減弱）
  2. Dynamic b(0)：固有信念在持續衝擊下緩慢漂移

向後相容：無事件時 crisis_intensity=0，退化為原始 FJ。
不修改 BeliefState（frozen=True）或 FJEngine。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from .belief_state import BeliefState


# ── 安全邊界 ──────────────────────────────────────────────
# 崩潰臨界 spread=0.1（test_spread_floor.py 驗證）
# MIN_SPREAD = 0.12 = 臨界 + 0.02 buffer
MIN_SPREAD = 0.12


def _compute_spread(B: np.ndarray) -> float:
    """所有 Agent 信念向量的標準差均值。"""
    return float(np.std(B, axis=0).mean())


# ── 設定 ──────────────────────────────────────────────────

@dataclass
class CrisisConfig:
    """持續危機動態參數。"""
    alpha_base: float = 0.3       # 平時 alpha
    alpha_crisis: float = 0.6     # 危機高峰 alpha（上限）
    crisis_decay: float = 0.05    # 每步危機強度自然衰退
    crisis_growth: float = 0.15   # 每個事件的危機強度增長
    b0_drift_rate: float = 0.15   # b(0) 漂移率（每步）
    crisis_threshold: float = 0.3 # 高於此強度才觸發 b(0) 漂移


@dataclass(frozen=True)
class CrisisStepResult:
    """單步結果：BeliefState + 危機元資料。"""
    belief_state: BeliefState
    crisis_intensity: float
    effective_alpha: float
    b0_current: np.ndarray


# ── Pure Functions（供向量化路徑使用）─────────────────────

def update_crisis_intensity(
    current: float,
    has_event: bool,
    event_magnitude: float = 0.0,
    config: CrisisConfig | None = None,
) -> float:
    """更新危機強度。有事件累積，無事件衰退。"""
    if config is None:
        config = CrisisConfig()
    if has_event:
        growth = config.crisis_growth * max(event_magnitude, 0.5)
        return min(1.0, current + growth)
    else:
        return max(0.0, current - config.crisis_decay)


def compute_dynamic_alpha(
    crisis_intensity: float,
    config: CrisisConfig | None = None,
) -> float:
    """線性插值：alpha_base → alpha_crisis。"""
    if config is None:
        config = CrisisConfig()
    return config.alpha_base + \
        (config.alpha_crisis - config.alpha_base) * crisis_intensity


def drift_b0(
    b0_current: np.ndarray,
    B_current: np.ndarray,
    crisis_intensity: float,
    config: CrisisConfig | None = None,
    event_impact: np.ndarray | None = None,
) -> np.ndarray:
    """b(0) 緩慢漂移：危機中固有信念被持續衝擊重寫。

    drift_rate=0.15 → 完全重寫需約 7 步（約一週的持續危機）
    只在 crisis_intensity > threshold 時觸發。

    漂移方向：
      有事件時 → 向事件衝擊方向漂移（累積事件效果到 b0）
      無事件時 → 向當前信念均值漂移（社會學習效果）
    """
    if config is None:
        config = CrisisConfig()
    if crisis_intensity <= config.crisis_threshold:
        return b0_current

    drift = config.b0_drift_rate * crisis_intensity
    b0_new = b0_current.copy()

    if event_impact is not None:
        # 有事件：b0 向事件衝擊方向漂移
        # 事件 impact 直接加到 b0（按 drift 比例）
        if event_impact.ndim == 2 and b0_new.ndim == 2:
            b0_new = b0_new + drift * event_impact
        elif event_impact.ndim == 1 and b0_new.ndim == 2:
            for i in range(b0_new.shape[0]):
                b0_new[i] = b0_new[i] + drift * event_impact
        else:
            b0_new = b0_new + drift * event_impact
    else:
        # 無事件：向當前信念均值漂移
        target = B_current.mean(axis=0) if B_current.ndim == 2 else B_current
        if b0_new.ndim == 2:
            for i in range(b0_new.shape[0]):
                b0_new[i] = b0_new[i] + drift * (target - b0_new[i])
        else:
            b0_new = b0_new + drift * (target - b0_new)

    return np.clip(b0_new, -1.0, 1.0)


def crisis_fj_step(
    B: np.ndarray,
    W: np.ndarray,
    b0: np.ndarray,
    alpha: float,
    event: np.ndarray | None = None,
    noise: float = 0.0,
) -> np.ndarray:
    """單步 FJ（用動態 alpha 和動態 b0）。Pure function。"""
    B_next = alpha * (W @ B) + (1 - alpha) * b0
    if event is not None:
        B_next = B_next + event
    if noise > 0:
        B_next = B_next + np.random.normal(0, noise, B_next.shape)
    return np.clip(B_next, -1.0, 1.0)


# ── CrisisAwareFJEngine ──────────────────────────────────

class CrisisAwareFJEngine:
    """FJ 模型的持續危機擴展版。

    核心修正：
      1. b(0) 在累積衝擊下緩慢漂移（不再固定）
      2. alpha 在危機中升高（錨定減弱，更依賴社會影響）

    向後相容：
      無事件 → crisis_intensity=0 → alpha 不變 → b0 不漂移 → 退化為原始 FJ
    """

    def __init__(
        self,
        alpha: float,
        b0: np.ndarray,
        config: CrisisConfig | None = None,
    ):
        self.config = config or CrisisConfig(alpha_base=alpha)
        self.b0_original = b0.copy()
        self.b0_current = b0.copy()
        self.crisis_intensity = 0.0

    def step(
        self,
        state: BeliefState,
        event: Optional[np.ndarray] = None,
        noise: float = 0.0,
    ) -> CrisisStepResult:
        """單步更新：動態 alpha + 動態 b(0) + FJ。"""
        # 計算事件強度
        has_event = event is not None
        event_magnitude = float(np.linalg.norm(event)) if has_event else 0.0

        # 更新危機強度
        self.crisis_intensity = update_crisis_intensity(
            self.crisis_intensity, has_event, event_magnitude, self.config,
        )

        # 動態 alpha
        eff_alpha = compute_dynamic_alpha(self.crisis_intensity, self.config)

        # 動態 b(0) 漂移（有事件時向衝擊方向漂移）
        self.b0_current = drift_b0(
            self.b0_current, state.B, self.crisis_intensity, self.config,
            event_impact=event,
        )

        # 修正版 FJ：用動態 alpha 和動態 b0
        B_next = crisis_fj_step(
            state.B, state.W, self.b0_current, eff_alpha, event, noise,
        )

        # Spread floor 保護：防止高 alpha 導致信念崩潰
        # 二分搜尋找到能維持 MIN_SPREAD 的最大 alpha
        spread = _compute_spread(B_next)
        if spread < MIN_SPREAD:
            alpha_lo, alpha_hi = 0.0, eff_alpha
            for _ in range(8):  # 8 次二分 → 精度 < 0.5%
                alpha_mid = (alpha_lo + alpha_hi) / 2
                B_try = crisis_fj_step(
                    state.B, state.W, self.b0_current, alpha_mid, event, noise,
                )
                if _compute_spread(B_try) >= MIN_SPREAD:
                    alpha_lo = alpha_mid
                else:
                    alpha_hi = alpha_mid
            eff_alpha = alpha_lo
            B_next = crisis_fj_step(
                state.B, state.W, self.b0_current, eff_alpha, event, noise,
            )

        bs = BeliefState(
            t=state.t + 1,
            B=B_next,
            W=state.W,
            timestamp=datetime.now(timezone.utc),
        )
        return CrisisStepResult(
            belief_state=bs,
            crisis_intensity=self.crisis_intensity,
            effective_alpha=eff_alpha,
            b0_current=self.b0_current.copy(),
        )

    def run(
        self,
        initial: BeliefState,
        horizon: int,
        events: dict[int, np.ndarray] | None = None,
        noise: float = 0.0,
    ) -> list[CrisisStepResult]:
        """多步推演。"""
        events = events or {}
        results = [
            CrisisStepResult(
                belief_state=initial,
                crisis_intensity=0.0,
                effective_alpha=self.config.alpha_base,
                b0_current=self.b0_current.copy(),
            )
        ]
        state = initial
        for t in range(horizon):
            event = events.get(t)
            result = self.step(state, event, noise)
            results.append(result)
            state = result.belief_state
        return results

    def reset(self):
        """重置危機狀態。"""
        self.crisis_intensity = 0.0
        self.b0_current = self.b0_original.copy()
