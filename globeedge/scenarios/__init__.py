"""GlobeEdge 議題情境模組。"""

from . import ai_regulation, energy, geopolitics, iran_war, recall, trade_war
from .base import Scenario

SCENARIOS = {
    # 即時驗證（2026 進行中）
    "iran_war": iran_war.build,
    "recall": recall.build,
    # 歷史 Backtest（已完成基礎版）
    "energy_policy": energy.build,
    "ai_regulation": ai_regulation.build,
    "geopolitics": geopolitics.build,
    "trade_war": trade_war.build,
}


def get_scenario(scenario_id: str) -> Scenario:
    """取得情境。"""
    factory = SCENARIOS.get(scenario_id)
    if not factory:
        raise ValueError(f"Unknown scenario: {scenario_id}. Available: {list(SCENARIOS.keys())}")
    return factory()


def list_scenarios() -> list[str]:
    """列出所有情境 ID。"""
    return list(SCENARIOS.keys())


__all__ = ["Scenario", "get_scenario", "list_scenarios", "SCENARIOS"]
