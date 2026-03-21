"""Simulations API。"""

from flask import Blueprint, jsonify, request

from worldedge.db import db
from worldedge.models import Project, SimulationResult

bp = Blueprint("simulations", __name__, url_prefix="/api/simulations")


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
    return jsonify(_serialize(sim)), 201


@bp.get("/<uuid:sim_id>/status")
def get_status(sim_id):
    # TODO: Phase 5 — 先查 Redis 再查 DB（Celery 接上後改為 Redis-first）
    sim = db.session.get(SimulationResult, sim_id)
    if not sim:
        return jsonify(error="not found"), 404
    return jsonify({"id": str(sim.id), "status": sim.status})


@bp.get("/<uuid:sim_id>/result/summary")
def get_summary(sim_id):
    sim = db.session.get(SimulationResult, sim_id)
    if not sim:
        return jsonify(error="not found"), 404
    # Mock summary — Phase 4 接上真實仿真後替換
    return jsonify({
        "id": str(sim.id),
        "status": sim.status,
        "summary": {
            "mean_belief": [0.12, -0.34, 0.56],
            "std_belief": [0.05, 0.08, 0.03],
            "convergence_step": 18,
            "lambda_max": 0.92,
            "ews_triggered": False,
        },
    })
