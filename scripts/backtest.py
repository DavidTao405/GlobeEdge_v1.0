"""Phase 7 Backtest — EWS 在歷史事件前是否出現預警信號？

用法:
    python scripts/backtest.py --event hualien_earthquake
    python scripts/backtest.py --all
    python scripts/backtest.py --event pelosi_visit --verbose

原理:
    1. 用歷史事件的合成軌跡模擬 FJ 動態
    2. 餵入 EWSMonitor，記錄每一步的 lambda_max / variance / z-score
    3. 檢查事件發生前 7 天是否有 EWS 觸發
    4. 計算 AUC (Area Under Curve) 評估預警品質
"""

import argparse
import logging
import sys

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Import from calibrate.py's event definitions
sys.path.insert(0, ".")
from scripts.calibrate import EVENTS, HistoricalEvent


def run_backtest(event: HistoricalEvent, verbose: bool = False) -> dict:
    """對歷史事件執行 EWS backtest。

    Returns:
        {
            "event": str,
            "pre_event_alerts": int,
            "post_event_alerts": int,
            "lead_time": int,        # 事件前最早預警距離事件幾步
            "lambda_max_series": [...],
            "variance_series": [...],
            "z_scores": [...],
            "auc": float,            # 預警品質
            "significance": str,     # significant | marginal | none
        }
    """
    from globeedge.core import FJEngine, MonteCarloRunner, MoEEWSMonitor

    traj = event.belief_trajectory  # (horizon+1, n_agents, n_dims)
    n_agents = len(event.agents)
    horizon = traj.shape[0] - 1
    agent_types = [a["type"] for a in event.agents]

    # 建立 W 矩陣（簡單均勻）
    W = np.full((n_agents, n_agents), 0.15)
    np.fill_diagonal(W, 0)
    row_sums = W.sum(axis=1, keepdims=True)
    W = W / np.maximum(row_sums, 1.0)

    # 建立 engine
    engine = FJEngine(alpha=0.6, b0=traj[0])
    runner = MonteCarloRunner(
        engine, n_runs=500, noise_level=0.05, seed=42,
        agent_types=agent_types,
    )

    # 執行仿真
    events_dict = {event.event_day: event.impact_vector}
    dist = runner.run(traj[0], W, horizon=horizon, events=events_dict)

    # 計算 EWS 指標
    monitor = MoEEWSMonitor()
    lambda_max_val = dist.lambda_max_series(W)

    lambda_series = []
    variance_series = []
    z_scores = []
    alerts_by_step = []

    for t in range(horizon + 1):
        # 信念變異數（跨 run）
        step_var = float(dist.trajectories[:, t, :, :].var())
        variance_series.append(step_var)
        lambda_series.append(lambda_max_val)  # 靜態 W，lambda 不變

        # 餵 EWSMonitor
        metrics = {
            "lambda_max": lambda_max_val,
            "variance": step_var,
        }
        alerts = monitor.update(metrics)
        alerts_by_step.append(alerts)
        z_scores.append(monitor.experts["belief"]._mean.get("variance", 0))

        if verbose and alerts:
            for a in alerts:
                marker = "⚠️" if t < event.event_day else "📍"
                print(f"  t={t:2d} {marker} [{a.expert}] {a.alert_type} "
                      f"z={a.z_score:+.2f} severity={a.severity}")

    # 分析預警品質
    pre_event_alerts = sum(
        len(a) for t, a in enumerate(alerts_by_step) if t < event.event_day
    )
    post_event_alerts = sum(
        len(a) for t, a in enumerate(alerts_by_step) if t >= event.event_day
    )

    # Lead time: 事件前最早預警
    lead_time = 0
    for t in range(event.event_day - 1, -1, -1):
        if alerts_by_step[t]:
            lead_time = event.event_day - t
            break

    # AUC: 用 variance 的累積異常面積
    # 事件前 variance 相對於 baseline 的 z-score 累積
    if len(variance_series) > event.event_day:
        pre_start = max(1, event.event_day // 4)  # skip t=0 (initial noise spike)
        pre_slice = variance_series[pre_start:max(pre_start + 1, event.event_day)]
        pre_baseline = np.mean(pre_slice) if pre_slice else 0.01
        pre_std = max(np.std(pre_slice) if len(pre_slice) > 1 else pre_baseline * 0.1, 1e-4)
        auc = 0.0
        for t in range(event.event_day, min(event.event_day + 7, len(variance_series))):
            z = (variance_series[t] - pre_baseline) / pre_std
            auc += max(0, z)
        auc = round(auc, 3)
    else:
        auc = 0.0

    # 判定顯著性
    if pre_event_alerts >= 2 or auc > 5.0:
        significance = "significant"
    elif pre_event_alerts >= 1 or auc > 2.0:
        significance = "marginal"
    else:
        significance = "none"

    return {
        "event": event.id,
        "event_name": event.name,
        "event_day": event.event_day,
        "horizon": horizon,
        "pre_event_alerts": pre_event_alerts,
        "post_event_alerts": post_event_alerts,
        "lead_time": lead_time,
        "lambda_max": lambda_max_val,
        "variance_series": variance_series,
        "auc": auc,
        "significance": significance,
    }


def print_report(result: dict):
    """印出 backtest 報告。"""
    sig_icon = {"significant": "✅", "marginal": "⚠️", "none": "❌"}
    icon = sig_icon.get(result["significance"], "?")

    print(f"\n{'='*60}")
    print(f"  {result['event_name']}  ({result['event']})")
    print(f"{'='*60}")
    print(f"  Event day:          t={result['event_day']} / {result['horizon']}")
    print(f"  Pre-event alerts:   {result['pre_event_alerts']}")
    print(f"  Post-event alerts:  {result['post_event_alerts']}")
    print(f"  Lead time:          {result['lead_time']} steps before event")
    print(f"  AUC (variance):     {result['auc']}")
    print(f"  Lambda_max:         {result['lambda_max']:.4f}")
    print(f"  Significance:       {icon} {result['significance']}")

    # Variance timeline
    vs = result["variance_series"]
    ed = result["event_day"]
    print(f"\n  Variance timeline (event at t={ed}):")
    for t, v in enumerate(vs):
        bar = "█" * int(v * 500)
        marker = " ←EVENT" if t == ed else ""
        if t <= ed + 3 or t == len(vs) - 1 or t % 5 == 0:
            print(f"    t={t:2d}  {v:.5f}  {bar}{marker}")


def main():
    parser = argparse.ArgumentParser(description="GlobeEdge EWS Backtest")
    parser.add_argument("--event", type=str, help="事件 ID")
    parser.add_argument("--all", action="store_true", help="全部 backtest")
    parser.add_argument("--verbose", action="store_true", help="詳細輸出每步 alert")
    args = parser.parse_args()

    event_ids = list(EVENTS.keys()) if args.all else [args.event] if args.event else []
    if not event_ids:
        parser.print_help()
        return

    results = []
    for eid in event_ids:
        if eid not in EVENTS:
            logger.error("Unknown event: %s", eid)
            continue

        event = EVENTS[eid]()
        result = run_backtest(event, verbose=args.verbose)
        print_report(result)
        results.append(result)

    # Summary
    if len(results) > 1:
        print(f"\n{'='*60}")
        print("  SUMMARY")
        print(f"{'='*60}")
        for r in results:
            sig_icon = {"significant": "✅", "marginal": "⚠️", "none": "❌"}
            print(f"  {sig_icon[r['significance']]} {r['event_name']:25s}  "
                  f"pre={r['pre_event_alerts']}  post={r['post_event_alerts']}  "
                  f"lead={r['lead_time']}  AUC={r['auc']:.1f}  "
                  f"sig={r['significance']}")


if __name__ == "__main__":
    main()
