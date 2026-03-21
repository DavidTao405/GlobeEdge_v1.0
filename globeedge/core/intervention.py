"""What If 反事實分析 — 介入模型。

核心概念：
  一個 What If = 基準仿真 + 一個或多個 Intervention
  Intervention 套用到 BeliefState / W 矩陣 / Events，產生修改後的狀態
  所有操作 immutable（不修改原始資料）

介入類型：
  remove_agent   — W 矩陣對應行列清零（Agent 失去影響力）
  modify_belief  — 修改特定 Agent 的 b(0) 特定維度
  remove_event   — 從 events dict 移除特定事件
  modify_edge    — 修改 W[source][target] 的權重
  shift_event    — 事件時間點前移/後移
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Intervention:
    """單一介入操作。"""
    type: str           # remove_agent | modify_belief | remove_event | modify_edge | shift_event
    target: str | int   # Agent index/ID 或 Event timestep 或 Edge source_idx
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        valid_types = {"remove_agent", "modify_belief", "remove_event", "modify_edge", "shift_event"}
        if self.type not in valid_types:
            raise ValueError(f"Invalid intervention type: {self.type}. Must be one of {valid_types}")


@dataclass
class InterventionResult:
    """介入套用結果。"""
    B0: np.ndarray           # 修改後的 B0
    W: np.ndarray            # 修改後的 W
    events: dict             # 修改後的 events
    applied: list[str]       # 已套用的介入描述
    removed_agents: list[int] = field(default_factory=list)


class InterventionEngine:
    """套用介入到仿真參數，回傳修改後的狀態。

    所有操作 immutable——原始 B0, W, events 不會被修改。
    """

    def apply(
        self,
        B0: np.ndarray,
        W: np.ndarray,
        events: dict[int, np.ndarray],
        interventions: list[Intervention],
        agent_names: list[str] | None = None,
    ) -> InterventionResult:
        """套用所有介入，回傳修改後的仿真參數。"""
        B_new = B0.copy()
        W_new = W.copy()
        events_new = copy.deepcopy(events)
        applied: list[str] = []
        removed_agents: list[int] = []

        for iv in interventions:
            if iv.type == "remove_agent":
                idx = self._resolve_agent_index(iv.target, agent_names)
                if idx is not None and 0 <= idx < W_new.shape[0]:
                    W_new[idx, :] = 0.0   # 失去影響力（不被影響）
                    W_new[:, idx] = 0.0   # 不影響他人
                    removed_agents.append(idx)
                    name = agent_names[idx] if agent_names else str(idx)
                    desc = iv.description or f"移除 Agent: {name}"
                    applied.append(desc)
                    logger.info("intervention: remove_agent %s (idx=%d)", name, idx)

            elif iv.type == "modify_belief":
                idx = self._resolve_agent_index(iv.target, agent_names)
                dim = iv.params.get("dim")
                value = iv.params.get("value")
                if idx is not None and dim is not None and value is not None:
                    old_val = B_new[idx, dim]
                    B_new[idx, dim] = np.clip(float(value), -1.0, 1.0)
                    name = agent_names[idx] if agent_names else str(idx)
                    desc = iv.description or f"{name} dim{dim}: {old_val:.2f} → {value:.2f}"
                    applied.append(desc)
                    logger.info("intervention: modify_belief %s dim%d = %.2f", name, dim, value)

            elif iv.type == "remove_event":
                t = int(iv.target)
                if t in events_new:
                    del events_new[t]
                    desc = iv.description or f"移除 t={t} 事件"
                    applied.append(desc)
                    logger.info("intervention: remove_event t=%d", t)

            elif iv.type == "shift_event":
                t_old = int(iv.target)
                t_new = int(iv.params.get("new_t", t_old))
                if t_old in events_new and t_new != t_old:
                    events_new[t_new] = events_new.pop(t_old)
                    desc = iv.description or f"事件 t={t_old} → t={t_new}"
                    applied.append(desc)
                    logger.info("intervention: shift_event t=%d → t=%d", t_old, t_new)

            elif iv.type == "modify_edge":
                src = self._resolve_agent_index(iv.target, agent_names)
                tgt_raw = iv.params.get("target_idx") or iv.params.get("target")
                tgt = self._resolve_agent_index(tgt_raw, agent_names) if tgt_raw is not None else None
                weight = iv.params.get("weight")
                if src is not None and tgt is not None and weight is not None:
                    old_w = W_new[src, tgt]
                    W_new[src, tgt] = np.clip(float(weight), 0.0, 1.0)
                    src_name = agent_names[src] if agent_names else str(src)
                    tgt_name = agent_names[tgt] if agent_names else str(tgt)
                    desc = iv.description or f"邊 {src_name}→{tgt_name}: {old_w:.2f} → {weight:.2f}"
                    applied.append(desc)
                    logger.info("intervention: modify_edge %s→%s = %.2f", src_name, tgt_name, weight)

        # 確保 W 行和 ≤ 1
        row_sums = W_new.sum(axis=1, keepdims=True)
        mask = row_sums > 1
        W_new = np.where(mask, W_new / np.maximum(row_sums, 1e-9), W_new)

        return InterventionResult(
            B0=B_new,
            W=W_new,
            events=events_new,
            applied=applied,
            removed_agents=removed_agents,
        )

    @staticmethod
    def _resolve_agent_index(target: str | int | None, names: list[str] | None) -> int | None:
        """將 Agent target 解析為 index。"""
        if target is None:
            return None
        if isinstance(target, int):
            return target
        # 嘗試直接轉 int
        try:
            return int(target)
        except (ValueError, TypeError):
            pass
        # 用名稱查找
        if names:
            for i, name in enumerate(names):
                if name == target:
                    return i
        return None


def compute_whatif_diff(
    baseline_mean: np.ndarray,
    whatif_mean: np.ndarray,
    baseline_lambda: float,
    whatif_lambda: float,
    dimension_labels: list[str] | None = None,
) -> dict:
    """計算基準 vs What If 的差異摘要。

    Args:
        baseline_mean: (horizon+1, n_agents, n_dims) 基準仿真平均
        whatif_mean:   (horizon+1, n_agents, n_dims) What If 仿真平均
        baseline_lambda: 基準 λ_max
        whatif_lambda:   What If λ_max

    Returns:
        差異摘要 dict
    """
    # 最終時步差異
    delta_final = whatif_mean[-1] - baseline_mean[-1]  # (n_agents, n_dims)
    n_agents, n_dims = delta_final.shape

    # 每個維度的平均差異
    dim_deltas = []
    for d in range(n_dims):
        label = dimension_labels[d] if dimension_labels and d < len(dimension_labels) else f"dim{d}"
        dim_deltas.append({
            "dim": d,
            "label": label,
            "mean_delta": round(float(delta_final[:, d].mean()), 4),
            "max_delta": round(float(delta_final[:, d].max()), 4),
            "min_delta": round(float(delta_final[:, d].min()), 4),
            "abs_mean": round(float(np.abs(delta_final[:, d]).mean()), 4),
        })

    # 排序：絕對影響最大的維度在前
    dim_deltas.sort(key=lambda x: -x["abs_mean"])

    return {
        "lambda_max_baseline": round(baseline_lambda, 4),
        "lambda_max_whatif": round(whatif_lambda, 4),
        "lambda_max_delta": round(whatif_lambda - baseline_lambda, 4),
        "dimension_deltas": dim_deltas,
        "total_belief_shift": round(float(np.abs(delta_final).mean()), 4),
    }
