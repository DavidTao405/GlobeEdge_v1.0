"""Projects CRUD API。"""

from flask import Blueprint, jsonify, request

from globeedge.db import db
from globeedge.models import Project

bp = Blueprint("projects", __name__, url_prefix="/api/projects")

PROJECT_FIELDS = ("name", "description", "alpha", "mc_runs", "noise_level",
                  "sim_horizon", "time_step", "status")


def _serialize(p: Project) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "alpha": p.alpha,
        "mc_runs": p.mc_runs,
        "noise_level": p.noise_level,
        "sim_horizon": p.sim_horizon,
        "time_step": p.time_step,
        "status": p.status,
        "created_at": p.created_at.isoformat(),
    }


@bp.post("")
def create_project():
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify(error="name is required"), 400
    proj = Project(**{k: data[k] for k in PROJECT_FIELDS if k in data})
    db.session.add(proj)
    db.session.commit()
    return jsonify(_serialize(proj)), 201


@bp.get("")
def list_projects():
    projects = Project.query.filter(Project.status != "archived").all()
    return jsonify([_serialize(p) for p in projects])


@bp.get("/<uuid:project_id>")
def get_project(project_id):
    proj = db.session.get(Project, project_id)
    if not proj:
        return jsonify(error="not found"), 404
    return jsonify(_serialize(proj))


@bp.patch("/<uuid:project_id>")
def update_project(project_id):
    proj = db.session.get(Project, project_id)
    if not proj:
        return jsonify(error="not found"), 404
    data = request.get_json(force=True)
    for field in PROJECT_FIELDS:
        if field in data:
            setattr(proj, field, data[field])
    db.session.commit()
    return jsonify(_serialize(proj))


@bp.delete("/<uuid:project_id>")
def delete_project(project_id):
    """軟刪除：status → archived。"""
    proj = db.session.get(Project, project_id)
    if not proj:
        return jsonify(error="not found"), 404
    proj.status = "archived"
    db.session.commit()
    return "", 204
