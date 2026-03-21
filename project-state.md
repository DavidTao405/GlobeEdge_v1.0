# GlobeEdge — Project State

> 社會信念動態世界模型
> Repo: https://github.com/DavidTao405/GlobeEdge_v1.0
> Last updated: 2026-03-22

---

## 專案概覽

| 項目 | 數值 |
|---|---|
| 原始碼檔案 | 76 |
| 總程式碼行數 | 8,542 |
| Git commits | 7 |
| Python 套件 | `globeedge/` |
| 測試 | 47/47 passing (0.78s) |
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
| Phase 6 | 前端儀表板 | ✅ 完成 | 結果展示 + 5 頁設計流程 + AI 輔助 b(0) 估計 |
| Phase 7 | 整合測試與校準 | ✅ 完成 | Granger Causality, EWS backtest, alpha=0.3 校準 |

---

## 目錄結構

```
globeedge/
├── core/                    # 數學核心（零外部依賴）
│   ├── belief_state.py      #   BeliefState (frozen dataclass)
│   ├── fj_engine.py         #   Friedkin-Johnsen 引擎
│   ├── monte_carlo.py       #   MC runner + MoE 分層噪聲
│   ├── ews_monitor.py       #   MoE 多專家 EWS (Welford z-score)
│   └── distribution.py      #   SimulationDistribution (CI, percentile)
│
├── models/                  # SQLAlchemy ORM (7 實體)
│   ├── project.py           #   專案設定
│   ├── agent.py             #   Agent 節點
│   ├── influence_edge.py    #   W 矩陣邊 (含部分索引)
│   ├── issue_dimension.py   #   議題維度定義
│   ├── external_event.py    #   外部事件 (source_type 欄位)
│   ├── simulation_result.py #   仿真結果 (JSONB timesteps)
│   └── ews_alert.py         #   EWS 警報記錄
│
├── api/                     # Flask Blueprint
│   ├── projects.py          #   POST/GET/PATCH/DELETE /api/projects
│   ├── simulations.py       #   POST + status (Redis-first) + result
│   └── agents.py            #   POST agents + edges + matrix + AI estimate
│
├── services/                # 業務服務
│   └── belief_estimator.py  #   AI 輔助 b(0) 估計 (Ollama qwen3.5:9b)
│
├── crawler/                 # 輿論爬蟲（W 矩陣資料源）
│   ├── ptt_crawler.py       #   PTT 八卦/政黑板 (curl_cffi TLS)
│   ├── bluesky_crawler.py   #   Bluesky AT Protocol + 帳號探勘
│   ├── news_crawler.py      #   RSS + Crawl4AI 新聞引用
│   ├── financial_crawler.py #   金融文件 LLM (成本上限保護)
│   └── scheduler.py         #   APScheduler (PTT 8h, RSS 6h, Bluesky daily)
│
├── signals/                 # 地緣政治物理訊號（ExternalEvent）
│   ├── usgs_signal.py       #   台灣地震 (M≥4.5)
│   ├── gdelt_signal.py      #   GDELT 負面新聞 (rate limit 重試)
│   ├── impact_mapper.py     #   4 個靜態方法 → 8 維 impact_vector
│   └── signal_scheduler.py  #   USGS 1h + GDELT 6h
│
├── scenarios/               # 6 個議題情境
│   ├── base.py              #   Scenario / AgentDef / EventDef 基類
│   ├── energy.py            #   ①  台灣能源政策
│   ├── ai_regulation.py     #   ②  AI 監管與就業衝擊
│   ├── geopolitics.py       #   ③  地緣政治與戰亂溢出
│   ├── trade_war.py         #   ④  美中貿易戰 2.0
│   ├── iran_war.py          #   ⑤★ 美伊戰爭（即時議題）
│   └── recall.py            #   ⑥★ 全台大罷免潮（即時議題）
│
├── tasks/                   # Celery 仿真佇列
│   ├── celery_app.py
│   └── simulation_task.py
│
├── app.py                   # Flask 應用初始化
└── db.py                    # SQLAlchemy 實例

frontend/src/
├── views/                   # 7 個頁面
│   ├── ProjectListPage.vue  #   /projects — 專案管理
│   ├── DimensionPage.vue    #   /projects/:id/dimensions
│   ├── AgentDesignPage.vue  #   /projects/:id/agents (雷達圖 + AI 估計)
│   ├── EdgeDesignPage.vue   #   /projects/:id/edges (W 熱圖)
│   ├── EventDesignPage.vue  #   /projects/:id/events + Run Simulation
│   └── ResultDashboardPage.vue  # /dashboard — 結果展示
├── components/
│   ├── AgentRadarChart.vue  #   D3 雷達圖 (8 維)
│   ├── RiskGauge.vue        #   D3 弧形儀表
│   ├── EWSChart.vue         #   Observable Plot 時序圖
│   ├── BeliefChart.vue      #   Observable Plot 信念圖
│   └── ProgressBar.vue      #   仿真進度條
├── stores/
│   ├── projectStore.ts      #   專案/Agent/Edge/Event CRUD
│   └── simulationStore.ts   #   仿真提交+輪詢
└── lib/
    └── api.ts               #   API client

scripts/
├── start_api.py             # 啟動 Flask API
├── start_crawlers.py        # 啟動爬蟲 + 訊號排程
├── init_db.py               # 初始化 DB schema + 驗證
├── calibrate.py             # Granger Causality 校準
├── backtest.py              # EWS 歷史 backtest
└── run_scenario.py          # 議題情境仿真執行

tests/test_core/             # 47 個單元測試
├── test_belief_state.py     #   5 tests
├── test_distribution.py     #   6 tests
├── test_ews_monitor.py      #   15 tests (含 MoE)
├── test_fj_engine.py        #   9 tests
└── test_monte_carlo.py      #   12 tests (含 MoE 噪聲)
```

---

## 校準結果 (Phase 7)

### Granger Causality

| 歷史事件 | 顯著邊 (p<0.1) | 最佳 alpha | MSE |
|---|---|---|---|
| 花蓮 M7.2 地震 (2024-04) | 7 | 0.3 | 0.0077 |
| 台灣總統大選 (2024-01) | 5 | 0.3 | 0.0110 |
| 裴洛西訪台 (2022-08) | 13 | 0.3 | 0.0074 |

**核心發現：最佳 alpha = 0.3**（台灣社會個體固有信念權重高於社會影響）

### EWS Backtest

| 事件 | Variance 暴增倍率 | AUC | 顯著性 |
|---|---|---|---|
| 花蓮地震 | 16.5x | 563 | ✅ significant |
| 台灣大選 | 11.9x | 577 | ✅ significant |
| 裴洛西訪台 | 14.6x | 833 | ✅ significant |

---

## 六議題仿真結果

| # | 議題 | 類型 | λ_max | EWS 最高等級 | 最強極化維度 | spread |
|---|---|---|---|---|---|---|
| 5 | 美伊戰爭 | ★即時 | **0.791** | high | 經濟焦慮度 | 0.566 |
| 6 | 大罷免潮 | ★即時 | 0.752 | **critical** | 政府信任度 | **0.881** |
| 1 | 能源政策 | backtest | 0.760 | high | 核電接受度 | **1.015** |
| 2 | AI 監管 | backtest | 0.726 | high | AI監管支持度 | 0.812 |
| 3 | 地緣政治 | backtest | 0.745 | medium | 政府信任度 | 0.689 |
| 4 | 貿易戰 | backtest | 0.634 | medium | 對美信任度 | 0.483 |

---

## 服務運行狀態

| 服務 | 啟動方式 | 預設位址 |
|---|---|---|
| PostgreSQL | `docker compose up -d` | 127.0.0.1:5432 |
| Redis | `docker compose up -d` | 127.0.0.1:6379 |
| Flask API | `python scripts/start_api.py` | 0.0.0.0:5001 |
| 爬蟲+訊號排程 | `python scripts/start_crawlers.py` | 背景 (7 jobs) |
| Ollama LLM | 系統服務 | localhost:11434 |
| 前端 dev | `cd frontend && npm run dev` | localhost:5173 |

### 排程 Jobs

| Job ID | 頻率 | 資料源 |
|---|---|---|
| `news_crawler_daily` | 每天 02:00 | Crawl4AI 新聞 |
| `rss_crawler_6h` | 每 6 小時 | RSS |
| `ptt_crawler_8h` | 每 8 小時 | **PTT（主力）** |
| `bluesky_daily` | 每天 03:00 | Bluesky |
| `financial_daily` | 每天 04:00 | 金融 LLM |
| `usgs_hourly` | 每小時 | USGS 地震 |
| `gdelt_6h` | 每 6 小時 | GDELT 新聞 |

---

## 資料庫 (PostgreSQL)

| 表 | 說明 | 關鍵欄位 |
|---|---|---|
| `projects` | 專案設定 | alpha, mc_runs, sim_horizon |
| `agents` | Agent 節點 | type, domain, belief_init (FLOAT[]) |
| `influence_edges` | W 矩陣邊 | weight, weight_type, **partial index on valid_until IS NULL** |
| `issue_dimensions` | 議題維度 | index, name, range_min/max |
| `external_events` | 外部事件 | **source_type** (ais\|gdelt\|usgs\|adsb\|news), impact_vector (FLOAT[]) |
| `simulation_results` | 仿真結果 | **timesteps (JSONB)**, elapsed_sec |
| `ews_alerts` | EWS 警報 | alert_type, severity, z_score |

---

## 安全措施

| 項目 | 狀態 |
|---|---|
| `.env` 在 `.gitignore` | ✅ |
| `.claude/` 在 `.gitignore` | ✅ |
| git history 無 .env | ✅ |
| LLM 呼叫上限 (MAX=20/run) | ✅ |
| 月預算硬限 ($10 USD) | ✅ |
| PostgreSQL 綁定 localhost | ✅ |
| AIS 單一連線守護 | ✅ |

---

## 推薦參數

```python
PROJECT_DEFAULTS = {
    "alpha":       0.3,    # 台灣社會校準值
    "mc_runs":     10000,
    "sim_horizon": 30,
    "noise_level": 0.05,
}
```

---

## Git History

```
4339249  AI-assisted belief estimation via Ollama Qwen3.5
ae41ce9  Add project-state.md
7a3baf4  Rename project: WorldEdge → GlobeEdge
f3b848b  Frontend: full scenario design workflow (5 new pages)
1d69354  Add real-time scenarios: Iran war impact + Taiwan recall movement
ba7b306  Phase 3-7: crawlers, signals, MoE core, calibration, 4 scenario analyses
0a0a956  Initial commit
```
