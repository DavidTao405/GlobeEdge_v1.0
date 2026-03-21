"""SimulationDistribution 測試。"""

import numpy as np

from globeedge.core import SimulationDistribution


def _make_dist(n_runs=100, horizon=10, n_agents=5, n_dims=8, seed=42):
    rng = np.random.default_rng(seed)
    data = rng.uniform(-1, 1, (n_runs, horizon + 1, n_agents, n_dims))
    return SimulationDistribution(trajectories=data)


class TestSimulationDistribution:
    def test_properties(self):
        dist = _make_dist(n_runs=50, horizon=20, n_agents=3, n_dims=4)
        assert dist.n_runs == 50
        assert dist.horizon == 20
        assert dist.n_agents == 3
        assert dist.n_dims == 4

    def test_mean_shape(self):
        dist = _make_dist()
        assert dist.mean().shape == (11, 5, 8)

    def test_std_shape(self):
        dist = _make_dist()
        assert dist.std().shape == (11, 5, 8)

    def test_ci_shape_and_order(self):
        dist = _make_dist()
        lower, upper = dist.ci(0.95)
        assert lower.shape == (11, 5, 8)
        assert np.all(lower <= upper)

    def test_percentile(self):
        dist = _make_dist()
        p50 = dist.percentile(50)
        assert p50.shape == (11, 5, 8)

    def test_variance_over_time_shape(self):
        dist = _make_dist()
        v = dist.variance_over_time()
        assert v.shape == (11,)
        assert np.all(v >= 0)
