# WorldEdge TODO

## P0 — 立刻確認
- [x] .env 在 .gitignore 裡
- [x] LLM 呼叫加上 MAX_CALLS 硬性上限 (20/run, $10/month)
- [x] docker-compose postgres 綁定 127.0.0.1（不暴露公網）
- [x] financial_crawler.py 成本追蹤（檔案式月度記錄）
- [ ] git init + 確認 .env 不在 history 中

## P1 — 近期處理
- [ ] aisstream 確保只有一個 WebSocket 連線實例（scheduler.py 已有 lock 機制）
- [x] `/api/simulations/{id}/status` Redis-first（Phase 5 完成）
- [x] Celery worker 整合：simulation task 寫 Redis `simulation:{id}:status`
- [ ] Cloudflare Tunnel 範圍控制：只暴露 Flask :5001，不暴露 DB/Redis/Flower

## P2 — 未來如果對外分享
- [ ] 報告加上研究免責聲明：「研究用途，不作為預測或操縱輿論的依據」
- [ ] 存取控制（JWT / API key）
- [ ] 資料敏感性分級
      - AIS 台海軍艦動態 → 軍事情資性質
      - GDELT 衝突事件 → 地緣政治資料
      - W 矩陣 → 揭示媒體影響力結構
      - 仿真結果 → 可能被解讀為輿論操縱建議

## Phase 7 待辦

### MoE W 矩陣分域
- 實作 MoEInfluenceRouter
- 需要：至少 3 個歷史事件的 backtest 資料
- 驗證方式：分域 W vs 全域 W 的預測誤差比較
- 預計工作量：2 天

## 爬蟲層備忘
- [ ] ETtoday RSS URL 歷史上改過幾次，如果 feedparser entries 為空需換備用 URL
- [ ] Bluesky TW_KOL_HANDLES 待擴充（目前台灣媒體帳號活躍度低）
- [ ] financial_crawler.py 金融文件爬取 + extract_belief_from_doc 實際整合
