# GlobeEdge 相關文獻參考資料

> 搜尋日期：2026-03-22
> 關鍵字：Friedkin-Johnsen, opinion dynamics, computational social science, LLM agents, 2025-2026
> 用途：GlobeEdge 研究報告的文獻基礎與差異化定位

---

## 一、FJ 模型的最新擴展（數學方向）

### 1. FJ-MM：記憶 + 高階鄰居影響
**標題**：FJ-MM: The Friedkin-Johnsen Opinion Dynamics Model with Memory and Higher-Order Neighbors
**作者**：Roberta Raineri, Anton V. Proskurnikov
**發表**：arXiv 2504.06731（2025 年 4 月）/ ScienceDirect（2025 年 7 月）
**連結**：https://arxiv.org/abs/2504.06731

**核心貢獻**：
- 引入記憶效應（memory effects）：Agent 整合當前和過去的意見
- 引入多跳影響（multi-hop）：不只考慮直接鄰居，也考慮高階鄰居
- 數值結果：加入記憶後，最終的極化程度可以降低

**對 GlobeEdge 的意義**：
- 與 CrisisAwareFJEngine 的動態 b(0) 是同一概念的不同數學表達
- FJ-MM 用「時間加權的過去意見」，GlobeEdge 用「動態漂移的錨點」
- 可引用作為 GlobeEdge 心理機制擴展的學術定位對比

**踩的坑**：
- 只處理收斂性和均衡性，不處理「持續危機下 b(0) 本身漂移」的問題

---

### 2. Efficient Algorithms for FJ Model
**標題**：Efficient Algorithms for Relevant Quantities of Friedkin-Johnsen Opinion Dynamics Model
**作者**：Gengyu Wang et al.
**發表**：arXiv 2507.14864（2025 年 7 月）/ ACM SIGKDD 2025
**連結**：https://arxiv.org/abs/2507.14864

**核心貢獻**：
- 提出確定性本地算法，可處理超過 1000 萬節點的網路
- 計算極化（polarization）和分歧（disagreement）的高效算法
- 整合逐次超鬆弛技術（successive over-relaxation）加速收斂

**對 GlobeEdge 的意義**：
- GlobeEdge 目前的 W 矩陣節點數量很小（20-40 個），這個算法暫時用不到
- 但若未來擴展到更大規模的台灣社會網路，這篇是重要參考

---

### 3. Signed FJ Model：對抗性互動
**標題**：Friedkin-Johnsen Model for Opinion Dynamics on Signed Graphs
**發表**：IEEE（2025）
**連結**：https://ieeexplore.ieee.org/iel8/69/4358933/10591448.pdf

**核心貢獻**：
- 帶符號的圖（signed graph）：正邊（合作）+ 負邊（競爭/對抗）
- 意見動態不再侷限於初始條件的凸包，允許裂縫加深

**對 GlobeEdge 的意義**：
- GlobeEdge 的 W 矩陣目前只有正值（影響力）
- 加入負值邊（對抗關係）可以更精確地建模台灣深藍/深綠的互相排斥
- 這是 Phase 9 的潛在方向：負值 W 邊 = 「看到 A 說的就反方向走」

---

### 4. Signed FJ（SFJ）Model：非正規系統
**標題**：Signed Friedkin-Johnsen Models: Opinion Dynamics With Stubborn Agents
**發表**：IEEE（2026）
**連結**：https://ieeexplore.ieee.org/iel8/9/4601496/10849573.pdf

**核心貢獻**：
- 研究固執 Agent + 對抗性互動的組合效應
- 發現 SFJ 系統可以表現為非正規（nonnormal）系統：意見先發散再收斂
- 這解釋了「短暫激化後達成扭曲共識」的現象

**對 GlobeEdge 的意義**：
- 台灣大罷免潮的動態很可能是 SFJ 系統：
  深藍/深綠先激化，中間選民被拉往其中一方
- 動機性推理（Layer 3）的數學基礎就在這裡

---

## 二、FJ + 其他機制的混合模型

### 5. FJC：FJ on Cascades（迷因傳播）
**標題**：Cascade-driven opinion dynamics on social networks
**連結**：https://arxiv.org/pdf/2506.16302v2

**核心貢獻**：
- 第一個整合意見動態和資訊瀑布（information cascades）的模型
- FJC 允許一篇貼文的病毒式傳播影響意見形成
- 在真實瀑布資料集上驗證，即使底層假設被放鬆也有效

**對 GlobeEdge 的意義**：
- WBC + 島嶼天光哏化事件就是一個資訊瀑布
- 迷因的傳播邏輯不是 FJ 的線性影響，而是病毒式瀑布
- FJC 是 GlobeEdge 未來建模迷因事件的數學基礎
- `meme_dynamics: reach_multiplier=3.0` 的直覺來源

---

### 6. FJ + Game Theory：保育話語
**標題**：Opinion dynamics game in conservation discourse
**作者**：Kareeva, Y., Sedakov, A.
**發表**：Journal of Computational Social Science, 2026
**連結**：https://doi.org/10.1007/s42001-025-00430-7

**核心貢獻**：
- 整合賽局理論和 FJ 模型，分析三種互動情境：直接衝突、價值對齊妥協、部分妥協
- 展示不同策略對意見形成的影響

**對 GlobeEdge 的意義**：
- 台灣能源政策的擁核/反核就是「直接衝突」情境
- 賽局理論框架可以用來分析 What If 介入的策略效果

---

## 三、LLM + 輿論動態（最前沿）

### 7. FDE-LLM：最接近 GlobeEdge 的系統
**標題**：Social opinions prediction utilizes fusing dynamics equation with LLM-based agents
**發表**：Scientific Reports（2025 年 5 月）
**連結**：https://doi.org/10.1038/s41598-025-99704-3

**核心貢獻**：
- 把 LLM 行為和輿論演化方程（dynamics equation）對齊
- 分成意見領袖（LLM 角色扮演）和追隨者（Cellular Automata）
- 用真實社交網路資料驗證

**對 GlobeEdge 的意義**：
- 這是跟 GlobeEdge 最接近的平行研究
- 差別：GlobeEdge 用 FJ + MC，他們用 CA + LLM 角色扮演
- GlobeEdge 的優勢：更嚴謹的數學（MC 不確定性量化）+ 台灣本地化
- 可以引用作為方法論的比較基準

**踩的坑**：
- 需要 follow lists 等完整社交網路資料，現實中難取得
- Grid-based CA 假設局部互動，忽略長距離影響

---

### 8. LLM Agents 的輿論動態模擬（NAACL 2024）
**標題**：Simulating Opinion Dynamics with Networks of LLM-based Agents
**作者**：Yun-Shiuan Chuang et al.（台大 + 威斯康辛大學）
**發表**：NAACL Findings 2024
**連結**：https://arxiv.org/html/2311.09618v3

**核心貢獻**：
- 用 LLM Agent 網路模擬輿論動態
- **關鍵發現：LLM Agent 天生偏向產出準確資訊，導致趨向科學共識**
- 加入確認偏誤（confirmation bias）後，可以模擬更真實的極化

**⚠️ 踩的坑（GlobeEdge 應避免）**：
- LLM Agent 直接驅動信念更新 → 偏向共識，無法捕捉真實極化
- 這正是 GlobeEdge 選擇用 FJ 數學而非純 LLM Agent 的理由
- GlobeEdge 的架構設計無意中避開了這個陷阱

**注意**：第一作者 Yun-Shiuan Chuang 是台灣人（台大），
可能是台灣最適合合作的研究者之一。

---

### 9. LODAS：語言驅動的輿論動態
**標題**：Language-Driven Opinion Dynamics in Agent-Based Simulations with LLMs
**發表**：EPJ Data Science（2025）
**連結**：https://link.springer.com/content/pdf/10.1140/epjds/s13688-025-00579-1.pdf

**核心貢獻**：
- 研究 LLM Agent 如何產生和傳播邏輯謬誤（logical fallacies）
- 發現初始條件對最終結果影響有限：系統的最終狀態主要由模型本身決定

**⚠️ 踩的坑**：
- 英語對齊的 LLM 在多 Agent 互動中引入文化偏見
- 這是 GlobeEdge 使用本地 Qwen3.5（中文優化）的正當理由

**對 GlobeEdge 的隱含挑戰**：
- 如果初始條件影響有限，花大力氣校準 b(0) 的回報可能不如預期
- GlobeEdge 的 b(0) 校準工作需要額外的敏感度分析來支撐

---

### 10. SocioVerse：1000 萬真實用戶池（復旦大學）
**標題**：SocioVerse — LLM-agent-driven world model for social simulation
**機構**：復旦大學 DISC Lab（Zhongyu Wei）
**發表**：NLPCC 2025
**連結**：http://tcci.ccf.org.cn/conference/2025/socialinfo.php

**核心貢獻**：
- 1000 萬真實個體的用戶池（user pool）
- 四個對齊組件：環境、目標用戶、互動機制、行為模式
- 在政治、新聞、經濟三個領域的大規模仿真

**對 GlobeEdge 的意義**：
- 這是規模最大的類似系統，直接競爭
- **關鍵差異：SocioVerse 做中國情境，GlobeEdge 做台灣情境**
- 台灣在計算社會科學的地圖上是空白，這是 GlobeEdge 的差異化空間

---

### 11. Backfire Effect + FJ（早稱 Waseda/Tokyo）
**標題**：The Backfire of Influence Operation: How Manipulating Moderate Influencers Affects Online Discourse
**作者**：Takeda, T., Toriumi, F., Sugawara, T.（早稻田 + 東大）
**發表**：Complex Networks 2025（Springer，2026 年出版）
**連結**：https://doi.org/10.1007/978-3-032-16723-1_21

**核心貢獻**：
- 把中間立場的意見領袖推向極端 → 引發對立用戶的反向排斥
- 整合 FJ + Bounded Confidence + Social Reinforcement
- 在 Scale-free 網路上的實驗支持 Backfire Effect

**對 GlobeEdge 的意義**：
- **直接驗證了 GlobeEdge Layer 3（動機性推理）的核心假設**
- GlobeEdge 的 98.1% 影響力消失與這篇論文的方向一致
- 可引用作為動機性推理機制的學術支撐

---

### 12. LLM 社會規範的湧現（Science Advances）
**標題**：Emergent social conventions and collective bias in LLM populations
**發表**：Science Advances（2025 年 5 月）
**連結**：https://pmc.ncbi.nlm.nih.gov/articles/PMC12077490/

**核心貢獻**：
- AI Agent 群體可以自發形成社會規範
- 展示 LLM 群體中的臨界質量動態（critical mass dynamics）
- 社會規範可以在沒有中央機構的情況下湧現

**對 GlobeEdge 的意義**：
- 台灣的集體信念（如「台灣有事」的感知）可能是這種湧現規範
- GlobeEdge 的 EWS 偵測的正是這種臨界質量的積累過程

---

## 四、從文獻看 GlobeEdge 的定位

### 你避開的坑

| 坑 | 前人遭遇 | GlobeEdge 的對應選擇 |
|---|---|---|
| LLM 偏向共識 | Chuang et al. (NAACL 2024) | 用 FJ 數學，LLM 只輔助標記 |
| 英語文化偏差 | LODAS (EPJ 2025) | 使用本地 Qwen3.5 |
| 缺乏不確定性量化 | 多數 LLM Agent 系統 | Monte Carlo 10,000 次 |
| 初始條件主觀 | 普遍問題 | AI 輔助 b(0) 估計 |

### 你的獨特貢獻（文獻中沒有的）

```
① 台灣特有 alpha=0.3 的實證校準
   → 首次用台灣歷史事件估計信念更新速率

② 跨議題注意力競爭模型
   → WBC 稀釋政治動員效果的量化

③ 持續危機的 CrisisAwareFJEngine
   → 區分一次性衝擊 vs 持續危機的信念演化

④ 公衛流行病學框架的跨域應用
   → alpha ≡ 信念傳播的 R0，EWS ≡ 疫情預警

⑤ 心理機制四層的整合
   → Ebbinghaus + ELM + 動機性推理 + System 1/2
   → 在同一個 FJ 框架下統一建模
```

### 最適合合作的研究者線索

```
Yun-Shiuan Chuang（台大）— NAACL 2024 第一作者，台灣人
  研究 LLM Agent 輿論動態，跟 GlobeEdge 最接近
  可能是台灣最適合合作的計算社會科學研究者

Anton V. Proskurnikov（FJ-MM 作者）
  FJ 模型的數學擴展專家
  GlobeEdge 的 CrisisAwareFJEngine 可以和 FJ-MM 對比

Zhongyu Wei（復旦 DISC Lab）
  SocioVerse 的作者
  中國情境 vs 台灣情境，互補而非競爭
```

---

## 五、推薦閱讀順序

**第一週（建立理論基礎）**：
1. FJ-MM (arXiv 2504.06731) — 了解 FJ 的最新擴展方向
2. Chuang et al. NAACL 2024 — 了解 LLM Agent 的坑
3. Backfire Effect (Complex Networks 2025) — 動機性推理的文獻支撐

**第二週（找差異化定位）**：
4. FDE-LLM (Scientific Reports 2025) — 最接近的平行研究
5. SocioVerse (NLPCC 2025) — 最大的競爭對手
6. FJC (Cascade model) — 迷因傳播的數學

**準備投稿前**：
7. Signed FJ (IEEE 2025/2026) — 負值邊的數學基礎
8. Efficient Algorithms (SIGKDD 2025) — 計算可擴展性的參考

---

## 六、建議引用格式（APA）

```
Raineri, R., & Proskurnikov, A. V. (2025). FJ-MM: The Friedkin-Johnsen
  opinion dynamics model with memory and higher-order neighbors.
  arXiv preprint arXiv:2504.06731.

Yao, J., Zhang, H., Ou, J., et al. (2025). Social opinions prediction
  utilizes fusing dynamics equation with LLM-based agents.
  Scientific Reports, 15, 15472. https://doi.org/10.1038/s41598-025-99704-3

Chuang, Y.-S., Goyal, A., Harlalka, N., et al. (2024). Simulating
  opinion dynamics with networks of LLM-based agents.
  Findings of NAACL 2024. arXiv:2311.09618.

Takeda, T., Toriumi, F., & Sugawara, T. (2026). The backfire of
  influence operation: How manipulating moderate influencers affects
  online discourse. In Complex Networks & Their Applications XIV.
  Springer. https://doi.org/10.1007/978-3-032-16723-1_21

Kareeva, Y., & Sedakov, A. (2026). Opinion dynamics game in
  conservation discourse. Journal of Computational Social Science, 9, 12.
  https://doi.org/10.1007/s42001-025-00430-7
```

---

---

## 五、情緒動能與前瞻性信念（新增方向）

### 13. SI-SEIR：社會強化 + 個人情緒調節模型
**標題**：Modeling the spread of negative emotions in social networks during sudden public crisis events
**作者**：Wang T, Liu T, Li C.
**發表**：清華大學學報（2025）
**連結**：https://www.sciopen.com/article/10.16511/j.cnki.qhdxxb.2025.22.013

**核心貢獻**：
- 提出非馬可夫負面情緒傳播模型（SI-SEIR）
- 整合社會強化（social reinforcement）和個人情緒調節兩個機制
- 比傳統傳染病模型更能捕捉情緒傳播的社會動態

**對 GlobeEdge 的意義**：
- FJ 的線性衰退無法捕捉「社會強化」效應
- 柯文哲判決後 PTT 的討論熱度是社會強化的具體案例
- crisis_decay 參數的設定需要考慮社會強化週期（第 7.7 節）

---

### 14. 情緒與政策觀點（2013-2025 Twitter 大規模研究）
**標題**：Emotions and Policy Views
**作者**：Algan Y, Davoine E, Renault T.
**發表**：2025
**連結**：https://socialeconomicslab.org/wp-content/uploads/2025/07/emotions.pdf

**核心貢獻**：
- 分析 2013-2025 年 Twitter 資料，記錄憤怒情緒的長期趨勢
- 關鍵發現：政治人物的憤怒遵循政治權力週期，但**公民的憤怒被觸發後不自動回落**
- 負面情緒顯著增加對保護主義、限制性移民政策的支持

**對 GlobeEdge 的意義**：
- 直接支持第 7.7 節的限制聲明
- FJ 的 b(0) 回歸假設在「公民憤怒」場景下失效
- 台灣的政治憤怒（反貪腐、罷免）可能也具有同樣的持續性

---

### 15. 前瞻性投票理論與選舉預測
**標題**：Prospective voting and the issues and leaders model: Forecasting the 2024 U.S. presidential election
**作者**：Graefe A.
**發表**：Journal of Electoral Studies（2025）
**連結**：https://journals.sagepub.com/doi/10.1177/20531680251367314

**核心貢獻**：
- 前瞻性投票理論：選民行為由「對未來表現的預期」驅動
- 比回顧性模型（過去政績、經濟基本面）有更高的預測準確度
- 2024 美國大選預測誤差僅 0.65 個百分點

**對 GlobeEdge 的意義**：
- 直接支持第 7.6 節的限制聲明
- GlobeEdge 缺乏「前瞻性信念維度」是結構性問題
- dim8（2028 大選政黨認同預期）的理論基礎就在這裡
- 柯文哲判決 → 民眾調整 2028 大選預期，這條路徑需要前瞻性維度才能捕捉

---

| 版本 | 日期 | 說明 |
|------|------|------|
| v1.0 | 2026-03-22 | 初版，涵蓋 12 篇文獻，分四大類 |
| v2.0 | 2026-03-28 | 新增第五大類（情緒動能與前瞻性信念）：SI-SEIR 社會強化模型、Algan et al. 情緒持續性研究、前瞻性投票理論 |

---

*由 Utux Labs 悟圖實驗室 / GlobeEdge 研究計畫整理，搜尋範圍：arXiv, IEEE, Springer, ACM, Nature 2025-2026*
*台灣在計算社會科學的地圖上仍是空白——這是 GlobeEdge 的學術定位。*
