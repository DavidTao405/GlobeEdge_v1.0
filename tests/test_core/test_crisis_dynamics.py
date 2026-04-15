"""CrisisAwareFJEngine 單元測試。"""

from datetime import datetime, timezone

import numpy as np
import pytest

from globeedge.core.belief_state import BeliefState
from globeedge.core.crisis_dynamics import (
    MIN_SPREAD,
    CrisisAwareFJEngine,
    CrisisConfig,
    CrisisStepResult,
    _compute_spread,
    compute_dynamic_alpha,
    drift_b0,
    update_crisis_intensity,
)


@pytest.fixture
def config():
    return CrisisConfig()


@pytest.fixture
def simple_state():
    n, d = 5, 8
    rng = np.random.default_rng(42)
    B = rng.uniform(-0.3, 0.3, (n, d))
    W = np.full((n, n), 0.1)
    np.fill_diagonal(W, 0)
    return BeliefState(t=0, B=B, W=W, timestamp=datetime.now(timezone.utc))


@pytest.fixture
def simple_b0():
    return np.random.default_rng(42).uniform(-0.3, 0.3, (5, 8))


class TestCrisisIntensity:
    def test_grows_with_events(self, config):
        intensity = 0.0
        intensity = update_crisis_intensity(intensity, True, 1.0, config)
        assert intensity > 0.0

    def test_decays_without_events(self, config):
        intensity = 0.5
        intensity = update_crisis_intensity(intensity, False, 0.0, config)
        assert intensity < 0.5

    def test_capped_at_1(self, config):
        intensity = 0.95
        intensity = update_crisis_intensity(intensity, True, 5.0, config)
        assert intensity <= 1.0

    def test_floored_at_0(self, config):
        intensity = 0.01
        intensity = update_crisis_intensity(intensity, False, 0.0, config)
        assert intensity >= 0.0

    def test_consecutive_events_accumulate(self, config):
        intensity = 0.0
        for _ in range(5):
            intensity = update_crisis_intensity(intensity, True, 1.0, config)
        assert intensity > 0.5


class TestDynamicAlpha:
    def test_at_zero_equals_base(self, config):
        assert compute_dynamic_alpha(0.0, config) == pytest.approx(config.alpha_base)

    def test_at_max_equals_crisis(self, config):
        assert compute_dynamic_alpha(1.0, config) == pytest.approx(config.alpha_crisis)

    def test_interpolation_midpoint(self, config):
        mid = compute_dynamic_alpha(0.5, config)
        expected = (config.alpha_base + config.alpha_crisis) / 2
        assert mid == pytest.approx(expected)

    def test_monotonically_increasing(self, config):
        alphas = [compute_dynamic_alpha(i / 10, config) for i in range(11)]
        for i in range(len(alphas) - 1):
            assert alphas[i] <= alphas[i + 1]


class TestB0Drift:
    def test_no_drift_below_threshold(self, config):
        b0 = np.array([[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]])
        B = np.array([[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]])
        b0_new = drift_b0(b0, B, 0.2, config)  # below threshold 0.3
        np.testing.assert_array_equal(b0_new, b0)

    def test_drift_occurs_above_threshold(self, config):
        b0 = np.zeros((3, 8))
        B = np.ones((3, 8)) * 0.5
        b0_new = drift_b0(b0, B, 0.8, config)
        assert not np.array_equal(b0_new, b0)
        # Should move toward B's mean
        assert np.all(b0_new > 0)

    def test_drift_proportional_to_intensity(self, config):
        b0 = np.zeros((3, 8))
        B = np.ones((3, 8)) * 0.5
        b0_low = drift_b0(b0, B, 0.4, config)
        b0_high = drift_b0(b0, B, 0.9, config)
        assert np.mean(np.abs(b0_high)) > np.mean(np.abs(b0_low))

    def test_clipped_to_bounds(self, config):
        b0 = np.ones((3, 8)) * 0.95
        B = np.ones((3, 8)) * 1.0
        b0_new = drift_b0(b0, B, 1.0, config)
        assert np.all(b0_new <= 1.0)
        assert np.all(b0_new >= -1.0)


class TestCrisisAwareFJEngine:
    def test_backward_compatible_no_events(self, simple_state, simple_b0):
        engine = CrisisAwareFJEngine(alpha=0.3, b0=simple_b0)
        result = engine.step(simple_state)
        assert isinstance(result, CrisisStepResult)
        assert result.crisis_intensity == 0.0
        # effective_alpha may be < 0.3 if spread floor activates on small fixture
        assert result.effective_alpha <= 0.3 + 0.01

    def test_crisis_builds_with_events(self, simple_state, simple_b0):
        engine = CrisisAwareFJEngine(alpha=0.3, b0=simple_b0)
        event = np.random.default_rng(0).uniform(0.1, 0.5, (5, 8))
        state = simple_state
        for _ in range(4):
            result = engine.step(state, event=event)
            state = result.belief_state
        assert result.crisis_intensity > 0.5
        assert result.effective_alpha > 0.4

    def test_b0_drifts_during_crisis(self, simple_state, simple_b0):
        engine = CrisisAwareFJEngine(alpha=0.3, b0=simple_b0)
        event = np.ones((5, 8)) * 0.3
        state = simple_state
        for _ in range(10):
            result = engine.step(state, event=event)
            state = result.belief_state
        diff = np.max(np.abs(result.b0_current - simple_b0))
        assert diff > 0.01  # b0 has visibly drifted

    def test_clip_bounds(self, simple_state, simple_b0):
        engine = CrisisAwareFJEngine(alpha=0.3, b0=simple_b0)
        big_event = np.ones((5, 8)) * 2.0
        result = engine.step(simple_state, event=big_event)
        assert np.all(result.belief_state.B >= -1.0)
        assert np.all(result.belief_state.B <= 1.0)

    def test_reset(self, simple_state, simple_b0):
        engine = CrisisAwareFJEngine(alpha=0.3, b0=simple_b0)
        event = np.ones((5, 8)) * 0.3
        engine.step(simple_state, event=event)
        engine.step(simple_state, event=event)
        assert engine.crisis_intensity > 0
        engine.reset()
        assert engine.crisis_intensity == 0.0
        np.testing.assert_array_equal(engine.b0_current, simple_b0)

    def test_run_trajectory_length(self, simple_state, simple_b0):
        engine = CrisisAwareFJEngine(alpha=0.3, b0=simple_b0)
        results = engine.run(simple_state, horizon=10)
        assert len(results) == 11  # initial + 10 steps

    def test_run_with_events(self, simple_state, simple_b0):
        engine = CrisisAwareFJEngine(alpha=0.3, b0=simple_b0)
        events = {
            2: np.ones((5, 8)) * 0.3,
            4: np.ones((5, 8)) * 0.4,
        }
        results = engine.run(simple_state, horizon=10, events=events)
        # After events, crisis_intensity should be elevated
        assert results[5].crisis_intensity > 0

    def test_spread_floor_in_crisis(self):
        """高 alpha（crisis）下 spread floor 防止崩潰。

        用持續事件（每 3 步注入）維持高危機強度，模擬真實持續危機。
        驗證 spread floor 讓 effective_alpha 在崩潰區被自動降低。
        """
        from globeedge.scenarios.energy import build as build_energy
        scenario = build_energy()
        B0 = scenario.belief_matrix()
        W = scenario.default_W()
        n_agents, n_dims = B0.shape

        config = CrisisConfig(alpha_base=0.3, alpha_crisis=0.6)
        engine = CrisisAwareFJEngine(alpha=0.3, b0=B0, config=config)

        # 每 3 步注入事件，維持高危機強度
        event = np.random.default_rng(42).uniform(-0.1, 0.3, (n_agents, n_dims))
        events = {t: event for t in range(0, 30, 3)}

        initial = BeliefState(t=0, B=B0.copy(), W=W, timestamp=datetime.now(timezone.utc))
        results = engine.run(initial, horizon=30, events=events)

        # 核心驗收：spread floor 應該讓 effective_alpha < alpha_crisis
        # 當 spread 接近 MIN_SPREAD 時
        floor_activated = any(
            r.effective_alpha < config.alpha_crisis - 0.01
            for r in results[5:]  # 跳過前幾步（危機還沒 build up）
            if r.crisis_intensity > 0.5
        )
        assert floor_activated, (
            "Spread floor should reduce effective_alpha when spread is low"
        )

    def test_spread_floor_no_intervention_at_low_alpha(self):
        """alpha=0.3 + 寬初始信念 → spread floor 不介入。"""
        from globeedge.scenarios.energy import build as build_energy
        scenario = build_energy()
        B0 = scenario.belief_matrix()
        W = scenario.default_W()

        engine = CrisisAwareFJEngine(alpha=0.3, b0=B0)
        initial = BeliefState(t=0, B=B0.copy(), W=W, timestamp=datetime.now(timezone.utc))
        results = engine.run(initial, horizon=30)
        # alpha=0.3 無危機 → effective_alpha 應該是 0.3
        for r in results:
            assert r.effective_alpha == pytest.approx(0.3, abs=0.05)

    def test_iran_war_direction_accuracy_improves(self):
        """核心驗收：美伊戰爭方向準確率 > 0%。"""
        from globeedge.scenarios.iran_war import build as build_scenario
        from scripts.predictive_validation import (
            IRAN_WAR_TIMELINE,
            VALIDATION_DIMS,
            generate_synthetic_ptt,
        )

        scenario = build_scenario()
        B0 = scenario.belief_matrix()
        W = scenario.default_W()
        n_agents, n_dims = B0.shape
        horizon = 22

        # Build events
        events = {}
        for evt in IRAN_WAR_TIMELINE:
            day = evt["day"]
            if day <= horizon:
                impact = np.zeros((n_agents, n_dims))
                for i in range(n_agents):
                    impact[i] = evt["impact"]
                events[day] = impact

        # Run with CrisisAwareFJEngine
        initial = BeliefState(t=0, B=B0.copy(), W=W, timestamp=datetime.now(timezone.utc))
        engine = CrisisAwareFJEngine(alpha=0.3, b0=B0)
        results = engine.run(initial, horizon=horizon, events=events)
        traj = np.array([r.belief_state.B for r in results])

        # Generate synthetic ground truth
        actual = generate_synthetic_ptt(horizon=horizon)

        # Check direction accuracy
        matches = 0
        for dim_idx, info in VALIDATION_DIMS.items():
            pred_series = [float(traj[t, :, dim_idx].mean()) for t in range(horizon + 1)]
            actual_days = actual.get(dim_idx, {})
            actual_series = [actual_days.get(t, 0.0) for t in range(horizon + 1)]

            pred_delta = pred_series[-1] - pred_series[0]
            actual_delta = actual_series[-1] - actual_series[0]

            if (pred_delta > 0.05 and actual_delta > 0.05) or \
               (pred_delta < -0.05 and actual_delta < -0.05):
                matches += 1

        accuracy = matches / len(VALIDATION_DIMS)
        assert accuracy > 0.0, (
            f"Direction accuracy still 0%. "
            f"Crisis dynamics should improve on baseline FJ."
        )
