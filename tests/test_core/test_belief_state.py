"""BeliefState 測試。"""

from datetime import datetime

import numpy as np
import pytest

from worldedge.core import BeliefState


class TestBeliefState:
    def test_frozen(self):
        """BeliefState 必須不可變。"""
        state = BeliefState(
            t=0,
            B=np.zeros((3, 8)),
            W=np.eye(3),
            timestamp=datetime.now(),
        )
        with pytest.raises(AttributeError):
            state.t = 1

    def test_lambda_max(self):
        """identity matrix 的 lambda_max 應為 1。"""
        state = BeliefState(
            t=0,
            B=np.zeros((3, 8)),
            W=np.eye(3),
            timestamp=datetime.now(),
        )
        assert abs(state.lambda_max() - 1.0) < 1e-10

    def test_lambda_max_dirichlet(self):
        """隨機 row-stochastic 矩陣的 lambda_max 應 ≤ 1。"""
        rng = np.random.default_rng(0)
        W = rng.dirichlet(np.ones(5), size=5)
        state = BeliefState(t=0, B=np.zeros((5, 8)), W=W, timestamp=datetime.now())
        assert state.lambda_max() <= 1.0 + 1e-10

    def test_variance(self):
        """全零矩陣的 variance 應為 0。"""
        state = BeliefState(
            t=0,
            B=np.zeros((3, 8)),
            W=np.eye(3),
            timestamp=datetime.now(),
        )
        assert state.variance() == 0.0

    def test_properties(self):
        state = BeliefState(
            t=0,
            B=np.zeros((5, 8)),
            W=np.eye(5),
            timestamp=datetime.now(),
        )
        assert state.n_agents == 5
        assert state.n_dims == 8
