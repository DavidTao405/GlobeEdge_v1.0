"""Flask 應用工廠。"""

import os

from dotenv import load_dotenv
from flask import Flask

from worldedge.db import db


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "WE_DB_URL", "postgresql://postgres:password@localhost:5432/worldedge"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # 註冊 blueprints
    from worldedge.api import agents, projects, simulations

    app.register_blueprint(projects.bp)
    app.register_blueprint(simulations.bp)
    app.register_blueprint(agents.bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
