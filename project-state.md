# GlobeEdge — Project State

> 社會信念動態世界模型
> Repo: https://github.com/DavidTao405/GlobeEdge_v1.0
> Last updated: 2026-03-22

---

## 專案概覽

| 項目 | 數值 |
|---|---|
| 原始碼檔案 | 86 |
| 總程式碼行數 | 11,128 |
| Git commits | 13 |
| Python 套件 | `globeedge/` |
| 測試 | 47/47 passing (0.78s) |
| 心理機制驗證 | 8/8 passing |
| 前端 TypeScript 錯誤 | 0 |

---

## 環境

| 項目 | 設定 |
|---|---|
| Python | 3.13.3 |
| venv | `.venv\` |
| OS | Windows, PowerShell |
| GPU | RTX 4070 SUPER |
| DB | PostgreSQL 16 (Docker) |
| Cache | Redis 7 (Docker) |
| LLM | Ollama qwen3.5:9b (本地) |
| Frontend | Vue 3 + TypeScript + Pinia |
| Charts | Observable Plot + D3 |

---

## Phase 完成狀態

| Phase | 名稱 | 狀態 | 關鍵產出 |
|---|---|---|---|
| Phase 1 | 數學核心 | ✅ 完成 | belief_state, fj_engine, monte_carlo, ews_monitor, distribution |
| Phase 2 | 資料模型 + API | ✅ 完成 | 7 ORM 實體, Flask CRUD API (projects, simulations, agents) |
| Phase 3 | 爬蟲層 | ✅ 完成 | PTT, Bluesky, RSS, 金融爬蟲 + APScheduler |
| Phase 4 | 地緣政治訊號 | ✅ 完成 | USGS, GDELT, ImpactMapper, signal_scheduler |
| Phase 5 | 仿真佇列 + GPU | ✅ 完成 | Celery task, torch.bmm GPU batching, Redis 進度 |
| Phase 6 | 前端儀表板 | ✅ 完成 | 結果展示 + 設計流程 + AI b(0) 估計 + What If |
| Phase 7 | 整合測試與校準 | ✅ 完成 | Granger Causality, EWS backtest, alpha=0.3 |

---

## 心理機制擴展

| Layer | 機制 | 狀態 | 關鍵驗證 |
|---|---|---|---|
| Layer 1 | Ebbinghaus 遺忘曲線 | ✅ | PTT 停電後恢復快 39% vs FJ |
| Layer 2 | ELM 雙路徑說服 | ✅ | High inv decay=0.15 < Low inv decay=0.40 |
| Layer 3 | 動機性推理 (Backfire) | ✅ | 反核↔擁核影響力降 98.1% |
| Layer 4 | System 1/2 雙歷程 | ✅ | S1(emo=0.8) 衰退快於 S2(emo=0.2) |

```python
PsychologyConfig(
    use_forgetting=True,           # Ebbinghaus
    use_elm=True,                  # ELM 雙路徑
    use_motivated_reasoning=True,  # Backfire Effect
    use_dual_process=True,         # System 1/2
)
```

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
│   └── intervention.py      #   What If 介入引擎
│
├── models/                  # SQLAlchemy ORM (7 實體)
│   ├── project.py
│   ├── agent.py             #   含 issue_involvement (ELM)
│   ├── influence_edge.py
│   ├── issue_dimension.py
│   ├── external_event.py
│   ├── simulation_result.py
│   └── ews_alert.py
│
├── api/                     # Flask Blueprint
│   ├── projects.py
│   ├── simulations.py       #   含 POST /{id}/whatif
│   └── agents.py            #   含 POST /estimate-belief
│
├── services/                # 業務服務
│   ├── belief_estimator.py  #   AI b(0) 估計 (Ollama)
│   └── message_analyzer.py  #   訊息情緒性分析 (System 1/2)
│
├── crawler/                 # 輿論爬蟲
│   ├── ptt_crawler.py
│   ├── bluesky_crawler.py
│   ├── news_crawler.py
│   ├── financial_crawler.py
│   ├── emotionality_tagger.py  # PTT 情緒標記 → Redis
│   └── scheduler.py
│
├── signals/                 # 地緣政治訊號
│   ├── usgs_signal.py
│   ├── gdelt_signal.py
│   ├── impact_mapper.py
│   └── signal_scheduler.py
│
├── scenarios/               # 6 個議題情境
│   ├── base.py
│   ├── energy.py            #   ①  台灣能源政策
│   ├── ai_regulation.py     #   ②  AI 監管
│   ├── geopolitics.py       #   ③  地緣政治
│   ├── trade_war.py         #   ④  貿易戰
│   ├── iran_war.py          #   ⑤★ 美伊戰爭
│   └── recall.py            #   ⑥★ 大罷免潮
│
├── tasks/                   # Celery
│   ├── celery_app.py
│   └── simulation_task.py
│
├── app.py
└── db.py

frontend/src/
├── views/                   # 8 個頁面
│   ├── ProjectListPage.vue  #   含心理機制 checkboxes
│   ├── DimensionPage.vue
│   ├── AgentDesignPage.vue  #   含 AI 估計 + 雷達圖
│   ├── EdgeDesignPage.vue   #   含 W 熱圖
│   ├── EventDesignPage.vue  #   含 Run Simulation
│   ├── WhatIfPage.vue       #   反事實分析
│   └── ResultDashboardPage.vue
├── components/              #   AgentRadarChart, RiskGauge, EWSChart...
├── stores/                  #   projectStore, simulationStore
└── lib/api.ts

scripts/
├── start_api.py             # Flask API 啟動
├── start_crawlers.py        # 爬蟲+訊號排程啟動
├── init_db.py
├── calibrate.py             # Granger Causality
├── backtest.py              # EWS backtest
├── run_scenario.py          # 情境仿真
├── test_psychology.py       # 心理機制驗證 (Layer 1-3)
└── test_dual_process.py     # System 1/2 驗證 (Layer 4)
```

---

## 校準結果 (Phase 7)

| 歷史事件 | 顯著邊 | alpha | MSE |
|---|---|---|---|
| 花蓮 M7.2 地震 | 7 | 0.3 | 0.0077 |
| 台灣總統大選 | 5 | 0.3 | 0.0110 |
| 裴洛西訪台 | 13 | 0.3 | 0.0074 |

---

## 六議題仿真結果

| # | 議題 | λ_max | EWS | 極化 spread |
|---|---|---|---|---|
| 5 | 美伊戰爭 ★ | **0.791** | high | 0.566 |
| 6 | 大罷免潮 ★ | 0.752 | **critical** | **0.881** |
| 1 | 能源政策 | 0.760 | high | **1.015** |
| 2 | AI 監管 | 0.726 | high | 0.812 |
| 3 | 地緣政治 | 0.745 | medium | 0.689 |
| 4 | 貿易戰 | 0.634 | medium | 0.483 |

---

## 驗證層次

| 層次 | 名稱 | 狀態 | 結果 |
|---|---|---|---|
| 1 | 理論一致性 | ✅ | 數學自洽，47/47 測試 |
| 2 | 歷史 Backtest | ✅ | 3 事件 AUC significant |
| 3a | 敏感度分析 | ✅ | Spread 變異 2.4% → ROBUST |
| 3b | 心理參數校準 | ✅ dry-run | forum S=2.0 ✅, demo S=4.5 ✅, kol S=19.4 ⚠️ |
| 4 | 預測性驗證 | ✅ dry-run | 方向準確率待真實 PTT 資料 |

### 敏感度分析關鍵發現
- **26 個參數組合**（S_forum × threshold × k）
- Spread 範圍 [1.312, 1.344] → **變異僅 2.4%**
- 結論反轉點：S_forum=1 時 PTT 恢復只需 2 步（vs S=2 時 30 步）
- Backfire k=1.0 時殘餘影響力仍 >0.01 → 效應不足

### 預測性驗證（dry-run 誠實結果）
- 方向準確率：0%（合成資料 vs 模型預測）
- **原因**：FJ+Ebbinghaus (alpha=0.3) 預測快速回到 b(0)，
  但真實輿論可能持續偏移 → alpha=0.3 可能過低
- 最準維度：能源供應安全感 (r=+0.438)
- 最不準維度：對美信任度 (r=-0.001)
- **這個失敗本身是重要發現**：需要用真實 PTT 資料重新校準

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

| 項目 | 狀態 |
|---|---|
| `.env` + `.claude/` 在 .gitignore | ✅ |
| LLM 呼叫上限 (20/run, $10/month) | ✅ |
| PostgreSQL/Redis 綁定 localhost | ✅ |

---

## Git History

```
cb1e854  System 1/2 dual process: message analyzer + emotionality tagger
1a374ff  Psychology mechanisms: Ebbinghaus + ELM + Motivated Reasoning
76eda17  What If counterfactual analysis: intervention engine + API + frontend
c05919f  Update project-state.md, todo.md, add README.md
4339249  AI-assisted belief estimation via Ollama Qwen3.5
ae41ce9  Add project-state.md
7a3baf4  Rename project: WorldEdge → GlobeEdge
f3b848b  Frontend: full scenario design workflow (5 new pages)
1d69354  Add real-time scenarios: Iran war + Taiwan recall
ba7b306  Phase 3-7: crawlers, signals, MoE core, calibration, 4 scenarios
0a0a956  Initial commit
```
