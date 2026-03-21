"""Simulations API — 仿真佇列管理 + What If 反事實分析。"""

import json
import logging
import os
import time

import numpy as np
import redis as redis_lib
from flask import Blueprint, jsonify, request

from globeedge.db import db
from globeedge.models import Agent, InfluenceEdge, Project, SimulationResult

logger = logging.getLogger(__name__)

bp = Blueprint("simulations", __name__, url_prefix="/api/simulations")

REDIS_URL = os.environ.get("WE_REDIS_URL", "redis://localhost:6379/0")


def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(REDIS_URL, decode_responses=True)


def _serialize(sim: SimulationResult) -> dict:
    return {
        "id": str(sim.id),
        "project_id": str(sim.project_id),
        "status": sim.status,
        "run_at": sim.run_at.isoformat(),
        "mc_runs_actual": sim.mc_runs_actual,
        "elapsed_sec": sim.elapsed_sec,
    }


@bp.post("")
def create_simulation():
    """建立仿真記錄 → 發送 Celery task。"""
    data = request.get_json(force=True)
    project_id = data.get("project_id")
    if not project_id:
        return jsonify(error="project_id is required"), 400
    proj = db.session.get(Project, project_id)
    if not proj:
        return jsonify(error="project not found"), 404

    sim = SimulationResult(
        project_id=proj.id,
        status="pending",
        mc_runs_actual=data.get("mc_runs", proj.mc_runs),
    )
    db.session.add(sim)
    db.session.commit()

    # 發送 Celery task
    try:
        from globeedge.tasks.simulation_task import run_simulation
        run_simulation.delay(str(sim.id))
        logger.info("simulation %s: task queued", sim.id)
    except Exception:
        logger.exception("failed to queue simulation task (Celery down?)")
        # Task 沒進 queue 但 DB 記錄已建立，允許手動重試

    return jsonify(_serialize(sim)), 201


@bp.get("/<uuid:sim_id>/status")
def get_status(sim_id):
    """Redis-first 查詢狀態：先查 Redis cache → miss 再查 DB。"""
    # Step 1: 先查 Redis
    try:
        r = _get_redis()
        cached = r.get(f"simulation:{sim_id}:status")
        if cached:
            data = json.loads(cached)
            data["id"] = str(sim_id)
            data["source"] = "redis"
            return jsonify(data)
    except Exception:
        logger.debug("Redis unavailable, falling back to DB")

    # Step 2: Redis miss → 查 DB
    sim = db.session.get(SimulationResult, sim_id)
    if not sim:
        return jsonify(error="not found"), 404
    return jsonify({
        "id": str(sim.id),
        "status": sim.status,
        "source": "db",
    })


@bp.get("/<uuid:sim_id>/result/summary")
def get_summary(sim_id):
    """取得仿真結果摘要。"""
    sim = db.session.get(SimulationResult, sim_id)
    if not sim:
        return jsonify(error="not found"), 404

    if sim.status != "done" or not sim.timesteps:
        return jsonify({
            "id": str(sim.id),
            "status": sim.status,
            "summary": None,
        })

    ts = sim.timesteps
    return jsonify({
        "id": str(sim.id),
        "status": sim.status,
        "elapsed_sec": sim.elapsed_sec,
        "summary": {
            "horizon": ts.get("horizon"),
            "n_agents": ts.get("n_agents"),
            "n_dims": ts.get("n_dims"),
            "mc_runs": ts.get("mc_runs"),
            "device": ts.get("device"),
            "lambda_max": ts.get("lambda_max"),
            "final_mean": ts.get("final_mean"),
            "variance_over_time": ts.get("variance_over_time"),
        },
    })


@bp.post("/<uuid:sim_id>/whatif")
def run_whatif(sim_id):
    """What If 反事實分析。

    從基準 simulation 取得 project 設定，
    套用 Intervention，重跑 MC，回傳對比結果。
    """
    from globeedge.core import (
        FJEngine, InterventionEngine, Intervention,
        MonteCarloRunner, MoEEWSMonitor, compute_whatif_diff,
    )

    # 取得基準仿真
    baseline_sim = db.session.get(SimulationResult, sim_id)
    if not baseline_sim:
        return jsonify(error="baseline simulation not found"), 404

    proj = db.session.get(Project, baseline_sim.project_id)
    if not proj:
        return jsonify(error="project not found"), 404

    data = request.get_json(force=True)
    interventions_raw = data.get("interventions", [])
    if not interventions_raw:
        return jsonify(error="interventions array is required"), 400

    # 組裝 agents, W, B0
    agents = Agent.query.filter_by(project_id=proj.id).order_by(Agent.name).all()
    if not agents:
        return jsonify(error="no agents in project"), 400

    n = len(agents)
    agent_names = [a.name for a in agents]
    agent_types = [a.type or "default" for a in agents]

    # B0
    B0 = np.zeros((n, 8))
    for i, a in enumerate(agents):
        if a.belief_init:
            B0[i] = (a.belief_init + [0.0] * 8)[:8]

    # W
    W = np.zeros((n, n))
    id_to_idx = {str(a.id): i for i, a in enumerate(agents)}
    edges = InfluenceEdge.query.filter_by(project_id=proj.id).filter(
        InfluenceEdge.valid_until.is_(None)
    ).all()
    for e in edges:
        si = id_to_idx.get(str(e.source_id))
        ti = id_to_idx.get(str(e.target_id))
        if si is not None and ti is not None:
            W[si, ti] = e.weight

    # 如果沒有邊，用預設 W
    if W.sum() == 0:
        W = np.full((n, n), 0.05)
        np.fill_diagonal(W, 0)
        row_sums = W.sum(axis=1, keepdims=True)
        W = np.where(row_sums > 1, W / row_sums, W)

    # Events（暫時為空，未來可從 DB 載入）
    events_dict: dict[int, np.ndarray] = {}

    # 解析 Intervention
    interventions = []
    for iv_raw in interventions_raw:
        # target 可以是 agent name 或 index
        target = iv_raw.get("target", "")
        # 如果 target 是 UUID，轉成 index
        if target in id_to_idx:
            target = id_to_idx[target]
        interventions.append(Intervention(
            type=iv_raw["type"],
            target=target,
            params=iv_raw.get("params", {}),
            description=iv_raw.get("description", ""),
        ))

    # 套用介入
    engine_iv = InterventionEngine()
    result_iv = engine_iv.apply(B0, W, events_dict, interventions, agent_names)

    # 跑基準仿真
    horizon = proj.sim_horizon or 30
    mc_runs = min(proj.mc_runs or 2000, 2000)
    seed = 42

    fj = FJEngine(alpha=proj.alpha or 0.3, b0=B0)
    runner = MonteCarloRunner(fj, n_runs=mc_runs, noise_level=proj.noise_level or 0.05,
                              seed=seed, agent_types=agent_types)

    t0 = time.time()
    dist_baseline = runner.run(B0, W, horizon=horizon, events=events_dict)
    baseline_lambda = dist_baseline.lambda_max_series(W)

    # 跑 What If 仿真（同 seed）
    fj_wi = FJEngine(alpha=proj.alpha or 0.3, b0=result_iv.B0)
    runner_wi = MonteCarloRunner(fj_wi, n_runs=mc_runs, noise_level=proj.noise_level or 0.05,
                                 seed=seed, agent_types=agent_types)
    dist_whatif = runner_wi.run(result_iv.B0, result_iv.W, horizon=horizon, events=result_iv.events)
    whatif_lambda = dist_whatif.lambda_max_series(result_iv.W)
    elapsed = time.time() - t0

    # 計算差異
    diff = compute_whatif_diff(
        dist_baseline.mean(), dist_whatif.mean(),
        baseline_lambda, whatif_lambda,
    )

    # EWS 對比
    monitor_b = MoEEWSMonitor()
    monitor_w = MoEEWSMonitor()
    baseline_alerts = []
    whatif_alerts = []
    baseline_variance = []
    whatif_variance = []

    for t in range(horizon + 1):
        bv = float(dist_baseline.trajectories[:, t, :, :].var())
        wv = float(dist_whatif.trajectories[:, t, :, :].var())
        baseline_variance.append(round(bv, 6))
        whatif_variance.append(round(wv, 6))

        ba = monitor_b.update({"lambda_max": baseline_lambda, "variance": bv})
        wa = monitor_w.update({"lambda_max": whatif_lambda, "variance": wv})
        if ba:
            baseline_alerts.extend([{"t": t, "severity": a.severity, "expert": a.expert} for a in ba])
        if wa:
            whatif_alerts.extend([{"t": t, "severity": a.severity, "expert": a.expert} for a in wa])

    # 儲存 What If 結果到 DB
    whatif_sim = SimulationResult(
        project_id=proj.id,
        status="done",
        mc_runs_actual=mc_runs,
        elapsed_sec=round(elapsed, 2),
        timesteps={
            "type": "whatif",
            "baseline_id": str(sim_id),
            "interventions": [iv.description or iv.type for iv in interventions],
            "horizon": horizon,
            "n_agents": n,
            "n_dims": 8,
            "mc_runs": mc_runs,
            "lambda_max": round(whatif_lambda, 4),
            "final_mean": dist_whatif.mean()[-1].tolist(),
            "variance_over_time": whatif_variance,
        },
    )
    db.session.add(whatif_sim)
    db.session.commit()

    return jsonify({
        "whatif_simulation_id": str(whatif_sim.id),
        "baseline_simulation_id": str(sim_id),
        "elapsed_sec": round(elapsed, 2),
        "interventions_applied": result_iv.applied,
        "diff": diff,
        "baseline": {
            "lambda_max": round(baseline_lambda, 4),
            "variance_over_time": baseline_variance,
            "alerts": baseline_alerts,
            "final_mean": dist_baseline.mean()[-1].tolist(),
        },
        "whatif": {
            "lambda_max": round(whatif_lambda, 4),
            "variance_over_time": whatif_variance,
            "alerts": whatif_alerts,
            "final_mean": dist_whatif.mean()[-1].tolist(),
        },
    })
