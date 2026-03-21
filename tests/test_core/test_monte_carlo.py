"""Monte Carlo 模擬測試 — P0 必須全過。"""

import numpy as np
import pytest

from worldedge.core import FJEngine, MonteCarloRunner, SimulationDistribution


def _setup(n=5, d=8, seed=42):
    rng = np.random.default_rng(seed)
    W = rng.dirichlet(np.ones(n), size=n)
    B0 = rng.uniform(-1, 1, (n, d))
    engine = FJEngine(alpha=0.7, b0=B0)
    return engine, B0, W


class TestMonteCarloRunner:
    def test_output_is_distribution(self):
        engine, B0, W = _setup()
        runner = MonteCarloRunner(engine, n_runs=100, seed=0)
        dist = runner.run(B0, W, horizon=10)
        assert isinstance(dist, SimulationDistribution)

    def test_shape(self):
        engine, B0, W = _setup()
        n_runs, horizon = 50, 20
        runner = MonteCarloRunner(engine, n_runs=n_runs, seed=0)
        dist = runner.run(B0, W, horizon=horizon)
        assert dist.trajectories.shape == (n_runs, horizon + 1, 5, 8)

    def test_not_single_point(self):
        """Monte Carlo 輸出應是分佈，不是單一結果。"""
        engine, B0, W = _setup()
        runner = MonteCarloRunner(engine, n_runs=100, noise_level=0.05, seed=0)
        dist = runner.run(B0, W, horizon=20)
        # 不同 run 的最終信念應有差異
        final = dist.trajectories[:, -1, :, :]
        assert final.std() > 1e-6

    def test_ci_contains_mean(self):
        """95% CI 應包含 mean。"""
        engine, B0, W = _setup()
        runner = MonteCarloRunner(engine, n_runs=200, seed=0)
        dist = runner.run(B0, W, horizon=10)
        mean = dist.mean()
        lower, upper = dist.ci(0.95)
        # mean 應大致在 CI 範圍內
        assert np.all(mean >= lower - 1e-6)
        assert np.all(mean <= upper + 1e-6)

    def test_values_in_range(self):
        """所有信念值應在 [-1, 1]。"""
        engine, B0, W = _setup()
        runner = MonteCarloRunner(engine, n_runs=100, seed=0)
        dist = runner.run(B0, W, horizon=10)
        assert np.all(dist.trajectories >= -1.0)
        assert np.all(dist.trajectories <= 1.0)

    def test_seed_reproducibility(self):
        """相同 seed 應產生相同結果。"""
        engine, B0, W = _setup()
        r1 = MonteCarloRunner(engine, n_runs=50, seed=123)
        r2 = MonteCarloRunner(engine, n_runs=50, seed=123)
        d1 = r1.run(B0, W, horizon=10)
        d2 = r2.run(B0, W, horizon=10)
        np.testing.assert_array_equal(d1.trajectories, d2.trajectories)

    def test_event_injection(self):
        """事件注入應改變分佈。"""
        engine, B0, W = _setup()
        event = np.zeros((5, 8))
        event[:, 7] = 0.5

        r1 = MonteCarloRunner(engine, n_runs=100, seed=0)
        d_no_event = r1.run(B0, W, horizon=10)

        r2 = MonteCarloRunner(engine, n_runs=100, seed=0)
        d_with_event = r2.run(B0, W, horizon=10, events={5: event})

        # 事件後的維度 7 平均值應較高
        mean_no = d_no_event.mean()[-1, :, 7].mean()
        mean_ev = d_with_event.mean()[-1, :, 7].mean()
        assert mean_ev > mean_no
