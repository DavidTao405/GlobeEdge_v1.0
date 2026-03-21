"""Celery task — 執行 Monte Carlo 仿真。

流程：
  1. 從 DB 讀取 project + agents + edges
  2. 組裝 B0, W0, agent_types
  3. 執行 MonteCarloRunner.run() (GPU 可用時自動切換)
  4. 結果寫入 SimulationResult (timesteps JSONB)
  5. 進度更新寫 Redis: simulation:{id}:status
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import numpy as np
import redis

from globeedge.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("WE_REDIS_URL", "redis://localhost:6379/0")
WE_DEVICE = os.environ.get("WE_DEVICE", "auto")


def _get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def _set_status(r: redis.Redis, sim_id: str, status: str, **extra):
    """寫入 Redis 狀態（TTL = 1 天）。"""
    payload = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
    payload.update(extra)
    r.setex(f"simulation:{sim_id}:status", 86400, json.dumps(payload))


def _assemble_state(project_id: str) -> tuple[np.ndarray, np.ndarray, list[str], int]:
    """從 DB 組裝 B0, W0, agent_types, n_dims。

    需在 Flask app context 中呼叫。
    """
    from globeedge.models import Agent, InfluenceEdge, IssueDimension

    agents = Agent.query.filter_by(project_id=project_id).order_by(Agent.created_at).all()
    if not agents:
        raise ValueError(f"Project {project_id} has no agents")

    n = len(agents)
    agent_id_to_idx = {a.id: i for i, a in enumerate(agents)}
    agent_types = [a.type or "default" for a in agents]

    # 維度數：從 issue_dimensions 查，預設 8
    dims = IssueDimension.query.filter(
        (IssueDimension.project_id == project_id)
        | (IssueDimension.project_id.is_(None))
    ).count()
    n_dims = dims if dims > 0 else 8

    # B0：agent.belief_init 或零向量
    B0 = np.zeros((n, n_dims))
    for i, a in enumerate(agents):
        if a.belief_init and len(a.belief_init) >= n_dims:
            B0[i] = np.array(a.belief_init[:n_dims])

    # W0：從 influence_edges 組裝（只取 valid_until IS NULL 的邊）
    W0 = np.zeros((n, n))
    edges = InfluenceEdge.query.filter_by(project_id=project_id).filter(
        InfluenceEdge.valid_until.is_(None)
    ).all()
    for e in edges:
        src_idx = agent_id_to_idx.get(e.source_id)
        tgt_idx = agent_id_to_idx.get(e.target_id)
        if src_idx is not None and tgt_idx is not None:
            W0[src_idx, tgt_idx] = e.weight

    # 行和正規化
    row_sums = W0.sum(axis=1, keepdims=True)
    mask = row_sums > 1
    W0 = np.where(mask, W0 / row_sums, W0)

    return B0, W0, agent_types, n_dims


def _detect_device() -> str:
    """偵測可用裝置。"""
    if WE_DEVICE != "auto":
        return WE_DEVICE
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


@celery_app.task(bind=True, name="globeedge.tasks.run_simulation")
def run_simulation(self, simulation_id: str):
    """主仿真 task。"""
    r = _get_redis()
    _set_status(r, simulation_id, "running", progress=0.0)

    try:
        # 需要 Flask app context 來存取 DB
        from globeedge.app import create_app
        app = create_app()

        with app.app_context():
            from globeedge.db import db
            from globeedge.models import Project, SimulationResult

            sim = db.session.get(SimulationResult, simulation_id)
            if not sim:
                raise ValueError(f"SimulationResult {simulation_id} not found")

            proj = db.session.get(Project, sim.project_id)
            if not proj:
                raise ValueError(f"Project {sim.project_id} not found")

            # 更新狀態
            sim.status = "running"
            db.session.commit()

            # 組裝狀態
            B0, W0, agent_types, n_dims = _assemble_state(str(proj.id))
            n_agents = B0.shape[0]

            mc_runs = sim.mc_runs_actual or proj.mc_runs
            horizon = proj.sim_horizon
            noise = proj.noise_level
            alpha = proj.alpha

            logger.info(
                "simulation %s: n=%d, d=%d, mc=%d, horizon=%d, alpha=%.2f",
                simulation_id, n_agents, n_dims, mc_runs, horizon, alpha,
            )

            _set_status(r, simulation_id, "running", progress=0.05,
                        detail="state assembled")

            # 建立 engine + runner
            from globeedge.core import FJEngine, MonteCarloRunner

            engine = FJEngine(alpha=alpha, b0=B0)
            runner = MonteCarloRunner(
                engine, n_runs=mc_runs, noise_level=noise,
                agent_types=agent_types,
            )

            # 執行仿真
            device = _detect_device()
            _set_status(r, simulation_id, "running", progress=0.1,
                        detail=f"starting MC on {device}")

            t_start = time.time()

            if device == "cuda":
                dist = runner.run_gpu(B0, W0, horizon)
            else:
                dist = runner.run(B0, W0, horizon)

            elapsed = time.time() - t_start

            _set_status(r, simulation_id, "running", progress=0.9,
                        detail="writing results")

            # 壓縮結果寫入 JSONB
            mean_traj = dist.mean()  # (horizon+1, n_agents, n_dims)
            lower, upper = dist.ci(0.95)
            var_over_time = dist.variance_over_time().tolist()
            lambda_max = dist.lambda_max_series(W0)

            timesteps_data = {
                "horizon": horizon,
                "n_agents": n_agents,
                "n_dims": n_dims,
                "mc_runs": mc_runs,
                "device": device,
                "mean": mean_traj.tolist(),
                "ci_lower": lower.tolist(),
                "ci_upper": upper.tolist(),
                "variance_over_time": var_over_time,
                "lambda_max": lambda_max,
                "final_mean": mean_traj[-1].tolist(),
            }

            sim.status = "done"
            sim.timesteps = timesteps_data
            sim.elapsed_sec = round(elapsed, 2)
            sim.mc_runs_actual = mc_runs
            db.session.commit()

            _set_status(r, simulation_id, "completed", progress=1.0,
                        elapsed_sec=round(elapsed, 2),
                        lambda_max=lambda_max)

            logger.info(
                "simulation %s: done in %.2fs (%s), lambda_max=%.4f",
                simulation_id, elapsed, device, lambda_max,
            )

    except Exception as exc:
        _set_status(r, simulation_id, "failed", error=str(exc))
        logger.exception("simulation %s failed", simulation_id)

        # 嘗試更新 DB 狀態
        try:
            from globeedge.app import create_app
            app = create_app()
            with app.app_context():
                from globeedge.db import db
                from globeedge.models import SimulationResult
                sim = db.session.get(SimulationResult, simulation_id)
                if sim:
                    sim.status = "failed"
                    db.session.commit()
        except Exception:
            pass

        raise self.retry(exc=exc, max_retries=1, countdown=30)
