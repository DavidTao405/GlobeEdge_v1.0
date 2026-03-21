"""Phase 7 校準腳本 — Granger Causality 反推歷史 W 矩陣。

用法:
    python scripts/calibrate.py --event hualien_earthquake --period 2024-04
    python scripts/calibrate.py --event pelosi_visit --period 2022-08
    python scripts/calibrate.py --list                # 列出所有歷史事件
    python scripts/calibrate.py --all                 # 全部事件校準

原理:
    1. 定義歷史事件的 Agent 與預期信念時序
    2. 用 Granger Causality Test 檢定 Agent 間的因果方向
    3. 校準結果回饋到 W 矩陣的 weight + confidence
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field

import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# ── 歷史事件定義 ─────────────────────────────────────────

@dataclass
class HistoricalEvent:
    """一個歷史事件的校準資料。"""
    id: str
    name: str
    period: str                     # YYYY-MM
    event_day: int                  # 事件在 horizon 中的發生日
    description: str
    agents: list[dict]              # [{"name", "type", "domain"}]
    belief_init: np.ndarray         # (n_agents, n_dims) 事件前信念
    belief_trajectory: np.ndarray   # (horizon+1, n_agents, n_dims) 實際演變
    impact_vector: np.ndarray       # (n_agents, n_dims) 事件衝擊
    expected_w_direction: dict = field(default_factory=dict)
    # {"媒體→民眾": "positive", "KOL→論壇": "positive"}


def _synthetic_trajectory(
    n_agents: int, n_dims: int, horizon: int,
    event_day: int, impact: np.ndarray,
    decay: float = 0.85, noise: float = 0.02,
    seed: int = 42,
) -> np.ndarray:
    """生成合成信念軌跡（基於衰減回歸模型）。

    事件前：穩定態 + 微噪聲
    事件後：衝擊 → 指數衰減 → 新穩態
    """
    rng = np.random.default_rng(seed)
    traj = np.zeros((horizon + 1, n_agents, n_dims))

    # 事件前：穩定態
    base = rng.uniform(-0.3, 0.3, (n_agents, n_dims))
    for t in range(event_day):
        traj[t] = base + rng.normal(0, noise, (n_agents, n_dims))

    # 事件當天：衝擊
    traj[event_day] = base + impact

    # 事件後：指數衰減
    for t in range(event_day + 1, horizon + 1):
        dt = t - event_day
        decay_factor = decay ** dt
        traj[t] = base + impact * decay_factor + rng.normal(0, noise, (n_agents, n_dims))

    return np.clip(traj, -1.0, 1.0)


# ── 三個歷史事件 ──────────────────────────────────────────

def _define_hualien_earthquake() -> HistoricalEvent:
    """2024-04 花蓮 M7.2 地震。

    信念動態：
    - 社會安全感急降 (dim 1)
    - 經濟焦慮升高 (dim 3)
    - 政策支持度（防災政策）先降後升 (dim 4)
    - 群體凝聚度短暫升高 (dim 6)
    """
    agents = [
        {"name": "主流媒體", "type": "media", "domain": "news"},
        {"name": "PTT鄉民", "type": "forum", "domain": "social"},
        {"name": "政府機構", "type": "institution", "domain": "government"},
        {"name": "救災KOL", "type": "kol", "domain": "social"},
        {"name": "一般民眾", "type": "demographic", "domain": "social"},
    ]
    n, d, h = 5, 8, 30
    event_day = 7  # 假設事件在第 7 天

    # 地震衝擊向量（每個 Agent 反應不同）
    impact = np.zeros((n, d))
    # dim1=安全感  dim3=經濟焦慮  dim4=政策支持  dim6=凝聚度
    impact[0] = [0, -0.4, 0, 0.3, -0.1, 0.2, 0.1, 0]     # 媒體：大幅報導
    impact[1] = [0, -0.6, 0, 0.5, -0.3, 0, 0.3, 0]        # PTT：強烈反應
    impact[2] = [0, -0.2, 0, 0.1, 0.3, 0, 0.2, 0]         # 政府：安撫
    impact[3] = [0, -0.5, 0, 0.2, -0.2, 0.3, 0.4, 0]      # KOL：動員救災
    impact[4] = [0, -0.7, 0, 0.6, -0.2, 0, 0.2, 0]        # 民眾：最受衝擊

    traj = _synthetic_trajectory(n, d, h, event_day, impact, decay=0.82, seed=42)

    return HistoricalEvent(
        id="hualien_earthquake",
        name="2024 花蓮 M7.2 地震",
        period="2024-04",
        event_day=event_day,
        description="M7.2 花蓮地震，造成重大傷亡，社會安全感急降",
        agents=agents,
        belief_init=traj[0],
        belief_trajectory=traj,
        impact_vector=impact,
        expected_w_direction={
            "主流媒體→一般民眾": "positive",
            "PTT鄉民→一般民眾": "positive",
            "政府機構→一般民眾": "positive",
            "救災KOL→PTT鄉民": "positive",
        },
    )


def _define_taiwan_election() -> HistoricalEvent:
    """2024-01 台灣總統大選。

    信念動態：
    - 政策支持度極化 (dim 4)
    - 身份認同對立加劇 (dim 2)
    - 媒體信任度下降 (dim 0)
    - 群體凝聚度下降（社會分裂）(dim 6)
    """
    agents = [
        {"name": "泛綠媒體", "type": "media", "domain": "news"},
        {"name": "泛藍媒體", "type": "media", "domain": "news"},
        {"name": "PTT政黑", "type": "forum", "domain": "social"},
        {"name": "KOL名嘴", "type": "kol", "domain": "social"},
        {"name": "選民", "type": "demographic", "domain": "social"},
    ]
    n, d, h = 5, 8, 30
    event_day = 15  # 選舉日

    impact = np.zeros((n, d))
    # dim0=媒體信任 dim2=身份認同 dim4=政策支持 dim6=凝聚度
    impact[0] = [-0.3, 0, 0.5, 0, 0.6, -0.2, -0.3, 0]    # 泛綠：勝選
    impact[1] = [-0.3, 0, -0.4, 0, -0.5, -0.2, -0.3, 0]   # 泛藍：敗選
    impact[2] = [-0.4, 0, 0.3, 0, 0.2, -0.3, -0.5, 0]     # PTT：激化
    impact[3] = [-0.5, 0, 0.2, 0, 0.1, -0.4, -0.4, 0]     # KOL：極化
    impact[4] = [-0.2, 0, 0.1, 0, 0.1, -0.1, -0.2, 0]     # 選民：溫和

    traj = _synthetic_trajectory(n, d, h, event_day, impact, decay=0.9, seed=123)

    return HistoricalEvent(
        id="taiwan_election",
        name="2024 台灣總統大選",
        period="2024-01",
        event_day=event_day,
        description="賴清德當選，三角督導致極化效應",
        agents=agents,
        belief_init=traj[0],
        belief_trajectory=traj,
        impact_vector=impact,
        expected_w_direction={
            "泛綠媒體→選民": "positive",
            "泛藍媒體→選民": "positive",
            "KOL名嘴→PTT政黑": "positive",
        },
    )


def _define_pelosi_visit() -> HistoricalEvent:
    """2022-08 裴洛西訪台。

    信念動態：
    - 外部威脅感知暴增 (dim 7)
    - 經濟焦慮升高 (dim 3)
    - 群體凝聚度先升後降 (dim 6)
    - 身份認同強化 (dim 2)
    """
    agents = [
        {"name": "國際媒體", "type": "media", "domain": "news"},
        {"name": "台灣媒體", "type": "media", "domain": "news"},
        {"name": "PTT八卦", "type": "forum", "domain": "social"},
        {"name": "軍事分析KOL", "type": "kol", "domain": "social"},
        {"name": "台灣民眾", "type": "demographic", "domain": "social"},
    ]
    n, d, h = 5, 8, 30
    event_day = 3  # 訪台很突然

    impact = np.zeros((n, d))
    # dim2=身份認同 dim3=經濟焦慮 dim6=凝聚度 dim7=外部威脅
    impact[0] = [0, 0, 0, 0.2, 0, 0, 0, 0.8]              # 國際媒體：外部威脅報導
    impact[1] = [0, 0, 0.3, 0.4, -0.2, 0, 0.3, 0.7]       # 台灣媒體：全面報導
    impact[2] = [0, 0, 0.4, 0.3, 0, 0, 0.5, 0.6]          # PTT：激動
    impact[3] = [0, 0, 0.2, 0.5, 0, 0.3, 0.1, 0.9]        # 軍事KOL：專業分析
    impact[4] = [0, -0.3, 0.2, 0.6, 0, 0, 0.2, 0.7]       # 民眾：焦慮+團結

    traj = _synthetic_trajectory(n, d, h, event_day, impact, decay=0.78, seed=456)

    return HistoricalEvent(
        id="pelosi_visit",
        name="2022 裴洛西訪台",
        period="2022-08",
        event_day=event_day,
        description="美國眾議院議長訪台引發台海軍事緊張",
        agents=agents,
        belief_init=traj[0],
        belief_trajectory=traj,
        impact_vector=impact,
        expected_w_direction={
            "國際媒體→台灣媒體": "positive",
            "台灣媒體→台灣民眾": "positive",
            "軍事分析KOL→PTT八卦": "positive",
        },
    )


EVENTS = {
    "hualien_earthquake": _define_hualien_earthquake,
    "taiwan_election": _define_taiwan_election,
    "pelosi_visit": _define_pelosi_visit,
}


# ── Granger Causality 分析 ────────────────────────────────

def granger_calibrate(event: HistoricalEvent, maxlag: int = 5) -> dict:
    """對歷史事件執行 Granger Causality 校準。

    Returns:
        {
            "edges": [{"source", "target", "p_value", "lag", "direction"}],
            "alpha_optimal": float,
            "summary": str,
        }
    """
    traj = event.belief_trajectory  # (horizon+1, n_agents, n_dims)
    n_agents = len(event.agents)
    agent_names = [a["name"] for a in event.agents]

    # 對每對 Agent 做 Granger test（在最受影響的維度上）
    edges = []
    for i in range(n_agents):
        for j in range(n_agents):
            if i == j:
                continue

            # 找最有變動的維度
            var_i = traj[:, i, :].var(axis=0)
            var_j = traj[:, j, :].var(axis=0)
            dim = int(np.argmax(var_i + var_j))

            series_i = traj[:, i, dim]
            series_j = traj[:, j, dim]

            # Granger test: j granger-causes i?
            data = np.column_stack([series_i, series_j])
            try:
                result = grangercausalitytests(data, maxlag=min(maxlag, len(data) // 3), verbose=False)
                # 取最小 p-value
                best_lag = min(result.keys(), key=lambda k: result[k][0]['ssr_ftest'][1])
                p_value = result[best_lag][0]['ssr_ftest'][1]

                if p_value < 0.1:  # 顯著性門檻
                    edges.append({
                        "source": agent_names[j],
                        "target": agent_names[i],
                        "p_value": round(p_value, 4),
                        "lag": best_lag,
                        "dimension": dim,
                        "direction": "positive" if np.corrcoef(series_i[best_lag:], series_j[:-best_lag or None])[0, 1] > 0 else "negative",
                    })
            except Exception as e:
                logger.debug("Granger test failed for %s→%s: %s", agent_names[j], agent_names[i], e)

    # 評估 alpha 最佳值：比較不同 alpha 下的預測誤差
    from worldedge.core import FJEngine, MonteCarloRunner

    best_alpha = 0.6
    best_error = float('inf')

    for alpha_test in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        engine = FJEngine(alpha=alpha_test, b0=event.belief_init)

        # 用校準出的 W 建立模型
        n = n_agents
        W_test = np.zeros((n, n))
        for e in edges:
            src_idx = agent_names.index(e["source"])
            tgt_idx = agent_names.index(e["target"])
            W_test[src_idx, tgt_idx] = max(0.1, 1 - e["p_value"])

        # 行和正規化
        row_sums = W_test.sum(axis=1, keepdims=True)
        mask = row_sums > 1
        W_test = np.where(mask, W_test / row_sums, W_test)

        runner = MonteCarloRunner(engine, n_runs=200, noise_level=0.05, seed=0,
                                  agent_types=[a["type"] for a in event.agents])
        events_dict = {event.event_day: event.impact_vector}
        dist = runner.run(event.belief_init, W_test, horizon=traj.shape[0] - 1, events=events_dict)

        pred_mean = dist.mean()
        error = float(np.mean((pred_mean - traj) ** 2))

        if error < best_error:
            best_error = error
            best_alpha = alpha_test

    summary = (
        f"Event: {event.name}\n"
        f"Period: {event.period}\n"
        f"Agents: {n_agents}\n"
        f"Significant edges (p < 0.1): {len(edges)}\n"
        f"Best alpha: {best_alpha}\n"
        f"MSE: {best_error:.6f}\n"
    )

    return {
        "event": event.id,
        "edges": edges,
        "alpha_optimal": best_alpha,
        "mse": best_error,
        "summary": summary,
    }


# ── 驗證 expected_w_direction ──────────────────────────────

def validate_directions(event: HistoricalEvent, calibrated_edges: list[dict]) -> list[dict]:
    """比對 Granger 結果與預期方向。"""
    results = []
    edge_lookup = {f"{e['source']}→{e['target']}": e for e in calibrated_edges}

    for expected_key, expected_dir in event.expected_w_direction.items():
        found = edge_lookup.get(expected_key)
        if found:
            match = found["direction"] == expected_dir
            results.append({
                "edge": expected_key,
                "expected": expected_dir,
                "actual": found["direction"],
                "p_value": found["p_value"],
                "match": match,
            })
        else:
            results.append({
                "edge": expected_key,
                "expected": expected_dir,
                "actual": "not_found",
                "p_value": None,
                "match": False,
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="WorldEdge Phase 7 校準")
    parser.add_argument("--event", type=str, help="事件 ID")
    parser.add_argument("--period", type=str, help="時間段 (YYYY-MM)")
    parser.add_argument("--list", action="store_true", help="列出所有事件")
    parser.add_argument("--all", action="store_true", help="全部校準")
    args = parser.parse_args()

    if args.list:
        for eid, factory in EVENTS.items():
            e = factory()
            print(f"  {eid:25s}  {e.name}  ({e.period})")
        return

    event_ids = list(EVENTS.keys()) if args.all else [args.event] if args.event else []
    if not event_ids:
        parser.print_help()
        return

    for eid in event_ids:
        if eid not in EVENTS:
            logger.error("Unknown event: %s", eid)
            continue

        event = EVENTS[eid]()
        logger.info("=" * 60)
        logger.info("Calibrating: %s (%s)", event.name, event.period)
        logger.info("=" * 60)

        result = granger_calibrate(event)

        print(f"\n{result['summary']}")

        print("Significant Granger edges:")
        for e in sorted(result["edges"], key=lambda x: x["p_value"]):
            print(f"  {e['source']:15s} → {e['target']:15s}  "
                  f"p={e['p_value']:.4f}  lag={e['lag']}  "
                  f"dir={e['direction']}  dim={e['dimension']}")

        # 方向驗證
        directions = validate_directions(event, result["edges"])
        print("\nDirection validation:")
        for d in directions:
            status = "✅" if d["match"] else "❌"
            print(f"  {status} {d['edge']:30s}  "
                  f"expected={d['expected']:8s}  actual={d['actual']:8s}  "
                  f"p={d['p_value']}")

        print()


if __name__ == "__main__":
    main()
