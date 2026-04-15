"""TimesFM 柯文哲每日篇數時序曲線實驗。

驗證 SEIR 潛伏期假說（PLAN.md 第 8.7 節）：
  H1（單峰衰退）：立即高峰 → 快速指數衰退 → 符合 FJ 假設
  H2（多峰/延遲）：有第二個峰值 → SEIR 潛伏期假說成立

輸出：
  1. 每日篇數數列
  2. TimesFM 未來 7 天預測（含 10th-90th 分位信賴區間）
  3. 曲線形狀判斷
  4. crisis_decay 參數建議
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

START = datetime(2026, 3, 26)
END = datetime(2026, 4, 16)


def fetch_daily_counts(keywords: list[str]) -> tuple[list[str], list[int]]:
    """從 DB 取關鍵字相關的每日篇數。"""
    from globeedge.app import create_app
    from globeedge.db import db
    from globeedge.models import PttArticle

    app = create_app()
    with app.app_context():
        filters = [PttArticle.title.contains(kw) for kw in keywords]
        arts = PttArticle.query.filter(db.or_(*filters)).all()

        daily = Counter()
        for a in arts:
            m = re.search(r"M\.(\d+)\.A", a.url)
            if not m:
                continue
            dt = datetime.fromtimestamp(int(m.group(1)))
            if START <= dt < END:
                daily[dt.strftime("%Y-%m-%d")] += 1

    dates = []
    counts = []
    d = START
    while d < END:
        dates.append(d.strftime("%Y-%m-%d"))
        counts.append(daily.get(dates[-1], 0))
        d += timedelta(days=1)
    return dates, counts


def run_timesfm_forecast(series: list[int], horizon: int = 7) -> dict:
    """用 TimesFM 2.5 預測未來 horizon 天。"""
    import timesfm

    logger.info("Loading TimesFM 2.5-200M (pytorch)...")
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch"
    )
    model.compile(
        timesfm.ForecastConfig(
            max_context=max(128, len(series) + 16),
            max_horizon=max(32, horizon),
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=True,
            fix_quantile_crossing=True,
        )
    )

    logger.info(f"Forecasting {horizon} days ahead...")
    inputs = [np.asarray(series, dtype=np.float32)]
    point_forecast, quantile_forecast = model.forecast(
        horizon=horizon, inputs=inputs
    )

    point = point_forecast[0].tolist()
    # quantile_forecast shape: (batch, horizon, n_quantiles)
    # quantiles: [0.1, 0.2, ..., 0.9] + mean
    q = np.asarray(quantile_forecast[0])  # (horizon, n_q)

    return {
        "point": [round(float(x), 2) for x in point],
        "q10": [round(float(v), 2) for v in q[:, 0].tolist()],  # 10th percentile
        "q50": [round(float(v), 2) for v in q[:, 4].tolist()],  # median
        "q90": [round(float(v), 2) for v in q[:, 8].tolist()],  # 90th percentile
    }


def analyze_shape(counts: list[int]) -> dict:
    """分析曲線形狀：單峰 vs 多峰。"""
    arr = np.array(counts)

    # 找 local maxima（相對於前後各 2 天）
    peaks = []
    for i in range(len(arr)):
        lo = max(0, i - 2)
        hi = min(len(arr), i + 3)
        window = arr[lo:hi]
        if arr[i] == max(window) and arr[i] >= 5:
            if not peaks or i - peaks[-1] >= 3:  # 至少間隔 3 天
                peaks.append(i)

    # 主峰
    main_peak_idx = int(np.argmax(arr))
    main_peak_val = int(arr[main_peak_idx])

    # 主峰後的「第二峰」
    secondary = None
    for p in peaks:
        if p > main_peak_idx + 3 and arr[p] >= main_peak_val * 0.3:
            secondary = {"day": p, "count": int(arr[p]), "ratio": round(arr[p] / main_peak_val, 2)}
            break

    # 指數衰退擬合：檢查是否符合 exp(-t/τ)
    # 用主峰後 5 天擬合
    decay_series = arr[main_peak_idx:main_peak_idx + 6]
    if len(decay_series) >= 3 and decay_series[0] > 0:
        # log(y) = log(a) - t/tau
        y = np.log(np.maximum(decay_series, 0.5))  # avoid log(0)
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        tau_days = -1 / slope if slope < 0 else float("inf")
        # R² of exponential fit
        y_pred = intercept + slope * x
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    else:
        tau_days = None
        r2 = 0.0

    shape = "多峰" if secondary else "單峰"
    hypothesis = "H2（多峰/延遲）→ SEIR 潛伏期假說" if secondary else "H1（單峰衰退）→ FJ 指數衰退"

    # crisis_decay 建議
    # 目前 CrisisConfig.crisis_decay = 0.05（每步衰退 5%）
    # 如果 τ 值很短（1-2 天），衰退應更快 → 0.1+
    # 如果 τ 值長或多峰，衰退應更慢 → 0.02
    if secondary:
        decay_suggestion = 0.02
        decay_reason = "多峰：危機強度不應快速衰退，社會強化效應存在"
    elif tau_days and tau_days < 2:
        decay_suggestion = 0.15
        decay_reason = f"τ={tau_days:.1f} 天 < 2，應加速衰退"
    elif tau_days and tau_days < 4:
        decay_suggestion = 0.05
        decay_reason = f"τ={tau_days:.1f} 天，當前設定 0.05 合理"
    else:
        decay_suggestion = 0.03
        decay_reason = "衰退較慢或擬合不佳，建議保守降低 crisis_decay"

    return {
        "shape": shape,
        "hypothesis_supported": hypothesis,
        "peaks": [{"day": p, "count": int(arr[p])} for p in peaks],
        "main_peak": {"day": main_peak_idx, "count": main_peak_val},
        "secondary_peak": secondary,
        "exp_decay_tau_days": round(tau_days, 2) if tau_days else None,
        "exp_decay_r2": round(r2, 3),
        "crisis_decay_suggestion": decay_suggestion,
        "crisis_decay_reason": decay_reason,
    }


def plot_ascii(counts: list[int], forecast: dict, dates: list[str]) -> str:
    """ASCII 時序圖：實際 + 預測 + 信賴區間。"""
    all_vals = counts + forecast["point"] + forecast["q90"]
    max_v = max(all_vals) if all_vals else 1
    width = 35

    lines = []
    lines.append("=" * 70)
    lines.append("  柯文哲每日篇數時序（實際 + TimesFM 預測）")
    lines.append("=" * 70)
    lines.append(f"  {'日期':<11}  {'計數':>4}  圖示")
    lines.append("  " + "─" * 60)

    # 實際
    for d, c in zip(dates, counts):
        bar_len = int(c / max_v * width) if max_v else 0
        bar = "█" * bar_len
        lines.append(f"  {d}  {c:4d}  {bar}")

    # 預測
    last_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    lines.append("  " + "─" * 60 + "  (以下為 TimesFM 預測)")
    for i, p in enumerate(forecast["point"]):
        d = (last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        bar_len = int(p / max_v * width) if max_v else 0
        ci_lo = forecast["q10"][i]
        ci_hi = forecast["q90"][i]
        bar = "░" * bar_len
        lines.append(f"  {d}  {p:4.1f}  {bar}  [10%={ci_lo:.1f}, 90%={ci_hi:.1f}]")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TimesFM 柯文哲時序實驗")
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--output", type=str, default="results/timesfm_ko.json")
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    keywords = ["柯文哲", "京華城", "判決", "17年"]

    logger.info("=" * 60)
    logger.info("  TimesFM 柯文哲每日篇數時序實驗")
    logger.info("=" * 60)

    # Step 1
    logger.info("\nStep 1: 從 DB 取每日篇數")
    dates, counts = fetch_daily_counts(keywords)
    logger.info(f"  期間：{dates[0]} to {dates[-1]}  ({len(dates)} 天)")
    logger.info(f"  總篇數：{sum(counts)}")
    logger.info(f"  時序：{counts}")

    # Step 2
    logger.info(f"\nStep 2: TimesFM 預測未來 {args.horizon} 天")
    forecast = run_timesfm_forecast(counts, horizon=args.horizon)
    logger.info(f"  point: {forecast['point']}")
    logger.info(f"  q10:   {forecast['q10']}")
    logger.info(f"  q90:   {forecast['q90']}")

    # Step 3
    logger.info(f"\nStep 3: 曲線形狀分析")
    shape_report = analyze_shape(counts)
    logger.info(f"  形狀: {shape_report['shape']}")
    logger.info(f"  主峰: day {shape_report['main_peak']['day']} = {shape_report['main_peak']['count']} 篇")
    if shape_report["secondary_peak"]:
        sp = shape_report["secondary_peak"]
        logger.info(f"  次峰: day {sp['day']} = {sp['count']} 篇 ({sp['ratio']*100:.0f}% of main)")
    logger.info(f"  所有峰值: {shape_report['peaks']}")
    logger.info(f"  指數衰退 τ: {shape_report['exp_decay_tau_days']} 天 (R²={shape_report['exp_decay_r2']})")
    logger.info(f"  假說判定: {shape_report['hypothesis_supported']}")

    # Step 4: ASCII 圖
    logger.info(f"\nStep 4: 時序圖（實線=實際，虛線=預測）")
    logger.info(plot_ascii(counts, forecast, dates))

    # Step 5: crisis_decay 建議
    logger.info(f"\nStep 5: crisis_decay 參數建議")
    logger.info(f"  當前設定：0.05")
    logger.info(f"  建議數值：{shape_report['crisis_decay_suggestion']}")
    logger.info(f"  理由：{shape_report['crisis_decay_reason']}")

    # 輸出 JSON
    output = {
        "period": f"{dates[0]} to {dates[-1]}",
        "horizon": args.horizon,
        "keywords": keywords,
        "daily_counts": counts,
        "dates": dates,
        "total": sum(counts),
        "timesfm_forecast": forecast,
        "shape_analysis": shape_report,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"\n報告已輸出：{args.output}")


if __name__ == "__main__":
    main()
