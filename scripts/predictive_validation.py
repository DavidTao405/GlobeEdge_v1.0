"""預測性驗證 — 用真實 PTT 資料比對 GlobeEdge 模型預測。

Layer 4 驗證：模型在已知事件下的輿論走向預測 vs 真實 PTT 推噓方向。

驗證時期：2026-03-26 到 2026-04-15（21 天）
真實事件：
    t=0   3/26  柯文哲京華城案一審判 17 年
    t=4   3/30  鄭習會宣布：鄭麗文 4/7 訪中
    t=15  4/10  鄭習會實際會面（習近平「一家人」）
    t=18  4/13  黃國昌開除李貞秀黨籍

資料源：PTT HatePolitics + Gossiping（4,570 篇）
驗證方法：
    1. 按日期 × 議題關鍵字聚合 PTT 推噓比
    2. push_ratio 轉換為信念方向訊號
    3. 比對 GlobeEdge 仿真的信念趨勢
    4. Q3: b(0) 隨機化敏感度分析
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.core import FJEngine, MonteCarloRunner
from globeedge.core.crisis_dynamics import CrisisAwareFJEngine, CrisisConfig
from globeedge.core.psychology import apply_forgetting, apply_motivated_reasoning

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── 驗證時期 ─────────────────────────────────────────────
START_DATE = datetime(2026, 3, 26)
END_DATE = datetime(2026, 4, 16)  # exclusive
HORIZON = (END_DATE - START_DATE).days - 1  # 20 天窗口 → 21 時步

# ── 真實事件時程 ─────────────────────────────────────────
# 每個 impact_vector 基於實際 PTT 推噓校準（geopolitics/recall scenario）
REAL_TIMELINE = [
    {"day": 0,  "date": "2026-03-26", "title": "柯文哲京華城一審 17 年",
     "impact": [0.15, 0.0, 0.05, 0.0, 0.0, 0.1, -0.05, 0.0]},
    {"day": 4,  "date": "2026-03-30", "title": "鄭習會宣布（爭議型）",
     "impact": [-0.05, -0.05, 0.0, 0.0, -0.1, 0.0, -0.1, -0.15]},
    {"day": 15, "date": "2026-04-10", "title": "鄭習會實際（噓率降溫）",
     "impact": [-0.03, -0.03, 0.0, 0.0, -0.05, 0.0, -0.05, -0.20]},
    {"day": 18, "date": "2026-04-13", "title": "李貞秀被開除黨籍",
     "impact": [-0.1, -0.05, -0.05, 0.0, 0.0, 0.1, -0.1, 0.0]},
]

# ── 議題關鍵字 → 維度對應 ──────────────────────────────────
# 每個維度關聯的 PTT 關鍵字（多個關鍵字 = 該維度的 proxy 訊號）
DIM_KEYWORDS = {
    0: {"name": "政府信任度",     "keywords": ["賴清德", "民進黨", "國民黨", "執政", "下台", "無能"]},
    1: {"name": "制度公信力",     "keywords": ["柯文哲", "京華城", "判決", "司法", "違憲"]},
    5: {"name": "政治改革意願",   "keywords": ["罷免", "民主", "改革", "青鳥"]},
    6: {"name": "群體凝聯度",     "keywords": ["黃國昌", "民眾黨", "李貞秀", "黨籍", "開除"]},
    7: {"name": "外部威脅感知",   "keywords": ["鄭習會", "鄭麗文", "習近平", "兩岸", "訪中"]},
}


# ── Step 1: 從 DB 讀真實 PTT 推噓 ─────────────────────────

def fetch_real_ptt_stance(
    dim_idx: int,
    keywords: list[str],
    exclude_urls: set[str] | None = None,
) -> dict[int, dict]:
    """查 DB，按日聚合關鍵字相關文章的推噓比。

    Args:
        exclude_urls: Hohwy 反串過濾後要排除的文章 URL 集合

    Returns:
        {day: {"articles": N, "push": X, "boo": Y, "arrow": Z, "push_ratio": R}}
    """
    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    if exclude_urls is None:
        exclude_urls = set()

    app = create_app()
    with app.app_context():
        # 用 OR 查所有關鍵字
        filters = [PttArticle.title.contains(kw) for kw in keywords]
        arts = PttArticle.query.filter(db.or_(*filters)).all()

        # 按實際發表日期分組（從 URL timestamp）
        by_day: dict[int, dict] = defaultdict(lambda: {
            "articles": 0, "push": 0, "boo": 0, "arrow": 0
        })
        for a in arts:
            if a.url in exclude_urls:
                continue
            m = re.search(r'M\.(\d+)\.A', a.url)
            if not m:
                continue
            dt = datetime.fromtimestamp(int(m.group(1)))
            if not (START_DATE <= dt < END_DATE):
                continue
            day = (dt.date() - START_DATE.date()).days
            by_day[day]["articles"] += 1
            by_day[day]["push"] += (a.push_count or 0)
            by_day[day]["boo"] += (a.boo_count or 0)
            by_day[day]["arrow"] += (a.arrow_count or 0)

    # 計算 push_ratio
    for day, stats in by_day.items():
        total_pb = stats["push"] + stats["boo"]
        stats["push_ratio"] = stats["push"] / total_pb if total_pb > 0 else 0.5
        stats["total_int"] = stats["push"] + stats["boo"] + stats["arrow"]
    return dict(by_day)


# ── Step 2: 推噓比 → 信念方向訊號 ─────────────────────────

def ptt_to_belief_signal(push_ratio: float, articles: int) -> float:
    """把推噓比轉成 [-1, +1] 的信念訊號。

    push_ratio 75%+ → 強烈正方向（議題被支持討論）
    push_ratio 50% 基準 → 中性
    push_ratio 25%- → 強烈負方向（被反對）

    低樣本量（< 3 篇）→ 回傳中性，避免雜訊
    """
    if articles < 3:
        return 0.0
    # 把 [0, 1] 映射到 [-1, +1]，0.5 為中性
    return (push_ratio - 0.5) * 2


def build_actual_series(
    horizon: int,
    exclude_urls: set[str] | None = None,
) -> dict[int, list[float]]:
    """建構每個維度每天的真實信念訊號時序。

    Args:
        exclude_urls: Hohwy 反串過濾後排除的文章 URL

    Returns:
        {dim_idx: [signal_t0, signal_t1, ...]}
    """
    result = {}
    for dim_idx, info in DIM_KEYWORDS.items():
        logger.info("  Fetching dim %d (%s): %s",
                    dim_idx, info["name"], info["keywords"])
        stance_by_day = fetch_real_ptt_stance(dim_idx, info["keywords"], exclude_urls)

        series = []
        for day in range(horizon + 1):
            stats = stance_by_day.get(day)
            if stats:
                signal = ptt_to_belief_signal(stats["push_ratio"], stats["articles"])
            else:
                signal = 0.0
            series.append(signal)
        result[dim_idx] = series
        n_days_with_data = sum(1 for s in series if s != 0.0)
        logger.info("    %d/%d days with data", n_days_with_data, horizon + 1)
    return result


# ── Step 3: GlobeEdge 預測 ────────────────────────────────

def run_globeedge_prediction(
    horizon: int = HORIZON,
    b0_override=None,
    engine_type: str = "crisis",
    crisis_decay: float = 0.05,
) -> np.ndarray:
    """跑 GlobeEdge 仿真，回傳 (horizon+1, n_agents, n_dims) 軌跡。

    Args:
        engine_type: "fj"（原始 FJ）或 "crisis"（CrisisAwareFJEngine）
        crisis_decay: CrisisAwareFJEngine 的衰退率（僅 engine_type="crisis" 有效）
    """
    from globeedge.scenarios.geopolitics import build as build_scenario
    scenario = build_scenario()
    B0 = scenario.belief_matrix() if b0_override is None else b0_override
    W = scenario.default_W()
    agent_types = scenario.agent_types()
    n_agents, n_dims = B0.shape
    alpha = scenario.alpha

    W_mod = apply_motivated_reasoning(W, B0)

    # 注入真實事件
    events = {}
    for evt in REAL_TIMELINE:
        if evt["day"] <= horizon:
            impact = np.tile(np.array(evt["impact"]), (n_agents, 1))
            events[evt["day"]] = impact

    if engine_type == "crisis":
        # CrisisAwareFJEngine 路徑
        from globeedge.core.belief_state import BeliefState
        from datetime import timezone
        config = CrisisConfig(
            alpha_base=alpha,
            alpha_crisis=0.6,
            crisis_decay=crisis_decay,
        )
        engine = CrisisAwareFJEngine(alpha=alpha, b0=B0, config=config)
        initial = BeliefState(
            t=0, B=B0.copy(), W=W_mod,
            timestamp=datetime.now(timezone.utc),
        )
        results = engine.run(initial, horizon=horizon, events=events)
        trajectory = [r.belief_state.B for r in results]
    else:
        # 原始 FJ 路徑（保留做對照組）
        trajectory = [B0.copy()]
        B = B0.copy()
        for t in range(horizon):
            B_next = alpha * W_mod @ B + (1 - alpha) * B0
            if t in events:
                B_next = B_next + events[t]
            B_next = np.clip(B_next, -1.0, 1.0)
            B_next = apply_forgetting(B_next, B0, agent_types)
            B_next = np.clip(B_next, -1.0, 1.0)
            B = B_next
            trajectory.append(B.copy())

    return np.array(trajectory)


# ── Step 4: 比對與指標計算 ────────────────────────────────

def signal_direction(x: float, threshold: float = 0.05) -> int:
    """訊號方向：+1 正向、-1 負向、0 中性。"""
    if x > threshold:
        return 1
    if x < -threshold:
        return -1
    return 0


def compute_direction_accuracy(predicted: list[float], actual: list[float]) -> dict:
    """方向準確率：計算預測方向與真實方向一致的比例。"""
    if len(predicted) != len(actual):
        raise ValueError("length mismatch")
    matched = 0
    valid = 0
    for p, a in zip(predicted, actual):
        if a == 0:
            continue  # 真實資料為空（中性）不計
        valid += 1
        if signal_direction(p) == signal_direction(a):
            matched += 1
    accuracy = matched / valid if valid > 0 else 0.0
    return {"valid_days": valid, "matched": matched, "accuracy": round(accuracy, 3)}


def pearson_correlation(a: list[float], b: list[float]) -> float:
    """Pearson 相關係數（容錯）。"""
    a, b = np.array(a), np.array(b)
    if np.std(a) < 1e-9 or np.std(b) < 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def compare(predicted_trajectory: np.ndarray, actual: dict[int, list[float]]) -> dict:
    """比對 GlobeEdge 預測 vs PTT 真實訊號。"""
    horizon = predicted_trajectory.shape[0] - 1
    dim_reports = {}

    for dim_idx, info in DIM_KEYWORDS.items():
        # 預測：取所有 Agent 的平均
        pred_series = [float(predicted_trajectory[t, :, dim_idx].mean())
                       for t in range(horizon + 1)]
        actual_series = actual[dim_idx]

        acc = compute_direction_accuracy(pred_series, actual_series)
        corr = pearson_correlation(pred_series, actual_series)

        # MSE
        mse = float(np.mean((np.array(pred_series) - np.array(actual_series)) ** 2))

        dim_reports[dim_idx] = {
            "name": info["name"],
            "direction_accuracy": acc["accuracy"],
            "valid_days": acc["valid_days"],
            "pearson_r": round(corr, 3),
            "mse": round(mse, 4),
            "pred_final": round(pred_series[-1], 3),
            "actual_final": round(actual_series[-1], 3),
        }

    # 整體 AUC（方向準確率平均）
    accs = [r["direction_accuracy"] for r in dim_reports.values() if r["valid_days"] > 0]
    overall_auc = float(np.mean(accs)) if accs else 0.0

    best = max(dim_reports.items(), key=lambda x: x[1]["direction_accuracy"])
    worst = min(dim_reports.items(), key=lambda x: x[1]["direction_accuracy"])

    return {
        "period": f"{START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}",
        "horizon": horizon,
        "dimensions": dim_reports,
        "overall_auc": round(overall_auc, 3),
        "best_dimension": best[1]["name"],
        "worst_dimension": worst[1]["name"],
    }


# ── Q3: b(0) 敏感度分析 ──────────────────────────────────

def sensitivity_b0(actual: dict, n_trials: int = 5, seed: int = 42) -> dict:
    """隨機化 b(0) 跑多次，看 AUC 變化幅度。

    baseline AUC vs 隨機 b(0) 的 AUC 分佈
    差距大 → b(0) 重要，差距小 → W 矩陣主導
    """
    from globeedge.scenarios.geopolitics import build as build_scenario
    scenario = build_scenario()
    original_B0 = scenario.belief_matrix()

    rng = np.random.default_rng(seed)
    aucs = []
    for i in range(n_trials):
        # 隨機 b(0)，保持 [-1, 1] 範圍
        random_B0 = rng.uniform(-0.5, 0.5, original_B0.shape)
        pred = run_globeedge_prediction(horizon=HORIZON, b0_override=random_B0)
        report = compare(pred, actual)
        aucs.append(report["overall_auc"])

    return {
        "n_trials": n_trials,
        "random_b0_aucs": [round(a, 3) for a in aucs],
        "mean_random_auc": round(float(np.mean(aucs)), 3),
        "std_random_auc": round(float(np.std(aucs)), 3),
        "max_random_auc": round(float(np.max(aucs)), 3),
        "min_random_auc": round(float(np.min(aucs)), 3),
    }


# ── Main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GlobeEdge 真實 PTT 預測驗證")
    parser.add_argument("--output", type=str, default="results/predictive_validation.json")
    parser.add_argument("--skip-q3", action="store_true", help="跳過 b(0) 敏感度")
    parser.add_argument("--engine", choices=["fj", "crisis"], default="crisis",
                        help="fj=原始 FJ, crisis=CrisisAwareFJEngine（預設）")
    parser.add_argument("--crisis-decay", type=float, default=0.05,
                        help="CrisisAwareFJEngine 危機衰退率（預設 0.05）")
    parser.add_argument("--hohwy-filter", type=str, default=None,
                        help="Hohwy 反串過濾 JSON 路徑（排除 sarcasm_urls）")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    logger.info("=" * 60)
    logger.info("  GlobeEdge 預測性驗證（真實 PTT 資料）")
    logger.info(f"  期間：{START_DATE.date()} 到 {END_DATE.date()}")
    logger.info(f"  Horizon: {HORIZON} 天")
    logger.info(f"  真實事件：{len(REAL_TIMELINE)}")
    logger.info(f"  Engine: {args.engine}  crisis_decay: {args.crisis_decay}")
    logger.info("=" * 60)

    # Hohwy 反串過濾
    exclude_urls = set()
    if args.hohwy_filter:
        with open(args.hohwy_filter, encoding="utf-8") as f:
            hohwy_data = json.load(f)
        exclude_urls = set(hohwy_data.get("sarcasm_urls", []))
        logger.info(f"  Hohwy 過濾：排除 {len(exclude_urls)} 篇高 PE 文章")

    # Step 1: 從 DB 讀真實訊號
    logger.info("\nStep 1: 從 DB 讀取真實 PTT 推噓訊號")
    actual = build_actual_series(horizon=HORIZON, exclude_urls=exclude_urls)

    # Step 2: GlobeEdge 預測
    engine_label = "CrisisAwareFJEngine" if args.engine == "crisis" else "FJEngine"
    logger.info(f"\nStep 2: GlobeEdge 預測（{engine_label}, decay={args.crisis_decay}）")
    predicted = run_globeedge_prediction(
        horizon=HORIZON,
        engine_type=args.engine,
        crisis_decay=args.crisis_decay,
    )
    logger.info(f"  Trajectory shape: {predicted.shape}")

    # Step 3: 比對
    logger.info("\nStep 3: 預測 vs 真實比對")
    report = compare(predicted, actual)

    for dim_idx, r in sorted(report["dimensions"].items()):
        icon = "✅" if r["direction_accuracy"] >= 0.5 else "❌"
        logger.info(
            f"  {icon} dim{dim_idx} {r['name']:10s}  "
            f"acc={r['direction_accuracy']:.2f}  "
            f"valid_days={r['valid_days']:2d}  "
            f"r={r['pearson_r']:+.3f}  "
            f"mse={r['mse']:.4f}"
        )

    logger.info(f"\n  ★ 整體 AUC: {report['overall_auc']:.3f}")
    logger.info(f"  最準維度: {report['best_dimension']}")
    logger.info(f"  最差維度: {report['worst_dimension']}")

    # Q3: b(0) 敏感度
    if not args.skip_q3:
        logger.info("\nStep 4: Q3 敏感度分析（b(0) 隨機化 5 次）")
        q3 = sensitivity_b0(actual, n_trials=5)
        logger.info(f"  Baseline AUC:   {report['overall_auc']:.3f}")
        logger.info(f"  隨機 b(0) 平均:  {q3['mean_random_auc']:.3f} ± {q3['std_random_auc']:.3f}")
        logger.info(f"  隨機 b(0) 範圍:  [{q3['min_random_auc']:.3f}, {q3['max_random_auc']:.3f}]")
        delta = report["overall_auc"] - q3["mean_random_auc"]
        logger.info(f"  Δ(baseline - random): {delta:+.3f}")
        if abs(delta) > 0.1:
            logger.info(f"  → b(0) 重要：初始信念設定大幅影響結果")
        else:
            logger.info(f"  → W 矩陣主導：b(0) 變動對結果影響小")
        report["sensitivity_b0"] = q3
        report["delta_baseline_vs_random"] = round(delta, 3)

    # 記錄引擎設定
    report["engine"] = args.engine
    report["crisis_decay"] = args.crisis_decay

    # 輸出
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告已輸出：{args.output}")


if __name__ == "__main__":
    main()
