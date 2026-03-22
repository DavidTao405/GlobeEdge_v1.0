"""診斷預測失敗的根本原因。

用法:
    python scripts/diagnose_failure.py
    python scripts/diagnose_failure.py --output results/diagnosis_report.json

目標: 區分 0% 準確率的三個可能解釋
    A: alpha 太低（信念太快回歸 b(0)）
    B: b(0) 漂移（固有信念本身隨事件移動）
    C: impact_vector 設定錯誤（事件衝擊方向不對）
"""

import json
import logging
import os
import sys
from copy import deepcopy

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from globeedge.core.psychology import apply_forgetting, apply_motivated_reasoning
from globeedge.scenarios.iran_war import build as build_scenario
from scripts.predictive_validation import (
    IRAN_WAR_TIMELINE,
    VALIDATION_DIMS,
    generate_synthetic_ptt,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# ── 核心仿真 ──────────────────────────────────────────────

def run_simulation(
    alpha: float,
    B0: np.ndarray,
    W: np.ndarray,
    agent_types: list[str],
    events: dict[int, np.ndarray],
    horizon: int = 22,
    use_forgetting: bool = True,
) -> np.ndarray:
    """跑 FJ + Ebbinghaus，回傳 (horizon+1, n_agents, n_dims)。"""
    W_mod = apply_motivated_reasoning(W, B0)

    trajectory = []
    B = B0.copy()
    for t in range(horizon + 1):
        trajectory.append(B.copy())
        if t < horizon:
            B_next = alpha * W_mod @ B + (1 - alpha) * B0
            if t in events:
                B_next = B_next + events[t]
            B_next = np.clip(B_next, -1.0, 1.0)
            if use_forgetting:
                B_next = apply_forgetting(B_next, B0, agent_types)
            B_next = np.clip(B_next, -1.0, 1.0)
            B = B_next

    return np.array(trajectory)


def compute_direction_accuracy(
    predicted: np.ndarray,
    actual: dict[int, dict[int, float]],
) -> tuple[float, dict[int, dict]]:
    """計算方向準確率和每維度誤差。"""
    horizon = predicted.shape[0] - 1
    dim_results = {}

    for dim_idx, info in VALIDATION_DIMS.items():
        pred_series = [float(predicted[t, :, dim_idx].mean()) for t in range(horizon + 1)]
        actual_days = actual.get(dim_idx, {})
        actual_series = [actual_days.get(t, 0.0) for t in range(horizon + 1)]

        pred_trend = pred_series[-1] - pred_series[0]
        actual_trend = actual_series[-1] - actual_series[0]
        direction_match = (pred_trend > 0.05 and actual_trend > 0.05) or \
                          (pred_trend < -0.05 and actual_trend < -0.05) or \
                          (abs(pred_trend) <= 0.05 and abs(actual_trend) <= 0.05)

        # Pearson on diffs
        if len(pred_series) > 1:
            pd = np.diff(pred_series)
            ad = np.diff(actual_series)
            if np.std(pd) > 1e-9 and np.std(ad) > 1e-9:
                corr = float(np.corrcoef(pd, ad)[0, 1])
            else:
                corr = 0.0
        else:
            corr = 0.0

        dim_results[dim_idx] = {
            "name": info["name"],
            "direction_match": direction_match,
            "pred_delta": round(pred_trend, 4),
            "actual_delta": round(actual_trend, 4),
            "correlation": round(corr, 3),
            "pred_final": round(pred_series[-1], 4),
            "actual_final": round(actual_series[-1], 4),
        }

    matches = sum(1 for r in dim_results.values() if r["direction_match"])
    accuracy = matches / len(dim_results) if dim_results else 0.0

    return accuracy, dim_results


# ── Step 2: 維度誤差分析（解釋 C）──────────────────────────

def diagnose_impact_vectors(dim_results: dict[int, dict]) -> dict:
    """分析哪些維度的 impact_vector 可能設錯。"""
    errors = {}
    for dim_idx, r in dim_results.items():
        pred_dir = "+" if r["pred_delta"] > 0.05 else "-" if r["pred_delta"] < -0.05 else "0"
        actual_dir = "+" if r["actual_delta"] > 0.05 else "-" if r["actual_delta"] < -0.05 else "0"

        if pred_dir != actual_dir and pred_dir != "0" and actual_dir != "0":
            severity = "reversed"  # 方向完全相反
        elif pred_dir != actual_dir:
            severity = "mismatch"  # 不一致但非完全相反
        else:
            severity = "correct"

        errors[r["name"]] = {
            "dim_index": dim_idx,
            "predicted_direction": pred_dir,
            "actual_direction": actual_dir,
            "severity": severity,
            "correlation": r["correlation"],
        }

    worst = min(errors.values(), key=lambda x: abs(x["correlation"]))
    reversed_count = sum(1 for e in errors.values() if e["severity"] == "reversed")

    return {
        "dimension_errors": errors,
        "worst_dimension": worst["dim_index"],
        "reversed_count": reversed_count,
        "supported": reversed_count >= 2,  # 如果 ≥2 個維度方向相反 → C 成立
    }


# ── Step 3: Alpha 掃描（解釋 A）──────────────────────────

def diagnose_alpha(
    B0: np.ndarray, W: np.ndarray, agent_types: list[str],
    events: dict[int, np.ndarray], actual: dict[int, dict[int, float]],
    horizon: int = 22,
) -> dict:
    """掃描 alpha 值，找最佳值。"""
    alpha_scan = {}

    for alpha in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        traj = run_simulation(alpha, B0, W, agent_types, events, horizon)
        acc, _ = compute_direction_accuracy(traj, actual)
        alpha_scan[str(alpha)] = round(acc, 3)

    optimal_alpha = max(alpha_scan, key=alpha_scan.get)
    baseline_acc = alpha_scan.get("0.3", 0.0)
    best_acc = alpha_scan[optimal_alpha]
    improvement = best_acc - baseline_acc

    return {
        "alpha_scan": alpha_scan,
        "optimal_alpha": float(optimal_alpha),
        "baseline_accuracy": baseline_acc,
        "best_accuracy": best_acc,
        "accuracy_improvement": f"{baseline_acc*100:.0f}% → {best_acc*100:.0f}%",
        "supported": improvement > 0.25 and float(optimal_alpha) > 0.3,
    }


# ── Step 4: b(0) 漂移測試（解釋 B）──────────────────────

def diagnose_b0_drift(
    B0: np.ndarray, W: np.ndarray, agent_types: list[str],
    events: dict[int, np.ndarray], actual: dict[int, dict[int, float]],
    horizon: int = 22, alpha: float = 0.3,
) -> dict:
    """每 7 天用當週平均立場更新 b(0)。"""
    n_agents, n_dims = B0.shape
    drift_rate = 0.05

    # 基準（不漂移）
    traj_base = run_simulation(alpha, B0, W, agent_types, events, horizon)
    acc_base, _ = compute_direction_accuracy(traj_base, actual)

    # 漂移版本：每 7 天用 actual 資料微調 b(0)
    B0_drift = B0.copy()
    weekly_accuracies = {}

    for week in range(1, 4):  # 第 1-3 週
        week_start = (week - 1) * 7
        week_end = min(week * 7, horizon)

        # 從 actual 計算當週平均立場
        for dim_idx in VALIDATION_DIMS:
            actual_days = actual.get(dim_idx, {})
            week_vals = [actual_days.get(t, 0.0) for t in range(week_start, week_end)]
            if week_vals:
                observed_mean = np.mean(week_vals)
                # 每個 Agent 的 b(0) 向觀測值漂移
                for i in range(n_agents):
                    B0_drift[i, dim_idx] += drift_rate * (observed_mean - B0_drift[i, dim_idx])

        # 用漂移後的 b(0) 重跑
        traj_drift = run_simulation(alpha, B0_drift, W, agent_types, events, horizon)
        acc_drift, _ = compute_direction_accuracy(traj_drift, actual)
        weekly_accuracies[f"week_{week}"] = round(acc_drift, 3)

    final_drift_acc = weekly_accuracies.get("week_3", 0.0)
    improvement = final_drift_acc - acc_base

    return {
        "baseline_accuracy": round(acc_base, 3),
        "weekly_accuracies": weekly_accuracies,
        "final_drift_accuracy": final_drift_acc,
        "b0_drift_improvement": f"{acc_base*100:.0f}% → {final_drift_acc*100:.0f}%",
        "drift_rate": drift_rate,
        "supported": improvement > 0.15,
    }


# ── Step 5: 整合診斷 ──────────────────────────────────────

def integrate_diagnosis(
    explain_a: dict, explain_b: dict, explain_c: dict,
) -> dict:
    """整合三個解釋，判定主因。"""
    improvements = {
        "A": explain_a["best_accuracy"] - explain_a["baseline_accuracy"],
        "B": explain_b["final_drift_accuracy"] - explain_b["baseline_accuracy"],
        "C": 0.3 if explain_c["reversed_count"] >= 2 else 0.0,
    }

    # 主因判定
    best_cause = max(improvements, key=improvements.get)
    best_improvement = improvements[best_cause]

    if best_improvement < 0.1:
        most_likely = "ABC_mixed"
        confidence = 0.3
        explanation = "三個解釋改善幅度都不大，可能是混合因素或模型結構性問題"
        recommendation = "需要更多真實資料累積（90 天 PTT 追蹤）"
        next_step = "Phase 8: 長期資料收集 + 模型結構重新評估"
    elif best_cause == "A":
        most_likely = "A"
        confidence = min(0.5 + best_improvement, 0.9)
        explanation = (
            f"alpha=0.3 導致信念過快回歸 b(0)。"
            f"最佳 alpha={explain_a['optimal_alpha']}，"
            f"準確率提升 {explain_a['accuracy_improvement']}"
        )
        recommendation = (
            f"引入動態 alpha：平時 0.3，持續危機下升至 {explain_a['optimal_alpha']}"
        )
        next_step = "Phase 8A: 實作 DynamicAlpha（alpha 隨事件強度調整）"
    elif best_cause == "B":
        most_likely = "B"
        confidence = min(0.5 + best_improvement, 0.9)
        explanation = (
            f"b(0) 在持續危機中漂移（非固定錨點）。"
            f"3 週漂移後準確率 {explain_b['b0_drift_improvement']}"
        )
        recommendation = "引入 b(0) 緩慢漂移機制：每週用觀測資料微調固有信念"
        next_step = "Phase 8B: 實作 b(0) adaptive drift"
    else:
        most_likely = "C"
        confidence = 0.7
        worst_dim = explain_c["worst_dimension"]
        worst_name = VALIDATION_DIMS.get(worst_dim, {}).get("name", str(worst_dim))
        explanation = (
            f"impact_vector 方向設定可能有誤，"
            f"{explain_c['reversed_count']} 個維度方向相反。"
            f"最不準維度: {worst_name}"
        )
        recommendation = f"重新校準 {worst_name} 的 impact_vector，用真實 PTT 反應驗證方向"
        next_step = "Phase 8C: impact_vector 自動校準（用真實事件反應）"

    return {
        "most_likely_cause": most_likely,
        "cause_explanation": explanation,
        "confidence": round(confidence, 2),
        "improvements": {k: round(v, 3) for k, v in improvements.items()},
        "recommendation": recommendation,
        "next_step": next_step,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="GlobeEdge 預測失敗診斷")
    parser.add_argument("--output", type=str, default="results/diagnosis_report.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    scenario = build_scenario()
    B0 = scenario.belief_matrix()
    W = scenario.default_W()
    agent_types = scenario.agent_types()
    n_agents, n_dims = B0.shape
    horizon = 22

    # 建立事件 dict
    events = {}
    for evt in IRAN_WAR_TIMELINE:
        day = evt["day"]
        if day <= horizon:
            impact = np.zeros((n_agents, n_dims))
            for i in range(n_agents):
                impact[i] = evt["impact"]
            events[day] = impact

    # 取得真實資料（dry-run: 合成）
    logger.info("=" * 60)
    logger.info("Step 1: 載入資料")
    logger.info("=" * 60)
    actual = generate_synthetic_ptt(horizon=horizon)
    dry_run = True
    logger.info(f"  mode: {'dry_run (合成資料)' if dry_run else 'live (PTT 真實資料)'}")
    logger.info(f"  {len(actual)} 個驗證維度, horizon={horizon}")

    # 基準結果
    traj_base = run_simulation(0.3, B0, W, agent_types, events, horizon)
    baseline_acc, baseline_dims = compute_direction_accuracy(traj_base, actual)
    logger.info(f"  baseline accuracy (alpha=0.3): {baseline_acc*100:.0f}%")

    # Step 2: 維度誤差分析
    logger.info(f"\n{'='*60}")
    logger.info("Step 2: 維度誤差分析 (解釋 C)")
    logger.info("=" * 60)
    explain_c = diagnose_impact_vectors(baseline_dims)
    for name, err in explain_c["dimension_errors"].items():
        icon = {"correct": "✅", "mismatch": "⚠️", "reversed": "❌"}[err["severity"]]
        logger.info(
            f"  {icon} {name:15s}  pred={err['predicted_direction']}  "
            f"actual={err['actual_direction']}  r={err['correlation']:+.3f}  "
            f"[{err['severity']}]"
        )
    logger.info(f"  反向維度: {explain_c['reversed_count']}")
    logger.info(f"  解釋 C 成立: {explain_c['supported']}")

    # Step 3: Alpha 掃描
    logger.info(f"\n{'='*60}")
    logger.info("Step 3: Alpha 掃描 (解釋 A)")
    logger.info("=" * 60)
    explain_a = diagnose_alpha(B0, W, agent_types, events, actual, horizon)
    for alpha_str, acc in explain_a["alpha_scan"].items():
        marker = " ← current" if alpha_str == "0.3" else " ← BEST" if alpha_str == str(explain_a["optimal_alpha"]) else ""
        logger.info(f"  alpha={alpha_str}  accuracy={acc*100:.0f}%{marker}")
    logger.info(f"  最佳 alpha: {explain_a['optimal_alpha']}")
    logger.info(f"  改善: {explain_a['accuracy_improvement']}")
    logger.info(f"  解釋 A 成立: {explain_a['supported']}")

    # Step 4: b(0) 漂移
    logger.info(f"\n{'='*60}")
    logger.info("Step 4: b(0) 漂移測試 (解釋 B)")
    logger.info("=" * 60)
    explain_b = diagnose_b0_drift(B0, W, agent_types, events, actual, horizon)
    for week, acc in explain_b["weekly_accuracies"].items():
        logger.info(f"  {week}: accuracy={acc*100:.0f}%")
    logger.info(f"  改善: {explain_b['b0_drift_improvement']}")
    logger.info(f"  解釋 B 成立: {explain_b['supported']}")

    # Step 5: 整合
    logger.info(f"\n{'='*60}")
    logger.info("Step 5: 整合診斷")
    logger.info("=" * 60)
    diagnosis = integrate_diagnosis(explain_a, explain_b, explain_c)
    logger.info(f"  主因: {diagnosis['most_likely_cause']}")
    logger.info(f"  信心: {diagnosis['confidence']}")
    logger.info(f"  說明: {diagnosis['cause_explanation']}")
    logger.info(f"  建議: {diagnosis['recommendation']}")
    logger.info(f"  下一步: {diagnosis['next_step']}")

    # 輸出報告
    report = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "dry_run": dry_run,
        "period": "2026-02-28 to 2026-03-22",
        "baseline_accuracy": round(baseline_acc, 3),
        "diagnosis": diagnosis,
        "explanation_A": explain_a,
        "explanation_B": explain_b,
        "explanation_C": explain_c,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n報告已輸出到 {args.output}")

    # 最後摘要
    logger.info(f"\n{'='*60}")
    logger.info("診斷摘要")
    logger.info(f"{'='*60}")
    logger.info(f"  解釋 A (alpha 太低):    改善 {diagnosis['improvements']['A']*100:+.0f}%  {'✅ 支持' if explain_a['supported'] else '❌ 不支持'}")
    logger.info(f"  解釋 B (b(0) 漂移):     改善 {diagnosis['improvements']['B']*100:+.0f}%  {'✅ 支持' if explain_b['supported'] else '❌ 不支持'}")
    logger.info(f"  解釋 C (impact 設錯):   反向 {explain_c['reversed_count']}/4     {'✅ 支持' if explain_c['supported'] else '❌ 不支持'}")
    logger.info(f"\n  → 最可能原因: {diagnosis['most_likely_cause']} (信心 {diagnosis['confidence']})")
    logger.info(f"  → {diagnosis['recommendation']}")


if __name__ == "__main__":
    main()
