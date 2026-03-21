"""Agents & Edges API。"""

import numpy as np
from flask import Blueprint, jsonify, request

from worldedge.db import db
from worldedge.models import Agent, InfluenceEdge

bp = Blueprint("agents", __name__, url_prefix="/api/agents")


def _serialize_agent(a: Agent) -> dict:
    return {
        "id": str(a.id),
        "project_id": str(a.project_id),
        "name": a.name,
        "type": a.type,
        "domain": a.domain,
        "belief_init": a.belief_init,
        "created_at": a.created_at.isoformat(),
    }


def _serialize_edge(e: InfluenceEdge) -> dict:
    return {
        "id": str(e.id),
        "project_id": str(e.project_id),
        "source_id": str(e.source_id),
        "target_id": str(e.target_id),
        "weight": e.weight,
        "weight_type": e.weight_type,
        "confidence": e.confidence,
        "decay_rate": e.decay_rate,
    }


@bp.post("")
def create_agent():
    data = request.get_json(force=True)
    for field in ("project_id", "name"):
        if not data.get(field):
            return jsonify(error=f"{field} is required"), 400
    agent = Agent(
        project_id=data["project_id"],
        name=data["name"],
        type=data.get("type"),
        domain=data.get("domain"),
        belief_init=data.get("belief_init"),
    )
    db.session.add(agent)
    db.session.commit()
    return jsonify(_serialize_agent(agent)), 201


@bp.get("/<uuid:agent_id>")
def get_agent(agent_id):
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify(error="not found"), 404
    return jsonify(_serialize_agent(agent))


@bp.post("/edges")
def create_edge():
    data = request.get_json(force=True)
    for field in ("project_id", "source_id", "target_id", "weight"):
        if field not in data:
            return jsonify(error=f"{field} is required"), 400
    edge = InfluenceEdge(
        project_id=data["project_id"],
        source_id=data["source_id"],
        target_id=data["target_id"],
        weight=data["weight"],
        weight_type=data.get("weight_type"),
        confidence=data.get("confidence", 0.5),
        decay_rate=data.get("decay_rate", 0.1),
    )
    db.session.add(edge)
    db.session.commit()
    return jsonify(_serialize_edge(edge)), 201


@bp.get("/edges/matrix")
def get_matrix():
    """回傳指定 project 的 W 矩陣（僅目前有效的邊）。"""
    project_id = request.args.get("project_id")
    if not project_id:
        return jsonify(error="project_id query param is required"), 400

    agents = Agent.query.filter_by(project_id=project_id).order_by(Agent.name).all()
    if not agents:
        return jsonify(error="no agents found"), 404

    id_to_idx = {str(a.id): i for i, a in enumerate(agents)}
    n = len(agents)
    W = np.zeros((n, n))

    edges = InfluenceEdge.query.filter_by(project_id=project_id).filter(
        InfluenceEdge.valid_until.is_(None)
    ).all()

    for e in edges:
        si = id_to_idx.get(str(e.source_id))
        ti = id_to_idx.get(str(e.target_id))
        if si is not None and ti is not None:
            W[si, ti] = e.weight

    return jsonify({
        "agents": [{"id": str(a.id), "name": a.name, "index": i}
                   for i, a in enumerate(agents)],
        "matrix": W.tolist(),
    })
