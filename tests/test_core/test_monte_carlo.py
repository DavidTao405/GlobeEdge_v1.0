"""Monte Carlo 模擬測試 — P0 必須全過。"""

import numpy as np
import pytest

from worldedge.core import AgentNoiseProfile, FJEngine, MonteCarloRunner, SimulationDistribution


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


class TestMoENoise:
    """MoE 分層噪聲測試。"""

    def test_moe_noise_distribution(self):
        """KOL 的噪聲標準差應大於 media。"""
        engine, B0, W = _setup(n=3, d=8)
        runner = MonteCarloRunner(
            engine, n_runs=10, seed=42,
            agent_types=["media", "kol", "demographic"],
        )
        samples = np.array([
            runner._build_noise_for_B((3, 8), noise_level=1.0)
            for _ in range(1000)
        ])
        media_std = samples[:, 0, :].std()
        kol_std = samples[:, 1, :].std()
        demo_std = samples[:, 2, :].std()

        assert kol_std > media_std, f"kol={kol_std:.4f} <= media={media_std:.4f}"
        assert demo_std > media_std, f"demo={demo_std:.4f} <= media={media_std:.4f}"

    def test_moe_fallback_without_types(self):
        """沒有 agent_types 時應 fallback 為均勻噪聲。"""
        engine, B0, W = _setup()
        runner = MonteCarloRunner(engine, n_runs=50, seed=0)
        dist = runner.run(B0, W, horizon=10)
        assert dist.trajectories.shape[0] == 50

    def test_moe_with_types_shape(self):
        """有 agent_types 時 output shape 不變。"""
        engine, B0, W = _setup(n=5)
        runner = MonteCarloRunner(
            engine, n_runs=50, seed=0,
            agent_types=["media", "kol", "demographic", "forum", "institution"],
        )
        dist = runner.run(B0, W, horizon=10)
        assert dist.trajectories.shape == (50, 11, 5, 8)

    def test_moe_values_in_range(self):
        """MoE 噪聲後信念值仍在 [-1, 1]。"""
        engine, B0, W = _setup(n=5)
        runner = MonteCarloRunner(
            engine, n_runs=100, seed=0,
            agent_types=["media", "kol", "demographic", "forum", "institution"],
        )
        dist = runner.run(B0, W, horizon=10)
        assert np.all(dist.trajectories >= -1.0)
        assert np.all(dist.trajectories <= 1.0)

    def test_kol_laplace_heavier_tails(self):
        """KOL 使用 Laplace 分佈，尾部應比 media (Normal) 更重。"""
        engine, B0, W = _setup(n=2, d=8)
        runner = MonteCarloRunner(
            engine, n_runs=10, seed=42,
            agent_types=["media", "kol"],
        )
        samples = np.array([
            runner._build_noise_for_B((2, 8), noise_level=1.0)
            for _ in range(5000)
        ])
        # kurtosis of Laplace > Normal
        from scipy.stats import kurtosis
        media_kurt = kurtosis(samples[:, 0, :].flatten())
        kol_kurt = kurtosis(samples[:, 1, :].flatten())
        assert kol_kurt > media_kurt, f"kol_kurt={kol_kurt:.2f} <= media_kurt={media_kurt:.2f}"
