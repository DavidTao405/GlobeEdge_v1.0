# GlobeEdge — Claude Code 指引

## 專案說明
社會信念動態世界模型（Friedkin-Johnsen + 心理學擴展）
詳見 GLOBEEDGE_PLAN.md

## 開發原則
- 數學核心 (core/) 零外部依賴，可獨立測試
- BeliefState 必須 frozen=True
- 每個 Phase 完成前先跑對應測試
- 心理機制 flags 預設 False，向後相容
- impact_vector 優先用 PTT 推噓結構校準（非研究者猜測）
- 介面設計請參考: https://www.ibm.com/design/language/

## Phase 完成狀態
- [x] Phase 1：數學核心（FJ, MC, EWS, Distribution）
- [x] Phase 2：資料模型 + API（7 ORM + Flask CRUD）
- [x] Phase 3：爬蟲層（PTT, Bluesky, RSS, 金融）
- [x] Phase 4：地緣政治訊號（USGS, GDELT, ImpactMapper）
- [x] Phase 5：仿真佇列 + GPU（Celery, torch.bmm）
- [x] Phase 6：前端儀表板（Vue 3 + Observable Plot + What If）
- [x] Phase 7：整合測試與校準（Granger, Backtest, alpha=0.3）

## 擴展完成
- [x] 心理機制 4 層（Ebbinghaus, ELM, Backfire, System 1/2）
- [x] CrisisAwareFJEngine（動態 alpha + 動態 b(0) + spread floor）
- [x] What If 反事實分析引擎
- [x] AI b(0) 估計（Ollama qwen3.5:9b）
- [x] 6 議題情境（能源, AI, 地緣, 貿易, 美伊★, 罷免★）
- [x] PTT 真實資料校準（柯文哲判決 + 鄭習會，推噓結構→impact_vector）

## 校準參數
- alpha: 0.3（台灣社會校準值，Phase 7 三事件一致）
- CrisisAwareFJEngine: alpha_base=0.3, alpha_crisis=0.6
- Spread floor: MIN_SPREAD=0.12
- 方向準確率: FJ 0% → CrisisAware 50%（美伊戰爭驗證）

## 環境
- Python 3.13.3, venv 在 .venv\
- Windows, PowerShell
- GPU: RTX 4070 SUPER
- DB: PostgreSQL 16 (Docker, volume=pgdata)
- Cache: Redis 7 (Docker)
- LLM: Ollama qwen3.5:9b (本機 localhost:11434)

## 常用指令
```bash
# 啟動 DB
docker compose up -d

# 測試
PYTHONPATH=. .venv/Scripts/python -m pytest tests/test_core/ -v

# 爬蟲排程（保持 PowerShell 開著）
PYTHONPATH=. .venv/Scripts/python scripts/start_crawlers.py

# Backfill PTT
PYTHONPATH=. .venv/Scripts/python scripts/backfill_ptt.py --board HatePolitics --board Gossiping --pages 50 --keywords "關鍵字1,關鍵字2"

# 情境仿真
PYTHONPATH=. .venv/Scripts/python scripts/run_scenario.py --scenario recall
```

## DB 注意
- Docker volume `pgdata` 持久化，重啟不丟資料
- `docker compose down` 安全，`docker compose down -v` 會清資料
- Redis port 6379 偶爾被 Windows Hyper-V 保留，需管理員 `net stop winnat && net start winnat`
