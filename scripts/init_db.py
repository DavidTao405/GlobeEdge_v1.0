"""初始化資料庫 schema。

用法：
    python scripts/init_db.py          # 使用 .env 中的 WE_DB_URL
    python scripts/init_db.py --check  # 僅驗證 schema，不建立
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import inspect, text

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.db import db
from globeedge.models import (
    Agent,
    EWSAlert,
    ExternalEvent,
    InfluenceEdge,
    IssueDimension,
    Project,
    SimulationResult,
)

EXPECTED_TABLES = {
    "projects",
    "agents",
    "influence_edges",
    "issue_dimensions",
    "external_events",
    "simulation_results",
    "ews_alerts",
}


def create_app(db_url: str) -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def init_db(app: Flask) -> None:
    """建立所有表。"""
    with app.app_context():
        db.create_all()
        print("[OK] 所有表已建立。")


def check_schema(app: Flask) -> bool:
    """驗證 schema 是否正確。"""
    with app.app_context():
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        missing = EXPECTED_TABLES - existing
        if missing:
            print(f"[FAIL] 缺少表：{missing}")
            return False

        print(f"[OK] 所有 {len(EXPECTED_TABLES)} 張表存在：{sorted(EXPECTED_TABLES)}")

        # 驗證 influence_edges 部分索引
        edge_indexes = inspector.get_indexes("influence_edges")
        partial_found = any(
            idx.get("name") == "idx_edges_valid" for idx in edge_indexes
        )
        if partial_found:
            print("[OK] idx_edges_valid 部分索引存在")
        else:
            print("[WARN] idx_edges_valid 部分索引未找到（可能是資料庫不支援）")

        # 驗證 external_events.source_type 欄位
        ee_cols = {c["name"] for c in inspector.get_columns("external_events")}
        if "source_type" in ee_cols:
            print("[OK] external_events.source_type 欄位存在")
        else:
            print("[FAIL] external_events 缺少 source_type 欄位")
            return False

        # 驗證 simulation_results.timesteps 欄位
        sr_cols = {
            c["name"]: c["type"]
            for c in inspector.get_columns("simulation_results")
        }
        if "timesteps" in sr_cols:
            print(f"[OK] simulation_results.timesteps 欄位存在（{sr_cols['timesteps']}）")
        else:
            print("[FAIL] simulation_results 缺少 timesteps 欄位")
            return False

        # 驗證外鍵
        for table in ["agents", "influence_edges", "simulation_results", "ews_alerts"]:
            fks = inspector.get_foreign_keys(table)
            if fks:
                refs = [f"{fk['referred_table']}.{fk['referred_columns']}" for fk in fks]
                print(f"[OK] {table} 外鍵：{refs}")
            else:
                print(f"[WARN] {table} 沒有外鍵")

        return True


def main():
    parser = argparse.ArgumentParser(description="初始化 GlobeEdge 資料庫")
    parser.add_argument("--check", action="store_true", help="僅驗證 schema")
    args = parser.parse_args()

    load_dotenv()
    db_url = os.environ.get("WE_DB_URL")
    if not db_url:
        print("[ERROR] 未設定 WE_DB_URL 環境變數。請在 .env 中設定。")
        sys.exit(1)

    app = create_app(db_url)

    if args.check:
        ok = check_schema(app)
        sys.exit(0 if ok else 1)
    else:
        init_db(app)
        check_schema(app)


if __name__ == "__main__":
    main()
