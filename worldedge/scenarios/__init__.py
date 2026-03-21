"""WorldEdge 議題情境模組。"""

from . import ai_regulation, energy, geopolitics, trade_war
from .base import Scenario

SCENARIOS = {
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
