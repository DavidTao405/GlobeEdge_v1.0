"""Flask 應用工廠。"""

import os

from dotenv import load_dotenv
from flask import Flask

from globeedge.db import db


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "WE_DB_URL", "postgresql://postgres:password@localhost:5432/globeedge"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # 註冊 blueprints
    from globeedge.api import agents, projects, simulations

    app.register_blueprint(projects.bp)
    app.register_blueprint(simulations.bp)
    app.register_blueprint(agents.bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
