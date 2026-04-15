# GlobeEdge — Project State

> 社會信念動態世界模型（Friedkin-Johnsen + 心理學擴展）
> Repo: https://github.com/DavidTao405/GlobeEdge_v1.0
> Last updated: 2026-04-09

---

## 專案概覽

| 項目 | 數值 |
|---|---|
| 原始碼檔案 | 96 |
| 總程式碼行數 | 13,841 |
| Git commits | 20 |
| Python 套件 | `globeedge/` |
| 測試 | 70/70 passing (3.81s) |
| 前端 | Vue 3 + TypeScript + Observable Plot |
| DB 累積 | PTT 753 篇 + ExternalEvents 413 筆 |

---

## 環境

| 項目 | 設定 |
|---|---|
| Python | 3.13.3 |
| venv | `.venv\` |
| OS | Windows 11, PowerShell |
| GPU | RTX 4070 SUPER |
| DB | PostgreSQL 16 (Docker, volume=pgdata) |
| Cache | Redis 7 (Docker) |
| LLM | Ollama qwen3.5:9b (本機) |
| Frontend | Vue 3 + TypeScript + Pinia + Observable Plot + D3 |

---

## Phase 完成狀態

| Phase | 名稱 | 狀態 |
|---|---|---|
| 1 | 數學核心 | ✅ belief_state, fj_engine, monte_carlo, ews_monitor, distribution |
| 2 | 資料模型 + API | ✅ 7 ORM + Flask CRUD (projects, simulations, agents) |
| 3 | 爬蟲層 | ✅ PTT (curl_cffi), Bluesky, RSS, 金融 + APScheduler 7 jobs |
| 4 | 地緣政治訊號 | ✅ USGS, GDELT, ImpactMapper, signal_scheduler |
| 5 | 仿真佇列 + GPU | ✅ Celery task, torch.bmm GPU batching, Redis 進度 |
| 6 | 前端儀表板 | ✅ 8 頁面 + AI b(0) 估計 + What If + 心理機制 UI |
| 7 | 整合測試與校準 | ✅ Granger Causality, EWS backtest, alpha=0.3 |

---

## 核心擴展

### 心理機制（4 層）

| Layer | 機制 | 驗證結果 |
|---|---|---|
| 1 | Ebbinghaus 遺忘曲線 | PTT S=2 恢復快 39% vs FJ |
| 2 | ELM 雙路徑說服 | High inv decay=0.15 < Low inv decay=0.40 |
| 3 | 動機性推理 (Backfire) | 反核↔擁核影響力降 98.1% |
| 4 | System 1/2 雙歷程 | S1(emo=0.8) 衰退快於 S2(emo=0.2) |

### CrisisAwareFJEngine

| 機制 | 說明 |
|---|---|
| Dynamic alpha | base=0.3 → crisis=0.6（危機中錨定減弱） |
| Dynamic b(0) | drift_rate=0.03（持續危機重寫固有信念） |
| Spread floor | MIN_SPREAD=0.12（防高 alpha 信念崩潰） |
| 驗證 | 美伊戰爭方向準確率 0% → 50% |

### 敏感度分析

- 26 參數組合，Spread 變異僅 2.4% → **ROBUST**
- 結論反轉點：S_forum=1（PTT 恢復只需 2 步）、k=1.0（Backfire 效應不足）

---

## 六議題仿真結果

| # | 議題 | 類型 | λ_max | EWS | 極化 spread |
|---|---|---|---|---|---|
| 5 | 美伊戰爭 | ★ 即時 | **0.791** | high | 0.566 |
| 6 | 大罷免潮 | ★ 即時 | 0.752 | **critical** | **0.881** |
| 1 | 能源政策 | backtest | 0.760 | high | **1.015** |
| 2 | AI 監管 | backtest | 0.726 | high | 0.812 |
| 3 | 地緣政治 | backtest | 0.745 | medium | 0.689 |
| 4 | 貿易戰 | backtest | 0.634 | medium | 0.483 |

---

## PTT 真實資料校準

兩個事件用真實 PTT 推噓結構校準 impact_vector：

| 事件 | 篇數 | 推噓比 | → 比例 | 類型 |
|---|---|---|---|---|
| 柯文哲判決 17年 | 55 | 89:11 | 59% | 分裂型（共識但沉默對立） |
| 鄭習會宣布 | 44 | 66:34 | 55% | 爭議型（藍綠積極對立） |

---

## DB 資料累積

| 資料源 | 筆數 | 期間 | 看板 |
|---|---|---|---|
| PTT 文章 | 753 | 03-22 ~ 04-07 | 八卦 344 / 政黑 409 |
| External Events | 413 | GDELT + USGS | |
| 推/噓/→ | 10,352 / 1,924 / 11,189 | | |

關鍵字覆蓋：
| 關鍵字 | 篇數 |
|---|---|
| 柯文哲 | 95 |
| 鄭麗文 | 86 |
| 川普 | 67 |
| 鄭習會 | 66 |
| 罷免 | 53 |
| 關稅 | 39 |

---

## 目錄結構

```
globeedge/
├── core/                    # 數學核心
│   ├── belief_state.py      #   BeliefState (frozen)
│   ├── fj_engine.py         #   FJ 引擎 (4 層心理機制 flags)
│   ├── monte_carlo.py       #   MC runner + MoE 噪聲
│   ├── ews_monitor.py       #   MoE 多專家 EWS
│   ├── distribution.py      #   SimulationDistribution
│   ├── psychology.py        #   4 層心理機制
│   ├── intervention.py      #   What If 介入引擎
│   └── crisis_dynamics.py   #   CrisisAwareFJEngine + spread floor
│
├── models/                  # SQLAlchemy ORM (8 表)
│   ├── project.py / agent.py / influence_edge.py
│   ├── issue_dimension.py / external_event.py
│   ├── simulation_result.py / ews_alert.py
│   └── ptt_article.py       #   PTT 文章持久化
│
├── api/                     # Flask Blueprint
│   ├── projects.py / simulations.py (含 whatif)
│   └── agents.py (含 estimate-belief)
│
├── services/                # 業務服務
│   ├── belief_estimator.py  #   AI b(0) 估計 (Ollama)
│   └── message_analyzer.py  #   訊息情緒性分析
│
├── crawler/                 # 輿論爬蟲
│   ├── ptt_crawler.py       #   curl_cffi + 推噓解析 + DB 寫入
│   ├── bluesky_crawler.py / news_crawler.py / financial_crawler.py
│   ├── emotionality_tagger.py
│   └── scheduler.py         #   APScheduler 7 jobs
│
├── signals/                 # 地緣政治訊號
│   ├── usgs_signal.py / gdelt_signal.py / impact_mapper.py
│   └── signal_scheduler.py
│
├── scenarios/               # 6 議題情境
│   ├── base.py / energy.py / ai_regulation.py
│   ├── geopolitics.py       #   含鄭習會事件（PTT 校準）
│   ├── trade_war.py / iran_war.py
│   └── recall.py            #   含柯文哲判決 + WBC 事件
│
├── tasks/                   #   Celery
└── app.py / db.py

frontend/src/
├── views/  (8 頁面)
├── components/  (RadarChart, RiskGauge, EWSChart...)
├── stores/  (projectStore, simulationStore)
└── lib/api.ts

scripts/
├── start_api.py / start_crawlers.py / init_db.py
├── backfill_ptt.py          #   關鍵字補抓
├── calibrate.py / backtest.py / run_scenario.py
├── sensitivity_analysis.py / calibrate_psychology.py
├── predictive_validation.py / diagnose_failure.py
├── run_cross_topic.py
├── test_psychology.py / test_dual_process.py
├── test_accumulator.py / test_crisis_dynamics.py
└── test_spread_floor.py
```

---

## 校準結果

### Phase 7 Granger Causality

| 歷史事件 | 顯著邊 | 最佳 alpha | MSE |
|---|---|---|---|
| 花蓮 M7.2 地震 | 7 | 0.3 | 0.0077 |
| 台灣總統大選 | 5 | 0.3 | 0.0110 |
| 裴洛西訪台 | 13 | 0.3 | 0.0074 |

### 研究故事

```
FJ baseline (alpha=0.3)     → 0%   一次性衝擊假設的邊界
+ EventAccumulator          → 0%   Ebbinghaus 不是根本問題
+ CrisisAwareFJEngine       → 50%  FJ 結構限制的修正方向正確
```

---

## 服務運行狀態

| 服務 | 啟動方式 | 位址 |
|---|---|---|
| PostgreSQL | `docker compose up -d` | 127.0.0.1:5432 |
| Redis | `docker compose up -d` | 127.0.0.1:6379 |
| Flask API | `python scripts/start_api.py` | 0.0.0.0:5001 |
| 爬蟲+訊號 | `python scripts/start_crawlers.py` | 背景 7 jobs |
| Ollama | 系統服務 | localhost:11434 |
| 前端 | `cd frontend && npm run dev` | localhost:5173 |

---

## 安全措施

- `.env` + `.claude/` 在 .gitignore ✅
- LLM 呼叫上限 (20/run, $10/month) ✅
- PostgreSQL/Redis 綁定 127.0.0.1 ✅
- Docker volume `pgdata` 持久化 ✅

---

## Git History (20 commits)

```
c209dd5  Enable PTT DB persistence in scheduler + clean startup script
e7aa78d  PTT article persistence: ptt_articles table + crawler DB write
48749cd  Add WBC Team Taiwan event to recall scenario
b1cde96  CrisisAwareFJEngine: direction accuracy 0% → 50%
469d46a  EventAccumulator: sustained crisis vs one-time shock
4068c5d  Cross-topic coupling: multi-topic opinion dynamics
7a75644  Diagnosis: root cause analysis of 0% prediction accuracy
9c72c99  Validation Layer 3-4: sensitivity, calibration, prediction
11606f6  Update docs, add research report
cb1e854  System 1/2 dual process: message analyzer + emotionality tagger
1a374ff  Psychology mechanisms: Ebbinghaus + ELM + Motivated Reasoning
76eda17  What If counterfactual analysis
c05919f  Update project-state.md, todo.md, add README.md
4339249  AI-assisted belief estimation via Ollama Qwen3.5
ae41ce9  Add project-state.md
7a3baf4  Rename project: WorldEdge → GlobeEdge
f3b848b  Frontend: full scenario design workflow (5 new pages)
1d69354  Add real-time scenarios: Iran war + Taiwan recall
ba7b306  Phase 3-7: crawlers, signals, MoE core, calibration, 4 scenarios
0a0a956  Initial commit
```
