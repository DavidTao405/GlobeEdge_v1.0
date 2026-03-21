"""Simulations API — 仿真佇列管理。"""

import json
import logging
import os

import redis as redis_lib
from flask import Blueprint, jsonify, request

from globeedge.db import db
from globeedge.models import Project, SimulationResult

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
