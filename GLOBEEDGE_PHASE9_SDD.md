# GlobeEdge Phase 9 — SDD 規格文件

**版本**：v1.0  
**日期**：2026-04-16  
**作者**：David Tao / Utux Labs 悟圖實驗室  
**狀態**：草稿，供詳讀審閱

---

## 目錄

1. [Phase 9 目標與邊界](#1-phase-9-目標與邊界)
2. [背景：從 Phase 8 到 Phase 9](#2-背景從-phase-8-到-phase-9)
3. [四個核心問題](#3-四個核心問題)
4. [Station 1：修復驗證框架](#4-station-1修復驗證框架)
5. [Station 2：重設 dim0 Proxy](#5-station-2重設-dim0-proxy)
6. [Station 3：Hohwy 預測誤差反串偵測](#6-station-3hohwy-預測誤差反串偵測)
7. [Station 4：b(0) 真實校準](#7-station-4b0-真實校準)
8. [Station 5：Pol.is 資料接入（長期）](#8-station-5polis-資料接入長期)
9. [資料模型變更](#9-資料模型變更)
10. [驗收標準](#10-驗收標準)
11. [執行時程](#11-執行時程)
12. [風險與決策點](#12-風險與決策點)

---

## 1. Phase 9 目標與邊界

### 目標

Phase 8 完成後，GlobeEdge 首次用真實 PTT 資料跑出 AUC = 0.541。Phase 9 的目標是**在不改變核心 FJ 架構的前提下**，透過修復測量工具和改善資料品質，讓 AUC 有可量化的提升。

### 邊界宣言

```
Phase 9 做的事：
  ✅ 修復 predictive_validation.py（測量工具問題）
  ✅ 重設 dim0 的 PTT proxy 關鍵字（資料問題）
  ✅ 加入 Hohwy 預測誤差框架識別反串（資料品質問題）
  ✅ 用乾淨資料重新校準 b(0)（模型輸入問題）

Phase 9 不做的事：
  ❌ 改變 FJ 核心數學
  ❌ 實作 SEIR 議題網絡模型（Phase 10）
  ❌ 動態 W 矩陣（Phase 10）
  ❌ 前瞻性信念維度 dim8/dim9（Phase 10）
```

### 成功定義

```
最低成功：整體 AUC > 0.600（比 0.541 提升 10.9%）
理想成功：dim0 AUC > 0.500（從 0.12 顯著提升）
完整成功：整體 AUC > 0.650，dim0 > 0.500，dim7 維持 > 0.850
```

---

## 2. 背景：從 Phase 8 到 Phase 9

### Phase 8 的關鍵發現

| 發現 | 數值 | 意義 |
|------|------|------|
| 首次真實 PTT 驗證 | AUC = 0.541 | 模型有真實預測力，但微弱 |
| b(0) 重要性 | +18.3% AUC | b(0) > W 矩陣，Phase 9 優先校準 b(0) |
| dim7 最強 | AUC = 0.880 | 外部威脅感知語意最單純 |
| dim0 最弱 | AUC = 0.120 | 語意不匹配 + 反串雜訊（翁教授確認）|
| 多峰機制 | TimesFM 確認 | FJ 獨立事件假設不足，但 Phase 10 才修 |
| crisis_decay 實驗 | 陰性結果 | 驗證框架繞開 CrisisAwareFJEngine |

### 翁履中教授的三個關鍵回饋（2026-04-16）

**回饋一：「先站定立場，才來理解事件」**

對應 GlobeEdge：這是 Motivated Reasoning（動機性推理）的質性驗證。alpha = 0.3 的「信念更新緩慢」特性，在質性研究中也有對應觀察。

**回饋二：「部分共識、部分分裂」**

直接解釋 dim7 AUC=0.88 vs dim0 AUC=0.12 的落差：
- 外部威脅（dim7）：跨陣營存在共識 → 模型容易預測
- 國內政治（dim0）：涉及黨派立場就完全分裂 → 模型難以預測

**回饋三：PTT 反串問題**

台灣網路文化中反串與諷刺普遍，推噓比作為立場代理指標的可靠性存疑。這是 dim0 AUC=0.12 的第二個重要原因。

---

## 3. 四個核心問題

Phase 9 需要依序解決四個獨立問題，每個問題解決後都能獨立測量 AUC 的變化。

```
問題 1：測量工具不準
  predictive_validation.py 繞開 CrisisAwareFJEngine
  → 修復後，crisis 相關改動才有測試路徑

問題 2：dim0 資料語意錯誤
  proxy 關鍵字對應到 dim1（制度公信力），不是 dim0（政府信任）
  → 重設關鍵字，期望 dim0 AUC 從 0.12 提升

問題 3：PTT 推噓比有反串雜訊
  諷刺性「推文支持」和真實立場支持，在資料層面無法區分
  → Hohwy 預測誤差框架識別反串，提升資料品質

問題 4：b(0) 用主觀設定，不是真實資料
  b(0) 貢獻 18.3% AUC，但目前靠研究者估計
  → 用乾淨的 PTT 立場訊號（問題 3 解決後）重新校準
```

**關鍵約束：必須按順序執行**

```
問題 1 修好後 → 才能準確測量問題 2 的效果
問題 2 修好後 → 才知道問題 3 要針對哪個維度
問題 3 修好後 → 才有乾淨資料可以校準問題 4
問題 4 解決後 → 才算完成 Phase 9
```

---

## 4. Station 1：修復驗證框架

### 問題描述

```python
# 現在的 predictive_validation.py（錯誤）
from globeedge.core.fj_engine import FJEngine  # ← 原始 FJ，無 crisis 機制

def run_validation(scenario):
    engine = FJEngine(alpha=0.3)  # ← 完全繞開 CrisisAwareFJEngine
    ...
```

`crisis_decay`、`alpha_max`、`spread_floor` 等參數對目前的驗證框架完全無效。這是 crisis_decay 消融實驗 AUC 完全不變的根本原因。

### 修復方案

```python
# 修復後的 predictive_validation.py
from globeedge.core.crisis_dynamics import CrisisAwareFJEngine
from globeedge.core.crisis_dynamics import CrisisConfig

def run_validation(scenario, use_crisis_engine=True):
    if use_crisis_engine:
        config = CrisisConfig(
            alpha_base=0.3,
            alpha_max=0.6,
            crisis_decay=0.05,
            spread_floor=0.12,
        )
        engine = CrisisAwareFJEngine(config=config)
    else:
        engine = FJEngine(alpha=0.3)  # 保留做對照組
    ...
```

### 驗收標準

```
① 修改後跑 70/70 tests 全部通過
② predictive_validation.py --engine=crisis 跑出 AUC（預期接近 0.541）
③ predictive_validation.py --engine=crisis --crisis-decay=0.02 跑出不同 AUC
   → 如果跟 0.05 不同，說明修復成功
④ 新增參數 --engine=[fj|crisis]，預設值改為 crisis
```

### 工程量估計

約 50 行修改，半天。

---

## 5. Station 2：重設 dim0 Proxy

### 問題描述

翁教授確認：dim0（政府信任度）需要捕捉「對執政黨的直接評價」，但現在的關鍵字設計對應的是 dim1（制度公信力）：

```
現在的 dim0 proxy 關鍵字（錯誤）：
  柯文哲、京華城、判決、17年
  → 這些文章在討論「司法公正性」
  → 對應語意：dim1（制度公信力），不是 dim0

翁教授的觀察：
  dim0「部分共識、部分分裂」的分裂面
  是在「國內政治 × 執政黨評價」上
  → 需要「對執政黨直接評價」的關鍵字
```

### 新的 Proxy 設計

```python
DIM_PROXY_KEYWORDS = {
    "dim0_政府信任度": {
        "positive": ["賴清德做得好", "民進黨執政", "政府有效"],
        "negative": ["賴清德失職", "民進黨爛", "政府無能", "下台"],
        "search_keywords": ["賴清德", "執政黨", "民進黨施政", "國民黨執政"]
    },
    "dim1_制度公信力": {
        "positive": ["司法公正", "制度健全"],
        "negative": ["司法迫害", "制度崩壞", "違憲"],
        "search_keywords": ["柯文哲", "判決", "京華城", "司法", "立法院"]
    },
    "dim7_外部威脅感知": {
        "positive": ["台灣安全", "和平穩定", "一家人"],
        "negative": ["中共威脅", "戰爭風險", "飛彈演習"],
        "search_keywords": ["鄭習會", "兩岸", "習近平", "解放軍"]
    },
    # ... 其他維度
}
```

### 驗收標準

```
① dim0 的 proxy 關鍵字更新完成
② 重跑 predictive_validation.py
③ dim0 AUC 從 0.12 提升（目標 > 0.35）
④ 其他維度 AUC 沒有顯著下降
⑤ 如果 dim0 AUC 沒有提升
   → 記錄為陰性結果
   → 表示問題主要在反串雜訊，進入 Station 3
```

### 工程量估計

純設定變更 + 重跑，約 2 小時。

---

## 6. Station 3：Hohwy 預測誤差反串偵測

### 理論基礎

Hohwy（2013）的預測心智框架（Predictive Mind / Free Energy Principle）：

```
大腦不是在接收世界，而是在預測世界
然後用「預測誤差（prediction error）」來修正自己的模型

情緒效價（valence）= 自由能的變化率
  預測誤差下降（預期實現）→ valence 正向（真誠表態）
  預測誤差上升（預期被違背）→ valence 負向（反串/諷刺）
```

**對 GlobeEdge 的轉化**：

```
「立場代理框架」的預測模型：
  如果一篇文章表面是「推文支持」
  但語意向量距離「批評立場」更近
  → 表面訊號和語意訊號不一致
  → 高預測誤差 → 高機率是反串

prediction_error = |surface_signal - semantic_signal|
```

### 核心數學

```python
def compute_prediction_error(
    article: str,
    push_ratio: float,
    baseline_positive: str,
    baseline_negative: str,
    embed_fn: Callable,
) -> tuple[float, float]:
    """
    計算 PTT 文章的立場預測誤差。
    
    Returns:
        stance_signal: 語意立場 [-1, +1]，正值偏正向
        prediction_error: 表面(推噓)與語意的差距 [0, 1]
    """
    # 表面訊號（推噓比）
    surface_signal = (push_ratio - 0.5) * 2  # 映射到 [-1, +1]

    # 語意訊號（embedding 距離）
    article_vec = embed_fn(article)
    pos_vec = embed_fn(baseline_positive)
    neg_vec = embed_fn(baseline_negative)

    dist_to_pos = cosine_distance(article_vec, pos_vec)
    dist_to_neg = cosine_distance(article_vec, neg_vec)

    # 語意立場：負值代表偏正向（距離正向基準更近）
    semantic_signal = dist_to_pos - dist_to_neg  # [-1, +1]

    # Hohwy 預測誤差：兩個訊號的差距
    prediction_error = abs(surface_signal - semantic_signal)

    return semantic_signal, prediction_error
```

### 立場基準敘事（Stance Baseline Narratives）

每個信念維度需要建立「正向基準」和「負向基準」，共 8 × 2 = 16 個基準敘事，每個 2-3 句話。

**建立原則**：
- 使用台灣在地的政治語境
- 避免過於學術或正式的語言
- 反映 PTT 政黑板的常見表達方式

**範例**：

```python
STANCE_BASELINES = {
    "dim0": {
        "positive": "賴清德執政表現不錯，民進黨的施政方向是對的，政府有在做事",
        "negative": "賴清德執政一塌糊塗，民進黨完全不行，這個政府讓人失望透頂"
    },
    "dim1": {
        "positive": "台灣司法獨立公正，法院的判決合理，制度運作正常",
        "negative": "台灣司法根本是政治工具，法院配合執政黨辦案，制度已經崩壞"
    },
    "dim4": {
        "positive": "美台關係穩固，台灣靠向美國是對的，美國會保護台灣",
        "negative": "美國根本不可靠，台灣被賣掉、靠美國是戰略錯誤"
    },
    "dim5": {
        "positive": "台灣民主需要改革，罷免制度是民主的展現，公民有權利行動",
        "negative": "罷免根本是政治操弄，台灣政治改革是假的，換湯不換藥"
    },
    "dim6": {
        "positive": "台灣社會團結，大家對未來有共識，政治紛爭可以解決",
        "negative": "台灣社會嚴重撕裂，藍綠對立無解，台灣人根本沒有共識"
    },
    "dim7": {
        "positive": "兩岸緩和，中共不會打台灣，和平有希望",
        "negative": "中共威脅嚴重，戰爭風險升高，台灣隨時可能被打"
    },
}
```

### 反串判斷邏輯

```python
SARCASM_THRESHOLD = 0.35  # prediction_error > 0.35 → 疑似反串

def classify_article_stance(
    article: str,
    push_ratio: float,
    dim: str,
    embed_fn: Callable,
) -> dict:
    semantic_signal, prediction_error = compute_prediction_error(
        article=article,
        push_ratio=push_ratio,
        baseline_positive=STANCE_BASELINES[dim]["positive"],
        baseline_negative=STANCE_BASELINES[dim]["negative"],
        embed_fn=embed_fn,
    )
    
    is_sarcasm_suspect = prediction_error > SARCASM_THRESHOLD
    confidence = 1.0 - prediction_error  # 誤差越低，信心越高
    
    # 最終立場：
    # 若非反串嫌疑 → 用語意訊號
    # 若為反串嫌疑 → 翻轉表面訊號，或標記為「需人工審閱」
    if is_sarcasm_suspect:
        final_stance = "SARCASM_SUSPECT"
        final_signal = -surface_signal  # 假設反串：翻轉表面訊號
    else:
        final_stance = "GENUINE"
        final_signal = semantic_signal
    
    return {
        "stance": final_stance,
        "signal": final_signal,
        "semantic_signal": semantic_signal,
        "surface_signal": surface_signal,
        "prediction_error": prediction_error,
        "confidence": confidence,
    }
```

### Embedding 工具選擇

```
優先選項：Ollama + qwen3.5:9b（已有）
  pros：本地跑，不需要 API 費用，中文理解好
  cons：速度稍慢

備選選項：sentence-transformers（paraphrase-multilingual）
  pros：快速，專門為語意相似度設計
  cons：需要安裝新套件

推薦：先用 Ollama qwen3.5:9b 驗證概念
     如果速度太慢再換 sentence-transformers
```

### 驗收標準

```
① 對柯文哲 135 篇文章計算 prediction_error
② 人工抽樣 30 篇，驗證反串標記準確率 > 60%
③ 重跑 predictive_validation.py（用反串過濾後的資料）
④ 整體 AUC 提升（目標比 Station 2 後的基準提升 > 5%）
⑤ 特別觀察 dim0 AUC 變化：
   如果提升 → 反串是 dim0 問題的主要原因
   如果不提升 → 問題在別處，誠實記錄
```

### 工程量估計

約 200 行（含 baseline 定義 + embedding + 分類邏輯 + 測試），1-2 天。

---

## 7. Station 4：b(0) 真實校準

### 背景

Q3 敏感度分析確認：精心校準的 b(0) 比隨機 b(0) 多貢獻 18.3% AUC。目前 b(0) 由研究者主觀設定，Phase 9 目標是用 PTT 真實資料（Station 3 清洗後）自動校準。

### 設計原則

```
不是讓資料完全決定 b(0)
而是讓資料「修正」研究者設定的 b(0)

b(0)_final = α_calibrate × b(0)_ptt + (1 - α_calibrate) × b(0)_prior

α_calibrate：校準強度（0 = 完全用先驗，1 = 完全用資料）
             根據各維度的資料量決定
             資料量多 → α_calibrate 高
             資料量少 → α_calibrate 低（避免過擬合）
```

### 資料驅動 b(0) 計算

```python
def calibrate_b0_from_ptt(
    ptt_articles: list[dict],  # 已用 Station 3 清洗的文章
    dim: str,
    prior_b0: float,           # 研究者設定的先驗 b(0)
    agent_type: str,           # "media" | "kol" | "forum" | "public"
    min_articles: int = 10,    # 最少需要幾篇才做校準
) -> tuple[float, float]:      # (calibrated_b0, confidence)
    """
    用 PTT 資料校準特定 Agent 類型在特定維度上的初始信念。
    
    Returns:
        calibrated_b0: 校準後的 b(0) 值 [-1, +1]
        confidence: 校準信心（資料量越多越高）
    """
    # 篩選出這個 Agent 類型的文章
    relevant_articles = [a for a in ptt_articles
                        if a["agent_type"] == agent_type
                        and a["dim"] == dim
                        and a["stance"] != "SARCASM_SUSPECT"]  # 排除反串嫌疑

    if len(relevant_articles) < min_articles:
        # 資料不足，保持先驗
        return prior_b0, 0.0

    # 計算資料驅動的立場分佈
    signals = [a["signal"] for a in relevant_articles]
    data_b0 = np.mean(signals)

    # 校準強度：資料量越多，越信任資料
    n = len(relevant_articles)
    alpha_calibrate = min(n / 100, 0.8)  # 最高 80%，留 20% 給先驗

    calibrated_b0 = alpha_calibrate * data_b0 + (1 - alpha_calibrate) * prior_b0
    confidence = alpha_calibrate

    return float(np.clip(calibrated_b0, -1.0, 1.0)), confidence
```

### 校準範圍

Phase 9 優先校準以下 Agent 類型：

```
PTT 論壇 Agent（資料最豐富）：
  HatePolitics 板的平均立場 → 論壇 Agent 的 b(0)
  Gossiping 板的平均立場 → 八卦 Agent 的 b(0)

KOL Agent（按議題關鍵字識別）：
  柯文哲相關文章 → 民眾黨 KOL 的 b(0)
  鄭習會相關文章 → 國民黨 KOL 的 b(0)
  罷免相關文章 → 改革派 KOL 的 b(0)

媒體 Agent（RSS 新聞）：
  目前 RSS 資料量不足，暫不校準
```

### 驗收標準

```
① 各 scenario 的論壇 Agent b(0) 更新完成
② 重跑 predictive_validation.py
③ 整體 AUC 有可量化提升（目標 > Station 3 基準 + 3%）
④ 校準報告：每個 Agent 的 b(0) 變化量 + 信心分數
⑤ 如果某維度資料不足（< 10 篇）→ 保持先驗，記錄
```

### 工程量估計

約 150 行（含校準邏輯 + scenario 更新 + 測試），1 天。

---

## 8. Station 5：Pol.is 資料接入（長期）

### 背景

翁教授建議 Pol.is/vTaiwan 的結構化立場資料可以解決 PTT 推噓比的根本限制。Pol.is 要求用戶明確表態（同意/不同意/跳過），沒有反串問題。

### 設計概念

```
Pol.is 資料的優勢：
  ① 用戶明確表態，無反串問題
  ② 可以直接映射到 FJ 的 b(0)（-1 到 +1）
  ③ 有人口學資料（可以校準不同 Agent 類型）
  ④ vTaiwan 有能源政策的歷史資料

接入方式：
  Pol.is API 或 CSV 匯出
  按議題類型映射到 GlobeEdge 的 8 個信念維度
  作為 b(0) 的「黃金標準」校準資料
```

### 執行時程

```
Phase 9 期間：設計資料格式 + 確認接入可行性
Phase 10 期間：實際接入，比較 PTT 校準 vs Pol.is 校準的 AUC 差距
```

---

## 9. 資料模型變更

### 新增欄位：ptt_articles 表

```sql
ALTER TABLE ptt_articles ADD COLUMN IF NOT EXISTS
    semantic_signal FLOAT,       -- 語意立場訊號 [-1, +1]
    prediction_error FLOAT,      -- Hohwy 預測誤差 [0, 1]
    stance_label VARCHAR(20),    -- GENUINE | SARCASM_SUSPECT | UNKNOWN
    stance_confidence FLOAT,     -- 標記信心分數 [0, 1]
    dim_signals JSONB;           -- 8 維立場訊號 {"dim0": 0.3, "dim1": -0.2, ...}
```

### 新增表：stance_baselines

```sql
CREATE TABLE stance_baselines (
    id SERIAL PRIMARY KEY,
    dim VARCHAR(10) NOT NULL,           -- "dim0" to "dim7"
    direction VARCHAR(10) NOT NULL,     -- "positive" | "negative"
    narrative TEXT NOT NULL,            -- 基準敘事文本
    embedding VECTOR(768),              -- 預計算的 embedding 向量
    version VARCHAR(10) NOT NULL,       -- 版本號（更新基準時遞增）
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 新增表：b0_calibration_log

```sql
CREATE TABLE b0_calibration_log (
    id SERIAL PRIMARY KEY,
    scenario VARCHAR(50) NOT NULL,      -- "recall" | "geopolitics" | ...
    agent_type VARCHAR(20) NOT NULL,    -- "forum" | "kol" | "media" | "public"
    dim VARCHAR(10) NOT NULL,
    prior_b0 FLOAT NOT NULL,
    calibrated_b0 FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    article_count INTEGER NOT NULL,
    calibrated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 10. 驗收標準

### 整體 Phase 9 驗收表

| Station | 完成條件 | AUC 目標 | 狀態 |
|---------|---------|---------|------|
| 1. 修復驗證框架 | crisis_decay 改動有效果 | 基準確立 | ⏳ |
| 2. dim0 proxy 重設 | dim0 AUC > 0.350 | +15% | ⏳ |
| 3. 反串偵測 | 人工驗證準確率 > 60% | +5% | ⏳ |
| 4. b(0) 校準 | 論壇 Agent b(0) 更新完成 | +3% | ⏳ |
| 整體 | 70/70 tests 通過 | > 0.600 | ⏳ |

### 各 Station 的陰性結果處理

```
如果任何 Station 做完後 AUC 沒有提升：
  → 誠實記錄為陰性結果
  → 不強行解釋為「還需要調整」
  → 這個 Station 的假說被推翻，記入研究限制

例：如果 Station 2（dim0 proxy）做完後 AUC 仍然 0.12
  → 表示問題不在關鍵字設計
  → 可能完全是反串雜訊造成的
  → Station 3 的重要性升高
```

---

## 11. 執行時程

### 5 月中旬見面前的目標

翁履中教授預計 5 月中旬返台，建議在見面前完成 Station 1-3。

```
Week 1（現在）：Station 1
  修復 predictive_validation.py
  確認測量工具正確
  建立新的 AUC 基準線

Week 2：Station 2
  重設 dim0 proxy 關鍵字
  重跑 predictive_validation.py
  記錄 dim0 AUC 變化

Week 3-4：Station 3
  建立 16 個立場基準敘事
  實作 Hohwy 預測誤差計算
  對全部 4,700+ 文章跑標記
  人工驗證 30 篇
  重跑 predictive_validation.py

見面前：整理報告
  把 Station 1-3 的結果更新進 WORLDEDGE_REPORT.md
  準備給翁教授的報告版本
  包含：方法論改進、AUC 變化、陰性結果
```

### 見面後

```
Week 5-6：Station 4（b(0) 校準）
  根據翁教授回饋決定是否調整方向
  用 Station 3 清洗後的資料校準 b(0)
  重跑完整驗證

Month 2+：Station 5（Pol.is）
  設計資料格式
  確認接入可行性
  可能需要翁教授協助取得 vTaiwan 歷史資料
```

---

## 12. 風險與決策點

### 風險一：Station 3 反串偵測準確率不足

```
觸發條件：人工驗證準確率 < 60%

應對方案：
  A. 改進基準敘事文本，重新測試
  B. 降低 SARCASM_THRESHOLD（減少誤判）
  C. 放棄自動識別，改為「排除高 prediction_error 文章」
     （不判斷是否反串，只排除不確定的文章）
  D. 接受限制，誠實在報告中說明
```

### 風險二：Qwen3.5 embedding 速度太慢

```
觸發條件：對 4,700 篇文章跑 embedding 超過 4 小時

應對方案：
  A. 批次處理 + 快取（計算一次後存入 DB）
  B. 換用 sentence-transformers（速度快 5-10 倍）
  C. 只對「高爭議文章」（推噓比接近 50:50）跑 embedding
```

### 風險三：b(0) 校準資料不足

```
觸發條件：某個維度的有效文章 < 10 篇

應對方案：
  A. 保持先驗 b(0) 不變，在日誌中標記
  B. 繼續讓爬蟲累積資料，下個月再校準
  C. 合併相關維度的文章（例：dim4+dim7 都跟外部因素有關）
```

### 決策點一：Station 2 後

```
如果 dim0 AUC 從 0.12 提升到 > 0.35：
  → 問題主要在 proxy 關鍵字設計
  → Station 3（反串偵測）作為補強，非必要

如果 dim0 AUC 沒有提升：
  → 問題主要在反串雜訊
  → Station 3 變成最高優先項目
```

### 決策點二：Station 3 後

```
如果整體 AUC > 0.60：
  → Phase 9 核心目標達成，可以準備報告
  → Station 4 作為補強

如果整體 AUC 仍在 0.54-0.58：
  → FJ 線性模型的根本限制開始顯現
  → 考慮提前規劃 Phase 10（議題網絡架構）
  → 這個發現本身也是可以報告的結果
```

---

## 附錄：Phase 9 與 Phase 10 的邊界

```
Phase 9（本文件）：
  在現有 FJ 架構內，改善測量和資料品質
  不改變模型的核心數學

Phase 10（未來規劃）：
  SEIR 潛伏期框架（議題網絡效應）
  動態 W 矩陣 W(t+1) = f(W(t), content, algorithm)
  前瞻性信念維度 dim8/dim9（2028 大選預期）
  Agent 策略行為（賽局理論）

邊界的意義：
  Phase 9 做完後，如果 AUC 仍然沒有顯著提升
  → 說明問題不在測量和資料，而在模型架構
  → 這是進入 Phase 10 的明確觸發條件
  → 而不是「無限加功能」的理由
```

---

*GlobeEdge Phase 9 SDD v1.0*  
*Utux Labs 悟圖實驗室 · 2026-04-16*
