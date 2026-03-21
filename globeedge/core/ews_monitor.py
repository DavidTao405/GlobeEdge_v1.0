"""EWSMonitor — Early Warning Signals 偵測器（Welford 線上演算法）。

包含兩個版本：
  EWSMonitor    — 原版，單一 Welford 追蹤器
  MoEEWSMonitor — MoE 版，三專家分工，支援複合預警升級
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EWSAlert:
    """一筆 EWS 警報。"""

    alert_type: str       # lambda_max | variance | csd | convergence
    severity: str         # low | medium | high | critical
    metric_value: float
    threshold: float
    z_score: float
    description: str
    expert: str = ""      # MoE 版：哪個專家觸發的


class EWSMonitor:
    """使用 Welford 線上演算法追蹤指標的 z-score，偵測異常。

    Args:
        thresholds: 各指標的閾值字典，例如：
            {
                "lambda_max": {"warn": 0.85, "critical": 0.95},
                "variance":   {"z_warn": 2.0, "z_critical": 3.0},
                "csd":        {"z_warn": 2.0, "z_critical": 3.0},
            }
        min_samples: 最少樣本數才開始偵測（防假警報）
    """

    DEFAULT_THRESHOLDS = {
        "lambda_max": {"warn": 0.85, "critical": 0.95},
        "variance": {"z_warn": 2.0, "z_critical": 3.0},
        "csd": {"z_warn": 2.0, "z_critical": 3.0},
    }

    def __init__(
        self,
        thresholds: Optional[dict] = None,
        min_samples: int = 10,
    ) -> None:
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.min_samples = min_samples
        self._n: int = 0
        self._mean: dict[str, float] = {}
        self._M2: dict[str, float] = {}

    def update(self, metrics: dict[str, float]) -> list[EWSAlert]:
        """餵入一組指標值，回傳觸發的警報列表。

        Args:
            metrics: 例如 {"lambda_max": 0.87, "variance": 0.12, "csd": 0.3}
        """
        self._n += 1
        alerts: list[EWSAlert] = []

        for key, value in metrics.items():
            z = self._welford_update(key, value)
            alert = self._check(key, value, z)
            if alert is not None:
                alerts.append(alert)

        return alerts

    def _welford_update(self, key: str, value: float) -> float:
        """Welford 線上更新，回傳當前 z-score。"""
        if key not in self._mean:
            self._mean[key] = 0.0
            self._M2[key] = 0.0

        delta = value - self._mean[key]
        self._mean[key] += delta / self._n
        delta2 = value - self._mean[key]
        self._M2[key] += delta * delta2

        if self._n < self.min_samples:
            return 0.0

        std = (self._M2[key] / (self._n - 1)) ** 0.5 + 1e-9
        return (value - self._mean[key]) / std

    def _check(self, key: str, value: float, z: float) -> Optional[EWSAlert]:
        """根據閾值檢查是否觸發警報。"""
        if self._n < self.min_samples:
            return None

        cfg = self.thresholds.get(key)
        if cfg is None:
            return None

        # 絕對閾值檢查（lambda_max 用）
        critical_abs = cfg.get("critical")
        warn_abs = cfg.get("warn")
        if critical_abs is not None and value >= critical_abs:
            return EWSAlert(
                alert_type=key,
                severity="critical",
                metric_value=value,
                threshold=critical_abs,
                z_score=z,
                description=f"{key} = {value:.4f} 超過臨界閾值 {critical_abs}",
            )
        if warn_abs is not None and value >= warn_abs:
            return EWSAlert(
                alert_type=key,
                severity="high",
                metric_value=value,
                threshold=warn_abs,
                z_score=z,
                description=f"{key} = {value:.4f} 超過警告閾值 {warn_abs}",
            )

        # z-score 檢查（variance, csd 用）
        z_critical = cfg.get("z_critical")
        z_warn = cfg.get("z_warn")
        if z_critical is not None and abs(z) >= z_critical:
            return EWSAlert(
                alert_type=key,
                severity="critical",
                metric_value=value,
                threshold=z_critical,
                z_score=z,
                description=f"{key} z-score = {z:.2f} 超過臨界閾值 ±{z_critical}",
            )
        if z_warn is not None and abs(z) >= z_warn:
            return EWSAlert(
                alert_type=key,
                severity="high",
                metric_value=value,
                threshold=z_warn,
                z_score=z,
                description=f"{key} z-score = {z:.2f} 超過警告閾值 ±{z_warn}",
            )

        return None

    def reset(self) -> None:
        """重置所有統計量。"""
        self._n = 0
        self._mean.clear()
        self._M2.clear()


# ── MoE 多專家 EWS ──────────────────────────────────────

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_NEXT_SEVERITY = {"low": "medium", "medium": "high", "high": "critical", "critical": "critical"}


class EWSExpert:
    """單一 Welford 專家，只追蹤一組指標。"""

    def __init__(
        self, name: str, thresholds: dict, min_samples: int = 10
    ) -> None:
        self.name = name
        self.thresholds = thresholds
        self.min_samples = min_samples
        self._n: int = 0
        self._mean: dict[str, float] = {}
        self._M2: dict[str, float] = {}

    def update(self, metrics: dict[str, float]) -> list[EWSAlert]:
        self._n += 1
        alerts: list[EWSAlert] = []
        for key, value in metrics.items():
            z = self._welford_update(key, value)
            alert = self._check(key, value, z)
            if alert is not None:
                alerts.append(alert)
        return alerts

    def _welford_update(self, key: str, value: float) -> float:
        if key not in self._mean:
            self._mean[key] = 0.0
            self._M2[key] = 0.0
        delta = value - self._mean[key]
        self._mean[key] += delta / self._n
        delta2 = value - self._mean[key]
        self._M2[key] += delta * delta2

        if self._n < self.min_samples:
            return 0.0
        std = (self._M2[key] / (self._n - 1)) ** 0.5 + 1e-9
        return (value - self._mean[key]) / std

    def _check(
        self, key: str, value: float, z: float
    ) -> Optional[EWSAlert]:
        if self._n < self.min_samples:
            return None
        threshold = self.thresholds.get(f"{key}_z", 2.0)
        if abs(z) < threshold:
            return None
        severity = (
            "critical" if abs(z) >= 3.0 else
            "high"     if abs(z) >= 2.5 else
            "medium"   if abs(z) >= 2.0 else
            "low"
        )
        return EWSAlert(
            alert_type=key,
            severity=severity,
            metric_value=value,
            threshold=threshold,
            z_score=z,
            description=f"{key} z={z:.2f} (expert={self.name})",
            expert=self.name,
        )

    def reset(self) -> None:
        self._n = 0
        self._mean.clear()
        self._M2.clear()


class MoEEWSMonitor:
    """MoE 多專家 EWS。

    三個專家各自負責一類訊號，降低假警報：
      structural — λ_max（W 矩陣結構穩定性）
      belief     — variance（信念向量漂移）
      velocity   — CSD（系統恢復速度）

    複合預警：兩個以上專家同時觸發 → 升級 severity。
    """

    def __init__(self, thresholds: Optional[dict] = None) -> None:
        t = thresholds or {}
        self.experts = {
            "structural": EWSExpert(
                name="structural",
                thresholds={"lambda_max_z": t.get("lambda_max_z", 2.0)},
            ),
            "belief": EWSExpert(
                name="belief",
                thresholds={"variance_z": t.get("variance_z", 1.5)},
                min_samples=5,
            ),
            "velocity": EWSExpert(
                name="velocity",
                thresholds={"csd_z": t.get("csd_z", 2.5)},
                min_samples=15,
            ),
        }

    def update(self, metrics: dict[str, float]) -> list[EWSAlert]:
        """餵入指標，各專家獨立判斷，複合觸發時升級。"""
        alerts: list[EWSAlert] = []
        if "lambda_max" in metrics:
            alerts += self.experts["structural"].update(
                {"lambda_max": metrics["lambda_max"]}
            )
        if "variance" in metrics:
            alerts += self.experts["belief"].update(
                {"variance": metrics["variance"]}
            )
        if "csd" in metrics:
            alerts += self.experts["velocity"].update(
                {"csd": metrics["csd"]}
            )
        if len(alerts) >= 2:
            alerts = self._escalate(alerts)
        return alerts

    def _escalate(self, alerts: list[EWSAlert]) -> list[EWSAlert]:
        """多專家同時觸發 → 升級最高嚴重度的那個。"""
        top = max(alerts, key=lambda a: _SEVERITY_RANK[a.severity])
        top.severity = _NEXT_SEVERITY[top.severity]
        top.description = f"複合預警：{len(alerts)} 個專家同時觸發"
        return alerts

    def reset(self) -> None:
        for expert in self.experts.values():
            expert.reset()
