"""執行議題情境仿真 — 完整 pipeline。

用法:
    python scripts/run_scenario.py --scenario energy_policy
    python scripts/run_scenario.py --scenario ai_regulation --event 1
    python scripts/run_scenario.py --list
    python scripts/run_scenario.py --all
    python scripts/run_scenario.py --scenario energy_policy --events 0,1,2

流程:
    1. 載入 Scenario 定義
    2. 建立 B0, W0
    3. 對每個 ExternalEvent 執行 Monte Carlo 仿真
    4. EWS 分析
    5. 輸出結果報告
"""

import argparse
import logging
import sys
import time

import numpy as np

sys.path.insert(0, ".")

from worldedge.core import FJEngine, MonteCarloRunner, MoEEWSMonitor, SimulationDistribution
from worldedge.scenarios import get_scenario, list_scenarios
from worldedge.scenarios.base import Scenario

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_simulation(scenario: Scenario, event_indices: list[int] | None = None) -> dict:
    """對情境執行完整仿真。"""
    B0 = scenario.belief_matrix()
    W0 = scenario.default_W()
    agent_types = scenario.agent_types()
    horizon = scenario.sim_horizon

    engine = FJEngine(alpha=scenario.alpha, b0=B0)
    runner = MonteCarloRunner(
        engine, n_runs=min(scenario.mc_runs, 2000),  # 限制 CLI 速度
        noise_level=scenario.noise_level,
        seed=42,
        agent_types=agent_types,
    )

    # 決定要注入哪些事件
    if event_indices is None:
        event_indices = list(range(len(scenario.events)))

    events_dict = {}
    for i, idx in enumerate(event_indices):
        event = scenario.events[idx]
        # 每個事件間隔 5 步注入
        t_inject = 5 + i * 7
        if t_inject >= horizon:
            t_inject = min(5 + i * 3, horizon - 1)
        impact = np.array(event.impact_vector)
        # 擴展到所有 agent（每個 agent 接收相同的衝擊）
        impact_matrix = np.tile(impact, (scenario.n_agents, 1))
        events_dict[t_inject] = impact_matrix

    # 執行仿真
    t0 = time.time()
    dist = runner.run(B0, W0, horizon=horizon, events=events_dict)
    elapsed = time.time() - t0

    # EWS 分析
    monitor = MoEEWSMonitor()
    lambda_max = dist.lambda_max_series(W0)

    variance_series = []
    all_alerts = []
    for t in range(horizon + 1):
        step_var = float(dist.trajectories[:, t, :, :].var())
        variance_series.append(step_var)
        alerts = monitor.update({
            "lambda_max": lambda_max,
            "variance": step_var,
        })
        if alerts:
            for a in alerts:
                all_alerts.append({"t": t, "alert": a})

    return {
        "scenario": scenario,
        "distribution": dist,
        "elapsed": elapsed,
        "lambda_max": lambda_max,
        "variance_series": variance_series,
        "alerts": all_alerts,
        "event_indices": event_indices,
        "events_dict": events_dict,
    }


def print_report(result: dict):
    """輸出仿真報告。"""
    sc = result["scenario"]
    dist = result["distribution"]
    horizon = sc.sim_horizon

    print(sc.summary())
    print(f"\n{'─'*60}")
    print(f"  SIMULATION RESULTS")
    print(f"{'─'*60}")
    print(f"  MC runs:     {dist.trajectories.shape[0]}")
    print(f"  Elapsed:     {result['elapsed']:.2f}s")
    print(f"  Lambda_max:  {result['lambda_max']:.4f}")

    # Event timeline
    print(f"\n  Event injection timeline:")
    for t, impact in sorted(result["events_dict"].items()):
        idx = list(result["events_dict"].keys()).index(t)
        if idx < len(result["event_indices"]):
            eidx = result["event_indices"][idx]
            ev = sc.events[eidx]
            print(f"    t={t:2d}  {ev.title}")

    # EWS Alerts
    print(f"\n  EWS Alerts: {len(result['alerts'])}")
    for entry in result["alerts"]:
        a = entry["alert"]
        print(f"    t={entry['t']:2d}  [{a.expert}] {a.alert_type} "
              f"z={a.z_score:+.2f} severity={a.severity}")

    # Belief evolution summary
    mean_traj = dist.mean()  # (horizon+1, n_agents, n_dims)
    print(f"\n  Belief evolution (mean across runs):")
    print(f"  {'Agent':20s}  {'t=0':>10s}  {'t=final':>10s}  {'Δ':>10s}  max_dim")
    for i, agent in enumerate(sc.agents):
        b0 = mean_traj[0, i, :]
        bf = mean_traj[-1, i, :]
        delta = bf - b0
        max_dim = int(np.argmax(np.abs(delta)))
        dim_label = sc.dimensions[max_dim].label
        print(f"  {agent.name:20s}  {b0.mean():+.4f}  {bf.mean():+.4f}  "
              f"{delta.mean():+.4f}  dim{max_dim}({dim_label})")

    # Polarization check
    print(f"\n  Polarization analysis:")
    final_beliefs = mean_traj[-1]  # (n_agents, n_dims)
    for d_idx, dim in enumerate(sc.dimensions):
        vals = final_beliefs[:, d_idx]
        spread = vals.max() - vals.min()
        std = vals.std()
        if spread > 0.3:
            agents_high = [sc.agents[i].name for i in range(sc.n_agents) if vals[i] > vals.mean() + std]
            agents_low = [sc.agents[i].name for i in range(sc.n_agents) if vals[i] < vals.mean() - std]
            print(f"    dim{d_idx} {dim.label:15s}  spread={spread:.3f}  "
                  f"high={agents_high}  low={agents_low}")

    # Variance timeline
    vs = result["variance_series"]
    event_times = set(result["events_dict"].keys())
    print(f"\n  Variance timeline:")
    for t, v in enumerate(vs):
        if t % 5 == 0 or t in event_times or t == len(vs) - 1:
            bar = "█" * int(v * 300)
            marker = " ←EVENT" if t in event_times else ""
            print(f"    t={t:2d}  {v:.5f}  {bar}{marker}")

    # Expected findings check
    print(f"\n  Expected findings:")
    for i, finding in enumerate(sc.expected_findings):
        print(f"    [{i+1}] {finding}")


def main():
    parser = argparse.ArgumentParser(description="WorldEdge 議題情境仿真")
    parser.add_argument("--scenario", type=str, help="情境 ID")
    parser.add_argument("--event", type=int, help="只注入特定事件 (index)")
    parser.add_argument("--events", type=str, help="注入多個事件 (逗號分隔)")
    parser.add_argument("--list", action="store_true", help="列出所有情境")
    parser.add_argument("--all", action="store_true", help="全部情境")
    args = parser.parse_args()

    if args.list:
        for sid in list_scenarios():
            sc = get_scenario(sid)
            print(f"  {sid:20s}  {sc.name}  ({sc.n_agents} agents, {len(sc.events)} events)")
        return

    scenario_ids = list_scenarios() if args.all else [args.scenario] if args.scenario else []
    if not scenario_ids:
        parser.print_help()
        return

    for sid in scenario_ids:
        sc = get_scenario(sid)

        event_indices = None
        if args.event is not None:
            event_indices = [args.event]
        elif args.events:
            event_indices = [int(x) for x in args.events.split(",")]

        result = run_simulation(sc, event_indices)
        print_report(result)
        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
