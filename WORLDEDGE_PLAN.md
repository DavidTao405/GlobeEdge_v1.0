# WorldEdge 開發計畫

> 社會信念動態世界模型 — 個人研究用，本機部署
> 基於 Friedkin-Johnsen + Monte Carlo + Early Warning Signals

---

## 目錄

1. [專案概述](#1-專案概述)
2. [技術架構總覽](#2-技術架構總覽)
3. [開發環境設置](#3-開發環境設置)
4. [目錄結構](#4-目錄結構)
5. [資料來源策略](#5-資料來源策略)
6. [實作階段](#6-實作階段)
7. [資料模型](#7-資料模型)
8. [API 規格](#8-api-規格)
9. [核心抽象層](#9-核心抽象層)
10. [部署指令](#10-部署指令)
11. [測試策略](#11-測試策略)
12. [開發注意事項](#12-開發注意事項)
13. [研究限制聲明](#13-研究限制聲明)

---

## 1. 專案概述

### 是什麼

WorldEdge 是一個**社會信念動態世界模型引擎**。

- 輸入：台灣輿論種子資料 + 國際地緣政治物理訊號
- 輸出：**帶信心區間的系統狀態分佈** + **距離輿論失控臨界點的可量化距離**

### 不是什麼

- 不是 LLM 故事生成器
- 不是即時監控系統（批次週期性更新）
- 不預測「X 事件會發生」，只輸出「系統距臨界點多遠」

### 核心數學

```
Friedkin-Johnsen 模型（信念更新引擎）：
  b(t+1) = α * W @ b(t) + (1 - α) * b(0)

Monte Carlo（量化不確定性）：
  跑 N=10,000 次，每次加不同噪聲 → 輸出分佈而非單點

Early Warning Signals（臨界點偵測）：
  λ_max(W) → 1         : 系統接近臨界
  Variance 暴增         : 信念開始震盪
  CSD (Critical Slowing Down) : 恢復速度變慢
```

---

## 2. 技術架構總覽

```
┌──────────────────────────────────────────────┐
│  本機 Windows 主機                            │
│                                              │
│  ┌──────────┐   ┌───────────────────────┐   │
│  │ Vue 3    │   │  Flask API :5001       │   │
│  │ :3000    │──▶│                        │   │
│  └──────────┘   └───────────┬────────────┘   │
│                             │                │
│               ┌─────────────┼──────────┐     │
│               ▼             ▼          ▼     │
│         ┌──────────┐  ┌──────┐  ┌──────────┐│
│         │PostgreSQL│  │Redis │  │  Celery  ││
│         └──────────┘  └──────┘  └────┬─────┘│
│                                      ▼      │
│                             ┌──────────────┐ │
│                             │ Sim Worker   │ │
│                             │ RTX 4070S    │ │
│                             └──────────────┘ │
│                                              │
│  ┌──────────────┐   ┌──────────────────────┐ │
│  │ crawler/     │   │ signals/             │ │
│  │ 輿論爬蟲     │   │ 地緣政治物理訊號      │ │
│  │ APScheduler  │   │ AIS+GDELT+USGS+ADSB  │ │
│  └──────────────┘   └──────────────────────┘ │
└──────────────────────────────────────────────┘
```

### 技術選型

| 層級 | 技術 | 理由 |
|------|------|------|
| 後端 | Python 3.11 + Flask | 熟悉，科學計算生態完整 |
| 仿真 | NumPy + PyTorch | GPU batching，Monte Carlo 加速 |
| 資料庫 | PostgreSQL 16 | 穩定，與既有環境一致 |
| 佇列 | Celery + Redis | 仿真非同步執行 |
| 輿論爬蟲 | Crawl4AI + Scrapling | LLM-ready 輸出 + 反爬能力 |
| 地緣訊號 | Shadowbroker 資料管道邏輯 | AIS + GDELT + USGS 已整合 |
| 前端 | Vue 3 + TypeScript + ECharts | 熟悉技術棧 |
| 部署 | Docker Compose | 單指令啟動 |

---

## 3. 開發環境設置

### 前置需求

```bash
python --version      # 需要 3.11+
node --version        # 需要 18+
docker --version
nvidia-smi            # 確認 GPU 可用
```

### 初始化專案

```bash
mkdir worldedge && cd worldedge
git init

# Python 虛擬環境
python -m venv .venv
.venv\Scripts\activate        # Windows

# 安裝 Python 依賴
pip install flask flask-sqlalchemy psycopg2-binary \
            celery redis \
            numpy torch \
            crawl4ai scrapling \
            apscheduler websockets aiohttp \
            pydantic python-dotenv

# 安裝爬蟲瀏覽器
crawl4ai-setup
scrapling install

# 前端
mkdir frontend && cd frontend
npm create vue@latest . -- --typescript --router --pinia
npm install echarts vue-echarts
cd ..
```

### 環境變數 `.env`

```bash
# 資料庫
WE_DB_URL=postgresql://postgres:password@localhost:5432/worldedge

# Redis
WE_REDIS_URL=redis://localhost:6379/0

# LLM（報告生成用）
WE_LLM_API_KEY=your_api_key
WE_LLM_BASE_URL=https://api.anthropic.com
WE_LLM_MODEL=claude-sonnet-4-20250514

# 仿真預設參數
WE_DEFAULT_ALPHA=0.6
WE_DEFAULT_MC_RUNS=10000
WE_DEFAULT_NOISE=0.05
WE_DEVICE=cuda

# 地緣政治資料源（免費）
AISSTREAM_API_KEY=your_aisstream_key    # aisstream.io 免費方案申請

# Flask
FLASK_ENV=development
FLASK_DEBUG=1
```

---

## 4. 目錄結構

```
worldedge/
├── .env
├── .gitignore
├── docker-compose.yml
├── PLAN.md
│
├── worldedge/
│   ├── core/                  ← 數學核心（零外部依賴）
│   │   ├── belief_state.py
│   │   ├── fj_engine.py
│   │   ├── monte_carlo.py
│   │   ├── distribution.py
│   │   └── ews_monitor.py
│   │
│   ├── service/
│   │   ├── simulation_service.py
│   │   ├── report_generator.py
│   │   └── w_matrix_builder.py
│   │
│   ├── ports/                 ← Protocol 定義（依賴反轉）
│   │   ├── memory_protocol.py
│   │   └── governor_protocol.py
│   │
│   ├── api/                   ← Flask blueprints
│   │   ├── projects.py
│   │   ├── agents.py
│   │   ├── simulations.py
│   │   ├── alerts.py
│   │   └── data.py
│   │
│   ├── models/                ← SQLAlchemy ORM
│   │   ├── project.py
│   │   ├── agent.py
│   │   ├── influence_edge.py
│   │   ├── issue_dimension.py
│   │   ├── external_event.py
│   │   ├── simulation_result.py
│   │   └── ews_alert.py
│   │
│   ├── crawler/               ← 台灣輿論爬蟲（W 矩陣）
│   │   ├── news_crawler.py       # Crawl4AI，新聞媒體引用關係
│   │   ├── forum_crawler.py      # Scrapling，PTT/Dcard
│   │   ├── financial_crawler.py  # 法說會逐字稿
│   │   ├── bluesky_crawler.py    # AT Protocol，免費公開 API
│   │   ├── polis_crawler.py      # vTaiwan Pol.is 立場資料
│   │   └── scheduler.py
│   │
│   ├── signals/               ← 地緣政治物理訊號（ExternalEvent）
│   │   ├── ais_signal.py      # AIS 台海軍艦 → 外部威脅感知
│   │   ├── gdelt_signal.py    # GDELT 台灣相關衝突事件
│   │   ├── usgs_signal.py     # USGS 台灣地震
│   │   ├── military_flight.py # adsb.lol 軍機偵測
│   │   ├── impact_mapper.py   # 物理訊號 → impact_vector 轉換
│   │   └── signal_scheduler.py
│   │
│   └── tasks/
│       └── simulation_task.py
│
├── tests/
│   ├── test_core/
│   ├── test_signals/          ← impact_mapper 單元測試
│   └── test_api/
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── ProjectListPage.vue
│       │   ├── ProjectDetailPage.vue
│       │   ├── SimulationRunPage.vue
│       │   └── ResultDashboardPage.vue
│       ├── components/
│       │   ├── RiskGauge.vue
│       │   ├── BeliefChart.vue
│       │   ├── EWSChart.vue
│       │   ├── AlertPanel.vue
│       │   └── OutputSwitcher.vue
│       ├── stores/
│       │   ├── projectStore.ts
│       │   ├── simulationStore.ts
│       │   ├── alertStore.ts
│       │   └── uiStore.ts
│       └── services/api.ts
│
└── scripts/
    ├── init_db.py
    └── seed_dimensions.py
```

---

## 5. 資料來源策略

### 設計原則

每個資料源必須直接貢獻以下其中一項，否則剔除：

```
① W 矩陣邊（影響力關係）
② Agent 的 b(0)（初始信念向量）
③ ExternalEvent 的 impact_vector（外部衝擊）
```

### 全圖

```
┌──────────────────────────────────────────────────────┐
│  台灣輿論層 → W 矩陣 + b(0)                           │
│                                                      │
│  新聞媒體引用   →  W 骨架            Crawl4AI + BM25  │
│  PTT / Dcard   →  W 校準            Scrapling        │
│  Bluesky       →  W 補充（意見領袖） AT Protocol API  │
│  法說會逐字稿  →  b(0) 金融         Crawl4AI + LLM   │
│  Pol.is/vTaiwan →  b(0) 直接立場資料  公開 API        │
└──────────────────────────────────────────────────────┘
              ↓ ExternalEvent e(t) 注入仿真引擎
┌──────────────────────────────────────────────────────┐
│  國際地緣政治層 → ExternalEvent                       │
│                                                      │
│  AIS 台海軍艦  →  外部威脅感知   aisstream.io         │
│  adsb.lol 軍機 →  外部威脅感知   免費，無需 key       │
│  GDELT 事件    →  多維度衝擊     gdeltproject.org     │
│  USGS 地震     →  經濟焦慮衝擊   earthquake.usgs.gov  │
└──────────────────────────────────────────────────────┘
```

### 明確剔除（及理由）

| 來源 | 剔除理由 |
|------|---------|
| Facebook / Instagram | API 設計上不開放第三方研究存取，無合規路徑 |
| X（Twitter） | 2023 年後 API 改為付費制，個人研究負擔不起（$5,000/月起）|
| WorldMonitor | 直接用其上游，不繞道聚合器 |
| Shadowbroker 前端 | 只借資料管道邏輯，前端完全不要 |
| GPS 干擾偵測 | 訊號與輿論關聯難校準，二期再評估 |
| 衛星追蹤 N2YO | 與台灣輿論無直接因果關係 |
| CCTV 攝影機 | 完全無關 |
| 航母打擊群 OSINT | 粒度太粗，GDELT 已涵蓋相關事件 |
| 私人飛機追蹤 | 無關 |

> **注意**：FB 和 IG 是台灣最主要的輿論場域，X 上有大量政治意見領袖，
> 這個缺口在台灣輿論研究領域是結構性的限制，所有做此題目的研究者都面對同樣問題。
> 本研究以 Bluesky（開放 API）、PTT/Dcard、新聞媒體資料作為可及的替代，
> 並在研究結論中明確聲明此限制對模型代表性的影響。詳見第 13 節。

### 各資料源規格

#### 新聞媒體引用關係（Crawl4AI）

```
用途：W 骨架（weight_type = structural）
頻率：每天凌晨 2:00
目標：聯合報、自由時報、中央社、商業周刊、天下、ETtoday、三立
```

```python
# crawler/news_crawler.py

NEWS_SOURCES = [
    "https://www.udn.com",
    "https://www.ltn.com.tw",
    "https://www.cna.com.tw",
    "https://www.businessweekly.com.tw",
    "https://www.cw.com.tw",
    "https://www.ettoday.net",
    "https://news.setn.com",
]

async def crawl_citations(url: str) -> list[dict]:
    config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=BM25ContentFilter(
                user_query="引用 報導 轉載 據 根據 指出",
                bm25_threshold=1.0
            )
        )
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)
        return extract_citation_edges(result.markdown)
```

#### PTT / Dcard 互動（Scrapling）

```
用途：W 動態校準（weight_type = behavioral）
頻率：每 6 小時
目標版面：PTT 八卦、政治、股票；Dcard 時事
備用：Nodriver（若 Scrapling 被擋時切換）

校準邏輯：
  A 的發文 → B 的態度改變
  時序前後對比 → Granger Causality → W 更新
```

#### Bluesky（AT Protocol 公開 API）

```
用途：W 補充（意見領袖節點，weight_type = behavioral）
頻率：每 6 小時
工具：AT Protocol HTTP API，無需 API key（搜尋功能需免費 App Password）
目標：台灣政治、媒體、公民社會帳號

為何納入：
  2024 年底 X 出走潮後，台灣媒體人、立委、公民記者大量遷移至 Bluesky
  這批人正是輿論意見領袖，在 PTT 幾乎看不到他們
  AT Protocol 完全開放，是目前唯一合法且免費的類 Twitter 資料來源
```

```python
# crawler/bluesky_crawler.py

import httpx

BSKY_PUBLIC_API = "https://public.api.bsky.app/xrpc"

# 台灣重點追蹤帳號（KOL 節點，細粒度 Agent）
TW_KOL_HANDLES = [
    # 在此填入遷移至 Bluesky 的台灣媒體人、立委、意見領袖 handle
    # 例："xxx.bsky.social"
]

async def fetch_kol_posts(handle: str, limit: int = 50) -> list[dict]:
    """爬取特定帳號的貼文，抽取互動關係"""
    r = await httpx.get(
        f"{BSKY_PUBLIC_API}/app.bsky.feed.getAuthorFeed",
        params={"actor": handle, "limit": limit}
    )
    return r.json().get("feed", [])

async def search_taiwan_posts(query: str, limit: int = 100) -> list[dict]:
    """搜尋台灣相關貼文（需 App Password）"""
    # App Password 免費申請：Bluesky 設定 → 應用程式密碼
    r = await httpx.get(
        f"{BSKY_PUBLIC_API}/app.bsky.feed.searchPosts",
        params={"q": query, "limit": limit, "lang": "zh"},
        headers={"Authorization": f"Bearer {config.BSKY_APP_PASSWORD}"}
    )
    return r.json().get("posts", [])

def extract_influence_edges(posts: list[dict]) -> list[dict]:
    """從回覆和轉發關係抽取 W 矩陣邊"""
    edges = []
    for item in posts:
        post = item.get("post", {})
        reply = post.get("record", {}).get("reply")
        if reply:
            # A 回覆 B → B 對 A 有影響力
            edges.append({
                "source": reply.get("parent", {}).get("uri", ""),
                "target": post.get("author", {}).get("handle", ""),
                "type": "reply",
                "weight_raw": 1,
            })
    return edges
```

#### Pol.is / vTaiwan 立場資料

```
用途：b(0) 初始信念向量的直接校準材料（最高品質的輸入）
頻率：一次性歷史資料匯入 + 監控新議題
來源：https://pol.is（開放 API）+ vTaiwan GitHub 歷史資料
      https://github.com/g0v/vtaiwan.tw

為何特別有價值：
  Pol.is 的資料不是情緒表達，而是結構化立場投票
  每個參與者對每個命題明確表示同意/不同意
  這直接對應信念向量的每個維度，不需要 LLM 推斷
  台灣已有多個重大議題的 Pol.is 歷史資料（Uber 監管、勞基法等）
```

```python
# crawler/polis_crawler.py

import httpx

POLIS_API = "https://pol.is/api/v3"

async def fetch_conversation_votes(conversation_id: str) -> dict:
    """
    取得一個議題的所有投票資料
    conversation_id 從 vTaiwan 歷史記錄取得
    """
    r = await httpx.get(
        f"{POLIS_API}/participantStats",
        params={"conversation_id": conversation_id}
    )
    return r.json()

async def fetch_comment_stats(conversation_id: str) -> list[dict]:
    """取得每個命題的同意/不同意比例"""
    r = await httpx.get(
        f"{POLIS_API}/comments",
        params={"conversation_id": conversation_id, "include_voting_patterns": True}
    )
    return r.json()

def polis_to_belief_vector(comment_stats: list[dict],
                            dimension_map: dict) -> list[float]:
    """
    把 Pol.is 命題投票結果轉換成 b(0) 信念向量
    dimension_map: {"命題關鍵字": 維度 index}

    例：
      "我支持政府對 Uber 加強監管" → 維度 4（政策支持度）
      同意率 60% → b[4] = 0.2（正規化：60% → +0.2）
    """
    vector = [0.0] * 8
    for comment in comment_stats:
        text = comment.get("txt", "")
        agree_rate = comment.get("agrees", 0) / max(comment.get("total", 1), 1)
        # 正規化：0% → -1.0, 50% → 0.0, 100% → +1.0
        normalized = (agree_rate - 0.5) * 2

        for keyword, dim_idx in dimension_map.items():
            if keyword in text:
                vector[dim_idx] = round(normalized, 3)
                break

    return vector

# vTaiwan 已公開的歷史議題（可直接爬取校準用）
VTAIWAN_CONVERSATIONS = {
    "uber":         "8f3n4h",   # Uber 監管
    "fintech":      "fnc9zt",   # 金融科技
    "alcohol_sale": "7crtw9",   # 酒類網路販售
    # 更多從 https://github.com/g0v/vtaiwan.tw 取得
}
```

#### 法說會逐字稿（Crawl4AI）

```
用途：金融 Agent 的 b(0)（維度 3、4）
頻率：工作日盤後 18:00
來源：MOPS 公開法說會逐字稿

LLM 角色：只填數字，不造維度
  prompt: "估計這份法說會中市場對[政策支持度/經濟焦慮度]的態度，
           回傳 -1 到 1 的數值"
```

#### AIS 台海軍艦（aisstream.io）

```
用途：ExternalEvent → 外部威脅感知（維度 7）
工具：借用 Shadowbroker ais_stream.py 的 WebSocket 邏輯
      去掉：地圖渲染、全球追蹤
      保留：台灣海峽範圍過濾 + 軍艦計數
偵測：台灣海峽 200km 範圍，軍艦 ≥ 3 艘才產生事件
費用：aisstream.io 免費方案
```

```python
# signals/ais_signal.py

TAIWAN_STRAIT_BOUNDS = {
    "lat_min": 21.5, "lat_max": 27.0,
    "lon_min": 118.0, "lon_max": 124.0,
}
MILITARY_VESSEL_TYPES = {8, 9}

class AISSignalMonitor:
    """
    借用 Shadowbroker ais_stream.py WebSocket 連接邏輯
    前端地圖完全不要
    """
    async def monitor(self, on_event):
        async with websockets.connect("wss://stream.aisstream.io/v0/stream") as ws:
            await ws.send(json.dumps({
                "APIKey": self.api_key,
                "BoundingBoxes": [[
                    [TAIWAN_STRAIT_BOUNDS["lat_min"],
                     TAIWAN_STRAIT_BOUNDS["lon_min"]],
                    [TAIWAN_STRAIT_BOUNDS["lat_max"],
                     TAIWAN_STRAIT_BOUNDS["lon_max"]],
                ]]
            }))
            async for raw in ws:
                self._update_vessels(json.loads(raw))
                if self._should_emit_event():   # 每小時評估一次
                    event = self._to_external_event()
                    if event:
                        await on_event(event)

    def _to_external_event(self) -> ExternalEvent | None:
        military = [v for v in self._vessels.values()
                    if v.get("type") in MILITARY_VESSEL_TYPES]
        if len(military) < 3:
            return None
        t = min(len(military) / 20, 1.0)
        return ExternalEvent(
            title=f"台海軍事活動：{len(military)} 艘軍艦",
            domain="geopolitical",
            source_type="ais",
            impact_vector=[0, 0, 0,
                           round(t*0.3, 3),   # 經濟焦慮
                           round(-t*0.2, 3),  # 政策支持度
                           0,
                           round(-t*0.1, 3),  # 群體凝聚度
                           round(t, 3)],      # 外部威脅感知
        )
```

#### GDELT 台灣相關事件

```
用途：ExternalEvent → 多維度衝擊
頻率：每 6 小時
API：https://api.gdeltproject.org/api/v2/doc/doc（完全免費）
借用：Shadowbroker geopolitics.py 的查詢清洗邏輯
過濾：tone < -3（排除中性報導）
```

#### USGS 台灣地震

```
用途：ExternalEvent → 經濟焦慮衝擊（維度 3）
頻率：每小時
API：earthquake.usgs.gov（完全免費）
過濾：台灣範圍 + 規模 ≥ 4.5
```

#### adsb.lol 軍機偵測

```
用途：ExternalEvent → 外部威脅感知（AIS 的空中補充）
頻率：每小時 HTTP polling
API：https://api.adsb.lol/v2/mil（完全免費，無需 key）
借用：Shadowbroker data_fetcher.py 的端點邏輯
過濾：台灣 ADIZ 範圍內軍機數量異常
```

#### impact_mapper.py — 統一轉換介面

所有物理訊號轉 impact_vector 的邏輯集中在這一個檔案：

```python
# signals/impact_mapper.py

class ImpactMapper:
    """
    設計原則：
    - 每個維度的影響方向有明確的社會科學依據
    - 數值有上限，避免單一事件主宰整個仿真
    - 長期效應用 decay_rate 控制，不直接修改 W
    """

    @staticmethod
    def military_vessels(count: int) -> list[float]:
        t = min(count / 20, 1.0)
        return [0, 0, 0, t*0.3, -t*0.2, 0, -t*0.1, t]

    @staticmethod
    def earthquake(magnitude: float) -> list[float]:
        t = min(max(0, (magnitude - 4.5) / 3.0), 1.0)
        return [0, -t*0.3, 0, t*0.6, -t*0.1, 0, -t*0.2, 0]

    @staticmethod
    def military_flights(count: int, in_adiz: bool) -> list[float]:
        t = min(count / 10, 1.0) * (1.5 if in_adiz else 1.0)
        t = min(t, 1.0)
        return [0, 0, 0, t*0.2, -t*0.15, 0, 0, t*0.7]

    @staticmethod
    def gdelt_article(title: str, tone: float) -> list[float]:
        intensity = min(abs(tone) / 10, 1.0)
        vector = [0.0] * 8
        title_l = title.lower()
        if any(w in title_l for w in
               ["military", "war", "attack", "軍", "攻", "衝突"]):
            vector[7] += intensity * 0.8
            vector[3] += intensity * 0.3
        if any(w in title_l for w in
               ["economy", "stock", "trade", "經濟", "股", "貿易"]):
            vector[3] += intensity * 0.6
            vector[4] -= intensity * 0.2
        if any(w in title_l for w in
               ["election", "government", "policy", "選", "政", "政策"]):
            vector[0] -= intensity * 0.4
            vector[4] += intensity * 0.2
        return [round(min(max(v, -1.0), 1.0), 3) for v in vector]
```

---

## 6. 實作階段

### Phase 1：數學核心

**目標**：FJ 引擎跑起來並通過測試。

**預計時間**：2-3 天

**belief_state.py**：

```python
@dataclass(frozen=True)
class BeliefState:
    t:         int
    B:         np.ndarray    # (n_agents, n_dims)
    W:         np.ndarray    # (n_agents, n_agents)
    timestamp: datetime

    def lambda_max(self) -> float:
        return float(np.max(np.linalg.eigvals(self.W).real))

    def variance(self) -> float:
        return float(self.B.var())
```

**fj_engine.py**：

```python
class FJEngine:
    def __init__(self, alpha: float, b0: np.ndarray):
        assert 0 < alpha < 1
        self.alpha = alpha
        self.b0 = b0

    def step(self, state, event=None, noise=0.0):
        B_next = (self.alpha * state.W @ state.B
                  + (1 - self.alpha) * self.b0)
        if event is not None:
            B_next += event
        if noise > 0:
            B_next += np.random.normal(0, noise, B_next.shape)
        return BeliefState(t=state.t+1,
                           B=np.clip(B_next, -1.0, 1.0),
                           W=state.W,
                           timestamp=datetime.now())

    def run(self, initial, horizon, events={}, noise=0.0):
        trajectory = [initial]
        state = initial
        for t in range(1, horizon + 1):
            state = self.step(state, event=events.get(t), noise=noise)
            trajectory.append(state)
        return trajectory
```

**ews_monitor.py（Welford）**：

```python
class EWSMonitor:
    def __init__(self, thresholds: dict):
        self.thresholds = thresholds
        self._n = 0
        self._mean: dict = {}
        self._M2: dict = {}

    def update(self, metrics: dict) -> list:
        alerts = []
        for key, value in metrics.items():
            z = self._welford_update(key, value)
            alert = self._check(key, value, z)
            if alert:
                alerts.append(alert)
        return alerts

    def _welford_update(self, key, value) -> float:
        if key not in self._mean:
            self._mean[key] = 0.0
            self._M2[key] = 0.0
        self._n += 1
        delta = value - self._mean[key]
        self._mean[key] += delta / self._n
        self._M2[key] += delta * (value - self._mean[key])
        if self._n < 10:
            return 0.0
        std = (self._M2[key] / (self._n - 1)) ** 0.5 + 1e-9
        return (value - self._mean[key]) / std
```

**驗收測試**：

```python
def test_fj_convergence():
    n, d = 5, 8
    W = np.random.dirichlet(np.ones(n), size=n)
    b0 = np.random.uniform(-1, 1, (n, d))
    engine = FJEngine(alpha=0.7, b0=b0)
    trajectory = engine.run(
        BeliefState(0, b0.copy(), W, datetime.now()), horizon=100
    )
    assert np.var([s.B for s in trajectory[-10:]], axis=0).max() < 0.01

def test_event_injection():
    event = np.zeros((5, 8))
    event[:, 7] = 0.5    # 外部威脅感知 +0.5
    state_after = engine.step(initial_state, event=event)
    assert state_after.B[:, 7].mean() > initial_state.B[:, 7].mean()

def test_impact_mapper_bounds():
    for count in [1, 5, 10, 20, 50]:
        v = ImpactMapper.military_vessels(count)
        assert all(-1 <= x <= 1 for x in v)
```

---

### Phase 2：資料模型與 API 骨架

**預計時間**：3-4 天

**議題維度預設值（seed_dimensions.py）**：

```python
UNIVERSAL_DIMENSIONS = [
    {"index": 0, "name": "政府信任度",   "range_min": -1, "range_max": 1},
    {"index": 1, "name": "制度公信力",   "range_min": -1, "range_max": 1},
    {"index": 2, "name": "社會公平感",   "range_min": -1, "range_max": 1},
    {"index": 3, "name": "經濟焦慮度",   "range_min": -1, "range_max": 1},
    {"index": 4, "name": "政策支持度",   "range_min": -1, "range_max": 1},  # 可覆蓋
    {"index": 5, "name": "變革意願",     "range_min": -1, "range_max": 1},  # 可覆蓋
    {"index": 6, "name": "群體凝聚度",   "range_min":  0, "range_max": 1},
    {"index": 7, "name": "外部威脅感知", "range_min":  0, "range_max": 1},
]
# 維度 4、5 可被專案層覆蓋（例如「核電接受度」、「綠能轉型意願」）
```

---

### Phase 3：爬蟲層與 W 矩陣構建

**預計時間**：5-7 天

```
Step 1：Crawl4AI 爬台灣新聞 → 引用關係 → W 骨架
Step 2：Scrapling 爬 PTT → Granger Causality → W 校準
Step 3：LLM 從法說會填 b(0)
Step 4：W 矩陣正規化（行和 ≤ 1）
```

---

### Phase 4：地緣政治訊號整合

**預計時間**：3-4 天

**signal_scheduler.py**：

```python
scheduler = AsyncIOScheduler()

# GDELT：每 6 小時
@scheduler.scheduled_job('interval', hours=6)
async def fetch_gdelt():
    events = await GDELTSignal().fetch(hours=6)
    await db.bulk_insert_events(events)

# USGS 地震：每小時
@scheduler.scheduled_job('interval', hours=1)
async def fetch_quakes():
    events = await USGSSignal().fetch(min_magnitude=4.5)
    await db.bulk_insert_events(events)

# adsb.lol 軍機：每小時
@scheduler.scheduled_job('interval', hours=1)
async def fetch_military_flights():
    event = await MilitaryFlightSignal().check_adiz()
    if event:
        await db.insert_event(event)

# AIS 台海軍艦：持續 WebSocket（在 AISSignalMonitor 內部控制觸發頻率）
async def start_ais():
    monitor = AISSignalMonitor(api_key=config.AISSTREAM_API_KEY)
    await monitor.monitor(on_event=db.insert_event)
```

**借用 Shadowbroker 的部分（只借邏輯，不借前端）**：

```
signals/ais_signal.py
  ← Shadowbroker: backend/services/ais_stream.py
     保留：WebSocket 連接、台灣海峽過濾、軍艦計數
     去掉：地圖渲染、全球追蹤、船隻分類顯示

signals/gdelt_signal.py
  ← Shadowbroker: backend/services/geopolitics.py
     保留：GDELT 查詢、tone 過濾、台灣關鍵字
     去掉：衝突熱點地圖、Region Dossier

signals/military_flight.py
  ← Shadowbroker: backend/services/data_fetcher.py
     保留：adsb.lol 端點、ADIZ 範圍過濾、數量計算
     去掉：全球軍機地圖、飛行軌跡
```

---

### Phase 5：仿真佇列與 GPU 加速

**預計時間**：2-3 天

```python
# tasks/simulation_task.py

@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3900)
def run_simulation(self, simulation_id: str):
    redis_client = get_redis()
    def on_progress(pct):
        redis_client.setex(f"simulation:{simulation_id}:status", 86400,
                           json.dumps({"status": "running", "progress": pct}))
    try:
        result = SimulationService(...).run_sync(
            simulation_id, on_progress=on_progress
        )
        redis_client.setex(f"simulation:{simulation_id}:result", 604800,
                           result.model_dump_json())
        redis_client.setex(f"simulation:{simulation_id}:status", 86400,
                           json.dumps({"status": "completed", "progress": 1.0}))
    except Exception as exc:
        redis_client.setex(f"simulation:{simulation_id}:status", 86400,
                           json.dumps({"status": "failed", "error": str(exc)}))
        raise self.retry(exc=exc)
```

**GPU batching**：

```python
def run_gpu(self, initial, horizon, noise_level=0.05):
    B = torch.tensor(initial.B, dtype=torch.float32, device=self.device)
    B = B.unsqueeze(0).expand(self.n_runs, -1, -1).clone()
    B += torch.randn_like(B) * noise_level * 0.5

    W = torch.tensor(initial.W, dtype=torch.float32, device=self.device)
    W = W.unsqueeze(0).expand(self.n_runs, -1, -1).clone()
    W = torch.clamp(W + torch.randn_like(W) * noise_level * 0.2, 0, 1)

    B0 = torch.tensor(self.engine.b0, dtype=torch.float32,
                      device=self.device).unsqueeze(0).expand(self.n_runs, -1, -1)

    all_B = [B.cpu().numpy()]
    for _ in range(horizon):
        B = torch.clamp(
            self.engine.alpha * torch.bmm(W, B)
            + (1 - self.engine.alpha) * B0,
            -1.0, 1.0
        )
        all_B.append(B.cpu().numpy())
    return SimulationDistribution(np.array(all_B).transpose(1, 0, 2, 3))
```

---

### Phase 6：前端儀表板

**預計時間**：3-4 天

**simulationStore.ts**：

```typescript
export const useSimulationStore = defineStore('simulation', () => {
    const result     = ref<SimulationResult | null>(null)
    const status     = ref<'idle'|'queued'|'running'|'completed'>('idle')
    const progress   = ref(0)
    const outputMode = ref<'dashboard'|'report'|'api'>('dashboard')

    async function submit(projectId: string) {
        status.value = 'queued'
        const { simulation_id } = await api.post('/simulations',
                                                 { project_id: projectId })
        await _poll(simulation_id)
    }

    async function _poll(simId: string) {
        status.value = 'running'
        while (true) {
            const s = await api.get(`/simulations/${simId}/status`)
            progress.value = s.progress
            if (s.status === 'completed') {
                result.value = await api.get(`/simulations/${simId}/result`)
                status.value = 'completed'
                return
            }
            if (s.status === 'failed') throw new Error(s.error)
            await new Promise(r => setTimeout(r, 3000))
        }
    }

    return { result, status, progress, outputMode, submit }
})
```

---

### Phase 7：整合測試與校準

**預計時間**：3-5 天

```
1. 選 3-5 個歷史事件（2021 萊豬、2024 選舉、重大地震）
2. Granger Causality 反推歷史 W
3. 驗證 EWS 指標在事件前是否出現預警
4. 調整 α 和 noise_level
5. 驗證 impact_vector 方向正確（台海軍演 → 外部威脅感知上升）
```

---

## 7. 資料模型

```sql
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    description TEXT,
    alpha       FLOAT DEFAULT 0.6,
    mc_runs     INT DEFAULT 10000,
    noise_level FLOAT DEFAULT 0.05,
    sim_horizon INT DEFAULT 30,
    time_step   TEXT DEFAULT 'day',
    status      TEXT DEFAULT 'draft',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES projects(id),
    name        TEXT NOT NULL,
    type        TEXT,   -- media | forum | kol | demographic | institution
    domain      TEXT,   -- news | social | financial | government
    belief_init FLOAT[],
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE influence_edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES projects(id),
    source_id   UUID REFERENCES agents(id),
    target_id   UUID REFERENCES agents(id),
    weight      FLOAT NOT NULL,
    weight_type TEXT,   -- structural | behavioral | semantic
    confidence  FLOAT DEFAULT 0.5,
    valid_from  TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,    -- NULL = 目前有效
    decay_rate  FLOAT DEFAULT 0.1
);

CREATE INDEX idx_edges_valid ON influence_edges (project_id, valid_until)
    WHERE valid_until IS NULL;

CREATE TABLE issue_dimensions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES projects(id),   -- NULL = 通用維度
    index       INT NOT NULL,
    name        TEXT NOT NULL,
    range_min   FLOAT DEFAULT -1,
    range_max   FLOAT DEFAULT 1,
    layer       TEXT DEFAULT 'universal'
);

CREATE TABLE external_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    description   TEXT,
    occurred_at   TIMESTAMPTZ NOT NULL,
    domain        TEXT,       -- geopolitical | domestic | financial | natural
    source_type   TEXT,       -- ais | gdelt | usgs | adsb | news
    impact_vector FLOAT[],
    source_url    TEXT,
    source_tier   INT DEFAULT 2,
    gdelt_id      TEXT
);

CREATE TABLE simulation_results (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID REFERENCES projects(id),
    run_at         TIMESTAMPTZ DEFAULT NOW(),
    mc_runs_actual INT,
    timesteps      JSONB,
    audit_log_id   TEXT
);

CREATE TABLE ews_alerts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID REFERENCES projects(id),
    result_id    UUID REFERENCES simulation_results(id),
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    timestep     INT,
    alert_type   TEXT,   -- lambda_max | variance | csd | convergence
    severity     TEXT,   -- low | medium | high | critical
    metric_value FLOAT,
    threshold    FLOAT,
    z_score      FLOAT,
    description  TEXT,
    acknowledged BOOL DEFAULT FALSE
);
```

---

## 8. API 規格

```
POST   /api/projects
GET    /api/projects
GET    /api/projects/{id}
PATCH  /api/projects/{id}
DELETE /api/projects/{id}

POST   /api/agents
POST   /api/agents/batch
GET    /api/agents/batch/{job_id}
GET    /api/agents/{id}
POST   /api/agents/edges
PUT    /api/agents/edges/{id}
GET    /api/agents/edges
GET    /api/agents/edges/matrix

POST   /api/simulations
GET    /api/simulations/{id}/status
GET    /api/simulations/{id}/result   ← Accept header 決定格式
GET    /api/simulations/{id}/result/summary
GET    /api/simulations/{id}/result/timestep/{t}
POST   /api/simulations/{id}/compare

GET    /api/alerts
GET    /api/alerts/{id}
PATCH  /api/alerts/{id}/acknowledge
POST   /api/alerts/thresholds

POST   /api/data/crawl
GET    /api/data/crawl/{job_id}
POST   /api/data/events
GET    /api/data/events
POST   /api/data/calibrate
GET    /api/data/calibrate/{job_id}
```

輸出格式由 `Accept` header 控制：

```bash
curl -H "Accept: application/json" /api/simulations/{id}/result   # 儀表板
curl -H "Accept: text/markdown"    /api/simulations/{id}/result   # 報告
curl -H "Accept: application/pdf"  /api/simulations/{id}/result   # PDF
```

---

## 9. 核心抽象層

```
BeliefState (frozen)
    ↓
FJEngine (step + run)
    ↓
MonteCarloRunner (GPU batching)
    ↓
SimulationDistribution (CI + EWS 指標)
    ↓
EWSMonitor (Welford z-score)
    ↓
SimulationService (唯一對外介面)
```

**Protocol 介面（整合 AuroMem / AuroGov 用，不整合用 Noop）**：

```python
class MemoryProtocol(Protocol):
    async def get_agent_sensitivity(self, agent_id, event_type) -> float: ...
    async def save_agent_state(self, agent_id, belief_vector) -> None: ...

class GovernorProtocol(Protocol):
    async def check_belief_update(self, agent_id, old, new) -> np.ndarray: ...
    async def audit(self, event, payload) -> None: ...

class NoopMemory:
    async def get_agent_sensitivity(self, *args) -> float: return 0.5
    async def save_agent_state(self, *args) -> None: pass

class NoopGovernor:
    async def check_belief_update(self, agent_id, old, new): return new
    async def audit(self, *args) -> None: pass
```

---

## 10. 部署指令

### docker-compose.yml

```yaml
version: "3.9"

services:
  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [api]

  api:
    build: .
    command: flask run --host 0.0.0.0 --port 5001
    env_file: .env
    ports: ["5001:5001"]
    depends_on: [postgres, redis]
    volumes: ["./worldedge:/app/worldedge"]

  worker:
    build: .
    command: celery -A worldedge.tasks worker --loglevel=info -c 2
    env_file: .env
    depends_on: [postgres, redis]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  crawler:
    build: .
    command: python -m worldedge.crawler.scheduler
    env_file: .env
    depends_on: [postgres]

  signal_monitor:
    build: .
    command: python -m worldedge.signals.signal_scheduler
    env_file: .env
    depends_on: [postgres]
    # 獨立服務：地緣政治物理訊號
    # crawler 和 signal_monitor 完全分開，互不影響

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: worldedge
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes: ["pgdata:/var/lib/postgresql/data"]
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    command: redis-server --save 60 1 --appendonly yes
    volumes: ["redisdata:/data"]
    ports: ["6379:6379"]

volumes:
  pgdata:
  redisdata:
```

### 常用指令

```bash
docker compose up -d
docker compose exec api python scripts/init_db.py
docker compose exec api python scripts/seed_dimensions.py
docker compose logs -f worker
docker compose logs -f signal_monitor
docker compose logs -f crawler
docker compose restart api
docker compose down
docker compose down -v    # 含資料完整清除
```

---

## 11. 測試策略

### P0（必須通過才能往下）

```
tests/test_core/test_fj_engine.py        FJ 收斂、事件注入
tests/test_core/test_monte_carlo.py      輸出是分佈不是單點
tests/test_core/test_ews_monitor.py      Welford z-score 正確性
tests/test_signals/test_impact_mapper.py 所有向量值在 [-1, 1]
```

### P1（Phase 4 完成後）

```
tests/test_signals/test_ais_signal.py    台海範圍過濾正確
tests/test_api/test_simulations.py       提交→輪詢→取結果流程
```

### P2（整合測試）

```
tests/test_integration/test_backtest.py  歷史事件 EWS 驗證
tests/test_integration/test_e2e.py       完整流程 smoke test
```

---

## 12. 開發注意事項

### 數學正確性

1. `BeliefState` 必須 `frozen=True`，Monte Carlo 並行安全
2. W 矩陣行和 ≤ 1，否則 FJ 不收斂
3. `np.clip(B, -1.0, 1.0)` 每步執行，防數值爆炸
4. Welford 需 ≥ 10 個樣本才報警，防假警報

### 資料來源注意

1. AIS WebSocket 要有斷線重連邏輯（指數退避，最長等 5 分鐘）
2. GDELT tone 值 -100~100，轉 impact_vector 要除以 10
3. USGS 地震用 `time` 欄位，不用 fetch 時間（可能有延遲）
4. adsb.lol 端點偶爾不穩，失敗直接跳過不報錯

### 爬蟲與訊號分離

```
crawler/       台灣輿論，慢速批次，影響 W 矩陣
signals/       地緣政治物理訊號，較快，影響 ExternalEvent

兩個服務獨立運行，一個掛了不影響另一個。
```

### Redis Key 規範

```
simulation:{id}:status   TTL 24h
simulation:{id}:result   TTL 7d
crawl:{job_id}:status    TTL 24h
signal:ais:latest        TTL 2h    最新台海軍艦狀態快取
signal:gdelt:latest      TTL 6h
```

### 常見問題

**Q：FJ 不收斂？**
W 矩陣行和是否 ≤ 1，α 是否在 (0,1)。

**Q：PTT 爬蟲被擋？**
切換 Nodriver：邏輯不變，換 fetcher。

**Q：AIS WebSocket 斷線？**
指數退避重連，`asyncio.sleep(min(2**retry, 300))`。

**Q：GPU 記憶體不夠？**
降低 `n_runs`（10000 → 1000）。

**Q：GDELT 事件太多太雜？**
調高 tone 閾值（-3 → -5），只取更強烈的事件。

---

## 13. 研究限制聲明

這一節不是附錄，是模型可信度的一部分。
**清楚說明限制，比假裝限制不存在更有學術價值。**

---

### Limitation 1：社群媒體覆蓋缺口（最重要）

**現況**

台灣最主要的輿論場域按影響力排序大致為：

```
Facebook    → 台灣滲透率最高，最多政治討論，但 API 完全封閉
LINE 群組   → 私訊為主，無法取得
Instagram   → 年輕族群，API 封閉
X（Twitter）→ 媒體人、政治人物活躍，但 API 收費至無法負擔
PTT         → 本計畫有爬，但用戶結構偏向特定族群
Dcard       → 本計畫有爬，年輕族群為主
Bluesky     → 本計畫有爬，但台灣用戶基數仍小
```

**影響評估**

W 矩陣缺少 Facebook 和 X 的資料，代表：

- 媒體對中老年族群（FB 主要用戶）的影響力被低估
- 政治人物的直接影響力被低估
- 快速擴散的病毒式輿論事件可能無法及時偵測

**緩解策略**

- 新聞媒體的「引用 FB/Twitter 貼文」報導，作為二手代理變數
- Bluesky 作為 X 的部分替代，持續監測台灣意見領袖遷移情況
- 在研究結論中，所有 W 矩陣校準數值應附「覆蓋率估計」

---

### Limitation 2：W 矩陣的代表性

**現況**

目前 W 矩陣由三類資料構建：
- 新聞媒體引用關係（結構性，相對可靠）
- PTT/Dcard 互動（行為性，但代表特定族群）
- Bluesky 互動（行為性，用戶基數仍小）

**影響評估**

影響力圖可能無法完整呈現：
- 私下訊息（LINE、FB Messenger）形成的意見領袖網絡
- 地方性、社區性的輿論影響力
- 宗教、職業、族群等次文化圈的內部影響

**緩解策略**

在報告輸出時，應標示每條 W 邊的 `confidence` 值和 `weight_type`，
讓讀者可以識別哪些邊是實測的、哪些是推斷的。

---

### Limitation 3：Pol.is 資料的時效性

**現況**

vTaiwan 的 Pol.is 歷史資料集中在 2015-2019 年的幾個議題（Uber、金融科技等），
近年來使用率下降，新議題的結構化立場資料較少。

**影響評估**

用這些資料校準 `b(0)` 時，可能反映的是五年前的民意基準，
對當前議題（AI 監管、能源政策、兩岸關係）的代表性有限。

**緩解策略**

Pol.is 資料優先用於：
- 驗證模型校準方法的有效性（用舊議題 backtest）
- 提供民主審議型議題的基準信念向量
不直接用作當前議題的 `b(0)` 初始值（仍以 LLM 從當前文件填值為主）。

---

### Limitation 4：反身性問題

**現況**

社會系統的根本特性：當預測結果被公開，它會改變被預測的行為。

```
模型預測「A 議題即將觸發臨界點」
  → 決策者提前介入
    → 輿論走向改變
      → 模型的預測「失準」
```

這不是模型的錯，而是社會世界模型的內建限制。
物理世界不知道你在模擬它，但社會世界會知道。

**影響評估**

模型的預測不應被視為「未來必然發生的事」，
而應被定位為「在不干預的情況下，系統的自然演化路徑」。

**緩解策略**

所有輸出報告應加上標準免責聲明：
> 「本模型基於現有可觀測資料的推斷，不包含反身性效應。
>  模型結果用於輔助決策參考，不應作為預測確定性的依據。」

---

### Limitation 5：Backtesting 的 Ground Truth 問題

**現況**

驗證 EWS 有效性需要歷史 ground truth，但台灣缺乏：
- 高品質的公開輿論追蹤時間序列（TVBS、台灣指標民調樣本有限）
- 標準化的「輿論臨界事件」定義

**緩解策略**

採用代理指標（proxy measures）：
- Google Trends 搜尋量暴增
- 新聞媒體報導量的異常上升
- 立法院公報的議題討論頻率

並在研究中明確說明：「以代理指標替代直接民調，
兩者之間的映射關係本身也是一個待驗證的假設。」

---

### 限制摘要表

| 限制 | 嚴重程度 | 影響範圍 | 緩解程度 |
|------|---------|---------|---------|
| FB/X 資料缺口 | 高 | W 矩陣完整性 | 部分（Bluesky 替代）|
| W 矩陣代表性 | 中 | 模型校準精度 | 部分（confidence 標示）|
| Pol.is 時效性 | 低 | b(0) 初始值 | 有限（用於 backtest）|
| 反身性問題 | 中 | 預測有效性 | 無法消除，只能聲明 |
| Backtest 基準 | 中 | 模型驗證可信度 | 部分（代理指標）|

---

## 版本記錄

| 版本 | 日期 | 說明 |
|------|------|------|
| v0.1 | 2026-03-21 | SDD 完成，初稿 |
| v0.2 | 2026-03-21 | 整合 Shadowbroker 地緣政治訊號；剔除不必要資料源；新增 `signals/` 模組與 `impact_mapper.py`；`docker-compose` 拆分 `crawler` 和 `signal_monitor` 兩個獨立服務；`external_events` 表新增 `source_type` 欄位 |
| v0.3 | 2026-03-21 | 新增 Bluesky（AT Protocol）和 Pol.is/vTaiwan 資料源；更新目錄結構；剔除清單說明更精確；新增第 13 節「研究限制聲明」|

---

*本文件由 Claude 協助從 SDD 八站討論整理產出。*
