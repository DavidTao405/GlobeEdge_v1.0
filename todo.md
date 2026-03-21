# GlobeEdge TODO

## ✅ 已完成

### P0 — 安全與基礎
- [x] .env 在 .gitignore
- [x] .claude/ 在 .gitignore
- [x] git history 無敏感資料
- [x] LLM 呼叫上限 (MAX=20/run, $10/month)
- [x] docker-compose postgres/redis 綁定 127.0.0.1
- [x] financial_crawler.py 成本追蹤

### 核心功能
- [x] Phase 1-7 全部完成
- [x] 6 個議題情境（4 backtest + 2 即時）
- [x] Granger Causality 校準（alpha=0.3）
- [x] EWS backtest（3 事件全部 significant）
- [x] 前端 5 頁設計流程
- [x] AI 輔助 b(0) 估計（Ollama qwen3.5:9b）
- [x] 啟動腳本 (start_api.py, start_crawlers.py)
- [x] WorldEdge → GlobeEdge 重命名

---

## 🔲 待辦

### P0 — 即時議題驗證
- [ ] 議題 5 (美伊戰爭) 接入真實 PTT 資料作為即時 ground truth
- [ ] 議題 6 (大罷免) PTT 政黑板即時驗證
- [ ] 建立即時驗證框架：模型預測 vs 爬蟲真實資料的比對腳本

### P1 — 訊號層擴充
- [ ] AIS WebSocket 即時訊號接入 (aisstream.io)
- [ ] adsb.lol 軍機偵測接入
- [ ] aisstream 確保只有一個 WebSocket 連線實例

### P1 — 前端優化
- [ ] AgentDesignPage 雷達圖支援多 Agent 疊加比較
- [ ] EdgeDesignPage 網絡圖（力導向圖）替代或補充熱圖
- [ ] 前端 dark/light mode 切換按鈕

### P2 — 校準與分析
- [ ] MoE W 矩陣分域（MoEInfluenceRouter）
  - 需要：≥3 歷史事件 backtest 資料
  - 驗證：分域 W vs 全域 W 的預測誤差比較
- [ ] Pol.is vTaiwan 歷史資料接入校準 b(0)
- [ ] 跨議題影響力結構比較報告
- [ ] alpha 議題特異性驗證（政治議題 alpha 是否更低？）

### P2 — 部署與安全
- [ ] Cloudflare Tunnel 範圍控制：只暴露 Flask :5001
- [ ] 報告加上研究免責聲明
- [ ] 存取控制（JWT / API key）
- [ ] 資料敏感性分級文件

### P3 — 長期
- [ ] 發表技術報告 / preprint
  - 核心論點：alpha=0.3（台灣特有參數）+ 六議題跨比較
- [ ] 反身性問題研究聲明完善
- [ ] 多語言支援（英文介面）

---

## 爬蟲備忘

- [ ] ETtoday RSS URL 歷史上改過，如果 feedparser entries 為空需換備用 URL
- [ ] Bluesky TW_KOL_HANDLES 持續擴充（已有 15 個手動策展帳號）
- [ ] financial_crawler.py extract_belief_from_doc 實際整合
- [ ] PTT over18 cookie 若失效，需改用 headless browser

---

## Phase 7 補充

### MoE W 矩陣分域（暫緩）
- 實作 MoEInfluenceRouter
- 需要：至少 3 個歷史事件的 backtest 資料
- 驗證方式：分域 W vs 全域 W 的預測誤差比較
- 預計工作量：2 天

### /api/simulations/{id}/status
- 目前：Redis-first，沒有再查 DB
- Phase 5 Celery 接上後已實作
- 無 Celery 環境時 fallback 到 DB status 欄位
