"""EWSMonitor — Early Warning Signals 偵測器（Welford 線上演算法）。"""

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
