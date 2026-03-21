"""啟動 GlobeEdge Flask API 服務。

用法：python scripts/start_api.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FLASK_DEBUG", "0")

from globeedge.app import create_app

app = create_app()

if __name__ == "__main__":
    print("[GlobeEdge] Starting API on http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
