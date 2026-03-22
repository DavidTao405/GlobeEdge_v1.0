"""心理機制擴展 — 超越行為主義的 FJ 模型。

四層可選擇性啟用的心理機制，全部預設關閉，向後相容。

Layer 1: Ebbinghaus 遺忘曲線
    R = e^(-steps/S)，每個 Agent 類型有不同的記憶穩定性 S
    PTT 論壇極短記憶 (S=2)，機構最穩定 (S=25)

Layer 2: ELM 雙路徑說服
    issue_involvement 高 → 中央路徑（深處理，持久）
    issue_involvement 低 → 周邊路徑（淺處理，快速衰退）

Layer 3: 動機性推理 (Backfire Effect)
    固有立場距離 > 閾值 → 社會影響力衰減甚至引發抵抗
    解釋：台灣深藍/深綠的結構性極化

Layer 4: System 1/2（長期，本版暫不實作完整邏輯）

參考：WORLDEDGE_REPORT.md 第 12 節
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# ── Layer 1: Ebbinghaus 遺忘曲線 ─────────────────────────

MEMORY_STABILITY: dict[str, float] = {
    "media":       20.0,   # 媒體立場穩定，慢慢忘
    "institution": 25.0,   # 機構最穩定
    "kol":         15.0,   # KOL 有時突然轉向
    "demographic":  5.0,   # 一般民眾快速遺忘
    "forum":        2.0,   # PTT 極短記憶（隔天就忘）
}


def compute_retention(agent_type: str, steps: int = 1) -> float:
    """Ebbinghaus 遺忘曲線：R = e^(-steps/S)。"""
    S = MEMORY_STABILITY.get(agent_type, 10.0)
    return float(np.exp(-steps / S))


def apply_forgetting(
    b_next: np.ndarray,
    b0: np.ndarray,
    agent_types: list[str],
) -> np.ndarray:
    """信念更新後施加遺忘衰退。

    每個 Agent 的信念從 b_next 向 b(0) 衰退，
    衰退速度由 Agent 類型的記憶穩定性決定。
    """
    result = b_next.copy()
    for i, agent_type in enumerate(agent_types):
        if i >= result.shape[0]:
            break
        retention = compute_retention(agent_type)
        result[i] = b0[i] + retention * (b_next[i] - b0[i])
    return result


# ── Layer 2: ELM 雙路徑說服 ──────────────────────────────

def compute_alpha_elm(
    base_alpha: float,
    agent_involvement: float,
    message_emotionality: float = 0.5,
) -> tuple[float, float]:
    """ELM 雙路徑：根據處理深度決定有效 alpha 和衰退率。

    Args:
        base_alpha: 專案的基礎 alpha
        agent_involvement: Agent 對議題的投入度 (0-1)
        message_emotionality: 訊息的情緒性 (0=理性, 1=純情緒)

    Returns:
        (alpha_effective, decay_rate)
        中央路徑: alpha↑ decay↓ (深處理，持久)
        周邊路徑: alpha↓ decay↑ (淺處理，快速衰退)
    """
    elaboration = agent_involvement * (1 - message_emotionality)

    if elaboration > 0.5:
        # 中央路徑：深處理
        alpha_eff = min(base_alpha * 1.5, 0.9)
        decay = 0.02
    elif elaboration > 0.2:
        # 混合路徑
        alpha_eff = base_alpha
        decay = 0.15
    else:
        # 周邊路徑：淺處理
        alpha_eff = base_alpha * 0.6
        decay = 0.4

    return alpha_eff, decay


def apply_elm_update(
    b_next: np.ndarray,
    b0: np.ndarray,
    base_alpha: float,
    agent_involvements: list[float],
    message_emotionality: float = 0.5,
) -> np.ndarray:
    """ELM 雙路徑更新：每個 Agent 根據 involvement 走不同路徑。"""
    result = b_next.copy()
    for i, involvement in enumerate(agent_involvements):
        if i >= result.shape[0]:
            break
        _, decay = compute_alpha_elm(base_alpha, involvement, message_emotionality)
        # 衰退修正：低 involvement → 更快回到 b(0)
        result[i] = b0[i] + (1 - decay) * (b_next[i] - b0[i])
    return result


# ── Layer 3: 動機性推理 (Backfire Effect) ─────────────────

def apply_motivated_reasoning(
    W: np.ndarray,
    B0: np.ndarray,
    identity_threshold: float = 0.5,
    k: float = 3.0,
) -> np.ndarray:
    """動機性推理修正 W 矩陣。

    當兩個 Agent 的固有立場距離超過閾值：
    - 社會影響力不是增強，而是引發抵抗
    - 距離越遠 → 阻力越大（Backfire Effect）

    這解釋了 FJ 的最大盲點：
    反核 KOL → 擁核 KOL：FJ 預測互相影響趨向中間，
    但動機性推理預測距離太遠引發抵抗，實際上互相強化對立。
    """
    n = W.shape[0]
    W_motivated = W.copy()

    for i in range(n):
        for j in range(n):
            if W[i, j] == 0:
                continue
            # i 被 j 影響：計算兩者固有立場距離
            distance = float(np.linalg.norm(B0[i] - B0[j]))

            if distance > identity_threshold:
                # Backfire Effect：距離越遠，阻力越大
                resistance = 1 - np.exp(-k * (distance - identity_threshold))
                W_motivated[i, j] *= (1 - resistance)

    return W_motivated


# ── 心理機制設定 ──────────────────────────────────────────

# ── Layer 4: System 1/2 雙歷程整合 ──────────────────────

# System 1/2 參數
ALPHA_S1 = 0.15   # System 1: 低 alpha（淺處理）
ALPHA_S2 = 0.45   # System 2: 高 alpha（深處理）
DECAY_S1 = 0.35   # System 1: 快速衰退
DECAY_S2 = 0.05   # System 2: 緩慢衰退


def dual_process_update(
    b_next: np.ndarray,
    b0: np.ndarray,
    social_influence: np.ndarray,
    agent_types: list[str],
    message_emotionality: float,
) -> np.ndarray:
    """System 1/2 整合：對已計算的 b_next 施加雙歷程衰退修正。

    不替換 b_next，而是修正「b_next 偏離 b0 的部分」的保留率。

    System 1（快、自動、情緒）→ 保留率低，快速回到 b0
    System 2（慢、理性、審慎）→ 保留率高，持久偏離

    最終保留率 = w_s1 × R_s1 + w_s2 × R_s2
    """
    w_s1 = message_emotionality          # 情緒訊息走 System 1
    w_s2 = 1.0 - message_emotionality    # 理性訊息走 System 2

    result = b_next.copy()
    for i, atype in enumerate(agent_types):
        if i >= result.shape[0]:
            break
        base_retention = compute_retention(atype)

        # System 1 保留率：低（快速衰退）
        r_s1 = base_retention * (1 - DECAY_S1)
        # System 2 保留率：高（持久記憶）
        r_s2 = base_retention * (1 - DECAY_S2)

        # 加權保留率
        retention = w_s1 * r_s1 + w_s2 * r_s2

        # 對偏離 b0 的部分施加衰退
        result[i] = b0[i] + retention * (b_next[i] - b0[i])

    return np.clip(result, -1.0, 1.0)


# ── Layer 5: EventAccumulator 持續事件模式 ─────────────────

@dataclass
class CrisisEvent:
    """危機序列中的單一事件。"""
    day: int
    impact_vector: np.ndarray  # (n_dims,)
    title: str = ""


class EventAccumulator:
    """持續危機下，相關事件的衝擊累積而非衰退。

    事件類型與信念演化模式：
      一次性衝擊（地震、選舉）  → 回歸型 → FJ + Ebbinghaus
      持續危機（戰爭、長期政策）→ 累積型 → EventAccumulator
      週期性事件（定期法說）    → 震盪型 → 待研究

    累積條件：
      1. 與前一事件同屬一個「危機序列」
      2. 時間間隔 < max_gap 天
      3. impact_vector 方向一致（cosine > alignment_threshold）
    """

    def __init__(
        self,
        max_gap: int = 7,
        alignment_threshold: float = 0.3,
        accumulation_decay: float = 0.95,
    ):
        self.max_gap = max_gap
        self.alignment_threshold = alignment_threshold
        self.accumulation_decay = accumulation_decay
        self._history: list[CrisisEvent] = []
        self._accumulated: np.ndarray | None = None

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        """兩個向量的 cosine 相似度。"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def should_accumulate(self, day: int, impact: np.ndarray) -> bool:
        """判斷新事件是否應累積。"""
        if not self._history:
            return False
        last = self._history[-1]
        gap = day - last.day
        alignment = self._cosine_sim(last.impact_vector, impact)
        return gap <= self.max_gap and alignment > self.alignment_threshold

    def process_event(
        self, day: int, impact: np.ndarray, title: str = "",
    ) -> np.ndarray:
        """處理一個事件，回傳有效 impact（可能是累積的）。

        Returns:
            effective_impact: 累積模式下 = 前次累積 × decay + 新 impact
                              非累積模式下 = 原始 impact
        """
        event = CrisisEvent(day=day, impact_vector=impact.copy(), title=title)

        if self.should_accumulate(day, impact):
            # 累積：前次累積值 × 衰減 + 新衝擊
            if self._accumulated is not None:
                self._accumulated = (
                    self._accumulated * self.accumulation_decay + impact
                )
            else:
                self._accumulated = impact.copy()
            self._history.append(event)
            return self._accumulated.copy()
        else:
            # 新危機序列：重置
            self._history = [event]
            self._accumulated = impact.copy()
            return impact.copy()

    def get_suppression_mask(self) -> np.ndarray | None:
        """回傳累積中的維度遮罩。

        累積中的維度不應被 Ebbinghaus 衰退。
        Returns:
            (n_dims,) bool array，True = 該維度正在累積，抑制遺忘
        """
        if self._accumulated is None:
            return None
        # 有顯著累積值的維度
        return np.abs(self._accumulated) > 0.05

    @property
    def is_in_crisis(self) -> bool:
        """是否正處於持續危機中。"""
        return len(self._history) >= 2

    @property
    def crisis_length(self) -> int:
        """目前危機序列的長度。"""
        return len(self._history)

    def reset(self):
        """重置累積器。"""
        self._history.clear()
        self._accumulated = None


def apply_forgetting_with_accumulator(
    b_next: np.ndarray,
    b0: np.ndarray,
    agent_types: list[str],
    accumulator: EventAccumulator | None = None,
) -> np.ndarray:
    """Ebbinghaus 遺忘 + 累積事件抑制。

    累積中的維度不被 Ebbinghaus 拉回 b(0)。
    """
    result = b_next.copy()
    suppression = accumulator.get_suppression_mask() if accumulator else None

    for i, agent_type in enumerate(agent_types):
        if i >= result.shape[0]:
            break
        retention = compute_retention(agent_type)

        for d in range(result.shape[1]):
            if suppression is not None and d < len(suppression) and suppression[d]:
                # 此維度正在累積 → 不衰退
                continue
            result[i, d] = b0[i, d] + retention * (b_next[i, d] - b0[i, d])

    return result


@dataclass
class PsychologyConfig:
    """心理機制開關。全部預設關閉，向後相容。"""
    use_forgetting: bool = False
    use_elm: bool = False
    use_motivated_reasoning: bool = False
    use_dual_process: bool = False
    use_accumulator: bool = False   # Layer 5: 持續事件累積
    use_crisis_dynamics: bool = False  # Layer 6: CrisisAwareFJ (dynamic alpha + b0 drift)

    # Ebbinghaus 參數
    memory_stability_override: dict[str, float] = field(default_factory=dict)

    # ELM 參數
    message_emotionality: float = 0.5

    # 動機性推理參數
    identity_threshold: float = 0.5
    backfire_k: float = 3.0

    # EventAccumulator 參數
    accumulator_max_gap: int = 7
    accumulator_alignment: float = 0.3

    def any_enabled(self) -> bool:
        return (self.use_forgetting or self.use_elm
                or self.use_motivated_reasoning or self.use_dual_process
                or self.use_accumulator or self.use_crisis_dynamics)

    def to_dict(self) -> dict:
        return {
            "use_forgetting": self.use_forgetting,
            "use_elm": self.use_elm,
            "use_motivated_reasoning": self.use_motivated_reasoning,
            "use_dual_process": self.use_dual_process,
            "use_accumulator": self.use_accumulator,
            "use_crisis_dynamics": self.use_crisis_dynamics,
            "identity_threshold": self.identity_threshold,
            "backfire_k": self.backfire_k,
            "message_emotionality": self.message_emotionality,
        }
