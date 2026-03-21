# GlobeEdge TODO

## ✅ 已完成

### 核心系統
- [x] Phase 1-7 全部完成
- [x] 6 個議題情境（4 backtest + 2 即時）
- [x] Granger Causality 校準（alpha=0.3）
- [x] EWS backtest（3 事件全部 significant）
- [x] WorldEdge → GlobeEdge 重命名

### 心理機制（4 層全部完成）
- [x] Layer 1: Ebbinghaus 遺忘曲線（PTT S=2, 機構 S=25）
- [x] Layer 2: ELM 雙路徑說服（issue_involvement 欄位）
- [x] Layer 3: 動機性推理 Backfire Effect（W 矩陣修正）
- [x] Layer 4: System 1/2 雙歷程（message_analyzer + emotionality_tagger）

### AI 輔助
- [x] AI b(0) 估計（Ollama qwen3.5:9b, /no_think）
- [x] 訊息情緒性分析（message_analyzer.py）
- [x] PTT 情緒標記 → Redis（emotionality_tagger.py）

### 前端
- [x] 5 頁設計流程（專案→維度→Agent→邊→事件）
- [x] AgentRadarChart D3 雷達圖
- [x] W 矩陣熱圖
- [x] AI 估計按鈕 + slider 整合
- [x] WhatIfPage 反事實分析
- [x] 心理機制 checkboxes

### 安全 / 基礎
- [x] .env + .claude/ 在 .gitignore
- [x] LLM 成本上限（20/run, $10/month）
- [x] Docker PostgreSQL/Redis 綁定 localhost
- [x] 啟動腳本（start_api.py, start_crawlers.py）

---

## 🔲 待辦

### P0 — 即時驗證
- [ ] 議題 5 (美伊戰爭) 接入真實 PTT 資料作為 ground truth
- [ ] 議題 6 (大罷免) PTT 政黑板即時驗證
- [ ] 即時驗證框架：模型預測 vs 爬蟲真實資料比對腳本
- [ ] 心理機制 + What If 的組合實驗
  - 「啟用 Backfire 後，移除反核 KOL 的效果差多少？」

### P1 — 訊號層擴充
- [ ] AIS WebSocket 即時訊號 (aisstream.io)
- [ ] adsb.lol 軍機偵測
- [ ] aisstream 單一 WebSocket 連線實例守護

### P1 — 前端優化
- [ ] 雷達圖多 Agent 疊加比較
- [ ] EdgeDesignPage 力導向網絡圖
- [ ] WhatIfPage 結果用 Observable Plot 繪製差異圖
- [ ] Dark/light mode 切換

### P2 — 校準深化
- [ ] MoE W 矩陣分域（MoEInfluenceRouter, 需 ≥3 backtest）
- [ ] Pol.is vTaiwan 歷史資料接入
- [ ] 跨議題影響力結構比較報告
- [ ] alpha 議題特異性驗證（政治 alpha 更低？）
- [ ] 心理機制參數校準（用真實 PTT 時序資料）
  - Ebbinghaus S 值的議題特異性
  - Backfire identity_threshold 的最佳值

### P2 — 部署
- [ ] Cloudflare Tunnel（只暴露 :5001）
- [ ] 研究免責聲明
- [ ] JWT / API key 存取控制

### P3 — 長期研究
- [ ] 技術報告 / preprint
  - alpha=0.3 + 六議題跨比較 + 四層心理機制
- [ ] H3 混合假說驗證（alpha 雙峰分佈）
- [ ] 反身性問題研究聲明
- [ ] 多語言支援

---

## 爬蟲備忘
- [ ] ETtoday RSS URL 變更監控
- [ ] Bluesky TW_KOL_HANDLES 持續擴充（15 個手動策展）
- [ ] financial_crawler extract_belief_from_doc 整合
- [ ] PTT over18 cookie 失效時改用 headless browser
- [ ] emotionality_tagger 整合到 PTT 爬蟲排程流程
