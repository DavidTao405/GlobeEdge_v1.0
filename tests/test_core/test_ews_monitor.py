"""EWS Monitor 測試 — P0 必須全過。"""

import pytest

from worldedge.core import EWSAlert, EWSMonitor, MoEEWSMonitor


class TestEWSMonitor:
    def test_no_alert_before_min_samples(self):
        """樣本不足 10 個時不應觸發任何警報。"""
        monitor = EWSMonitor(min_samples=10)
        for _ in range(9):
            alerts = monitor.update({"lambda_max": 0.99, "variance": 100.0})
            assert alerts == []

    def test_lambda_max_critical(self):
        """lambda_max 超過臨界閾值應觸發 critical。"""
        monitor = EWSMonitor(min_samples=5)
        # 先餵入足夠樣本建立基線
        for _ in range(5):
            monitor.update({"lambda_max": 0.5})
        alerts = monitor.update({"lambda_max": 0.96})
        assert len(alerts) == 1
        assert alerts[0].alert_type == "lambda_max"
        assert alerts[0].severity == "critical"

    def test_lambda_max_warn(self):
        """lambda_max 超過警告閾值應觸發 high。"""
        monitor = EWSMonitor(min_samples=5)
        for _ in range(5):
            monitor.update({"lambda_max": 0.5})
        alerts = monitor.update({"lambda_max": 0.87})
        assert len(alerts) == 1
        assert alerts[0].severity == "high"

    def test_variance_z_score(self):
        """variance 的 z-score 超標應觸發警報。"""
        monitor = EWSMonitor(min_samples=10)
        # 建立穩定基線
        for _ in range(20):
            monitor.update({"variance": 0.1})
        # 突然暴增
        alerts = monitor.update({"variance": 10.0})
        assert len(alerts) >= 1
        assert any(a.alert_type == "variance" for a in alerts)

    def test_no_alert_for_normal_values(self):
        """正常範圍的值不應觸發警報。"""
        monitor = EWSMonitor(min_samples=10)
        for _ in range(20):
            alerts = monitor.update({"lambda_max": 0.5, "variance": 0.1})
        # 穩定值不應報警
        assert alerts == []

    def test_welford_accuracy(self):
        """Welford z-score 應準確。"""
        monitor = EWSMonitor(min_samples=10)
        # 餵入 100 個 N(0,1) 的值
        import numpy as np
        rng = np.random.default_rng(42)
        values = rng.normal(0, 1, 100)
        for v in values:
            monitor.update({"test": float(v)})
        # Welford 的 mean 和 std 應接近 0, 1
        assert abs(monitor._mean["test"]) < 0.3
        std = (monitor._M2["test"] / (monitor._n - 1)) ** 0.5
        assert abs(std - 1.0) < 0.3

    def test_reset(self):
        """reset 後應回到初始狀態。"""
        monitor = EWSMonitor(min_samples=5)
        for _ in range(10):
            monitor.update({"lambda_max": 0.5})
        monitor.reset()
        assert monitor._n == 0
        assert len(monitor._mean) == 0

    def test_multiple_metrics(self):
        """同時追蹤多個指標。"""
        monitor = EWSMonitor(min_samples=5)
        for _ in range(5):
            monitor.update({"lambda_max": 0.5, "variance": 0.1})
        alerts = monitor.update({"lambda_max": 0.96, "variance": 0.1})
        # 只有 lambda_max 超標
        assert len(alerts) == 1
        assert alerts[0].alert_type == "lambda_max"

    def test_custom_thresholds(self):
        """自定閾值應生效。"""
        monitor = EWSMonitor(
            thresholds={"custom": {"warn": 0.5, "critical": 0.8}},
            min_samples=5,
        )
        for _ in range(5):
            monitor.update({"custom": 0.2})
        alerts = monitor.update({"custom": 0.6})
        assert len(alerts) == 1
        assert alerts[0].severity == "high"


class TestMoEEWSMonitor:
    """MoE 多專家 EWS 測試。"""

    def test_single_expert_trigger(self):
        """單一專家觸發，expert 欄位正確。"""
        monitor = MoEEWSMonitor()
        for _ in range(10):
            monitor.update({"lambda_max": 0.5, "variance": 0.1, "csd": 0.8})
        alerts = monitor.update({"lambda_max": 0.99, "variance": 0.1, "csd": 0.8})
        assert any(a.expert == "structural" for a in alerts)

    def test_escalation(self):
        """多專家同時觸發 → 升級 severity。"""
        monitor = MoEEWSMonitor()
        for _ in range(15):
            monitor.update({"lambda_max": 0.5, "variance": 0.1, "csd": 0.8})
        # 同時觸發 structural + belief
        alerts = monitor.update({"lambda_max": 9.9, "variance": 9.9, "csd": 0.8})
        assert len(alerts) >= 2
        severities = {a.severity for a in alerts}
        assert "high" in severities or "critical" in severities

    def test_no_alert_warmup(self):
        """warmup 期間不應有警報。"""
        monitor = MoEEWSMonitor()
        for _ in range(4):
            alerts = monitor.update({"lambda_max": 99.0, "variance": 99.0, "csd": 99.0})
            # structural/velocity 有 min_samples=10/15，
            # belief 有 min_samples=5
            # 前 4 次全部不應觸發
            assert alerts == []

    def test_belief_expert_fast_reaction(self):
        """belief 專家 min_samples=5，反應比 velocity 快。"""
        monitor = MoEEWSMonitor()
        # 餵 5 個正常值
        for _ in range(5):
            monitor.update({"variance": 0.1, "csd": 0.8})
        # 第 6 次異常
        alerts = monitor.update({"variance": 99.0, "csd": 99.0})
        # belief 已有 6 個樣本 > min_samples=5，應觸發
        # velocity 只有 6 個樣本 < min_samples=15，不應觸發
        experts = {a.expert for a in alerts}
        assert "belief" in experts
        assert "velocity" not in experts

    def test_reset(self):
        """reset 後所有專家回到初始狀態。"""
        monitor = MoEEWSMonitor()
        for _ in range(20):
            monitor.update({"lambda_max": 0.5})
        monitor.reset()
        for expert in monitor.experts.values():
            assert expert._n == 0

    def test_backward_compat_interface(self):
        """MoEEWSMonitor.update() 介面與 EWSMonitor 相容。"""
        monitor = MoEEWSMonitor()
        result = monitor.update({"lambda_max": 0.5})
        assert isinstance(result, list)
