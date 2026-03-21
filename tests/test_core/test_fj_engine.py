"""FJ 引擎測試 — P0 必須全過。"""

from datetime import datetime

import numpy as np
import pytest

from globeedge.core import BeliefState, FJEngine


def _make_state(n=5, d=8, seed=42):
    rng = np.random.default_rng(seed)
    W = rng.dirichlet(np.ones(n), size=n)  # 行和 = 1
    B = rng.uniform(-1, 1, (n, d))
    return BeliefState(t=0, B=B, W=W, timestamp=datetime.now()), B.copy()


class TestFJEngine:
    def test_alpha_bounds(self):
        b0 = np.zeros((3, 8))
        with pytest.raises(ValueError):
            FJEngine(alpha=0.0, b0=b0)
        with pytest.raises(ValueError):
            FJEngine(alpha=1.0, b0=b0)
        with pytest.raises(ValueError):
            FJEngine(alpha=-0.1, b0=b0)

    def test_single_step(self):
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)
        next_state = engine.step(state)
        assert next_state.t == 1
        assert next_state.B.shape == state.B.shape
        assert np.all(next_state.B >= -1.0)
        assert np.all(next_state.B <= 1.0)

    def test_convergence(self):
        """FJ 引擎在足夠多步後應收斂（方差趨近零）。"""
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)
        trajectory = engine.run(state, horizon=100)
        # 最後 10 步的信念矩陣方差應很小
        last_10_B = np.array([s.B for s in trajectory[-10:]])
        assert last_10_B.var(axis=0).max() < 0.01

    def test_trajectory_length(self):
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)
        trajectory = engine.run(state, horizon=50)
        assert len(trajectory) == 51  # initial + 50 steps

    def test_event_injection(self):
        """外部事件注入後，對應維度信念應改變。"""
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)

        event = np.zeros((5, 8))
        event[:, 7] = 0.5  # 外部威脅感知 +0.5

        state_after = engine.step(state, event=event)
        assert state_after.B[:, 7].mean() > state.B[:, 7].mean()

    def test_event_at_specific_timestep(self):
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)

        event = np.zeros((5, 8))
        event[:, 3] = 0.8  # 經濟焦慮

        trajectory = engine.run(state, horizon=10, events={5: event})
        # t=5 注入事件後 t=6 的信念應反映衝擊
        assert trajectory[6].B[:, 3].mean() > trajectory[4].B[:, 3].mean()

    def test_noise_adds_variation(self):
        """加噪聲應讓不同 run 的結果不同。"""
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)

        np.random.seed(1)
        traj1 = engine.run(state, horizon=10, noise=0.1)
        np.random.seed(2)
        traj2 = engine.run(state, horizon=10, noise=0.1)

        # 最後一步應該不完全相同
        assert not np.allclose(traj1[-1].B, traj2[-1].B)

    def test_clip_bounds(self):
        """即使有極端事件，信念值仍在 [-1, 1]。"""
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)

        extreme_event = np.full((5, 8), 10.0)
        result = engine.step(state, event=extreme_event)
        assert np.all(result.B <= 1.0)
        assert np.all(result.B >= -1.0)

    def test_w_preserved(self):
        """step 不應改變 W 矩陣。"""
        state, b0 = _make_state()
        engine = FJEngine(alpha=0.7, b0=b0)
        W_original = state.W.copy()
        result = engine.step(state)
        np.testing.assert_array_equal(result.W, W_original)
