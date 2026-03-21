"""議題五：美伊戰爭對台灣的衝擊 ★ 即時議題。

2026-02-28 美以發動 Epic Fury 聯合空襲，伊朗封鎖霍木茲海峽。
布蘭特原油 $70 → $126，台灣高度依賴中東進口能源。

這是 WorldEdge 的第一個即時驗證機會：
  模型預測（基於 2026-03-01 資料）vs PTT/新聞爬蟲真實輿論演化。
"""

from .base import AgentDef, DimensionDef, EventDef, Scenario

DIMENSIONS = [
    DimensionDef(0, "媒體信任度", "政府信任度",      "對政府危機處理能力的信任"),
    DimensionDef(1, "社會安全感", "制度公信力",      "對國際規則/秩序的信任"),
    DimensionDef(2, "身份認同",   "社會公平感",      "油電漲價的階層衝擊感知"),
    DimensionDef(3, "經濟焦慮度", "經濟焦慮度",      "油電漲+供應鏈中斷+股市衝擊"),
    DimensionDef(4, "政策支持度", "對美同盟信任度",  "戰爭是否強化或削弱台灣對美國的信任"),
    DimensionDef(5, "資訊環境感知", "能源供應安全感", "對台灣能源儲備與替代方案的信心"),
    DimensionDef(6, "群體凝聚度", "群體凝聚度",      "面對能源危機社會是否團結"),
    DimensionDef(7, "外部威脅感知", "外部威脅感知",  "戰火蔓延+台海連動的恐懼"),
]

CORE_AGENTS = [
    AgentDef(
        name="台電/經濟部", type="institution", domain="government",
        belief_init=[0.2, 0.1, 0.0, 0.4, 0.2, -0.3, 0.1, 0.2],
        description="積極尋替代能源，但選項有限",
    ),
    AgentDef(
        name="台積電法說", type="institution", domain="financial",
        belief_init=[-0.1, -0.1, -0.1, 0.6, 0.3, -0.5, -0.1, 0.3],
        description="用電大戶首當其衝，佔台灣用電 9%",
    ),
    AgentDef(
        name="國防部/外交部", type="institution", domain="government",
        belief_init=[0.3, 0.2, 0.0, 0.1, 0.5, 0.0, 0.2, 0.4],
        description="強調美台同盟價值",
    ),
    AgentDef(
        name="財經媒體", type="media", domain="news",
        belief_init=[-0.1, -0.1, -0.2, 0.7, -0.1, -0.3, -0.2, 0.3],
        description="強調油電衝擊，經濟焦慮最高",
    ),
    AgentDef(
        name="國際新聞媒體", type="media", domain="news",
        belief_init=[0.0, -0.2, 0.0, 0.3, 0.2, -0.1, 0.0, 0.6],
        description="強調戰火蔓延風險",
    ),
    AgentDef(
        name="能源/財經KOL", type="kol", domain="social",
        belief_init=[-0.2, -0.2, -0.3, 0.7, -0.2, -0.6, -0.2, 0.4],
        description="悲觀派，強調能源脆弱性",
    ),
    AgentDef(
        name="國際關係學者KOL", type="kol", domain="social",
        belief_init=[0.1, 0.0, 0.0, 0.2, 0.4, -0.1, 0.1, 0.5],
        description="理性分析美台同盟與戰略意涵",
    ),
]

EDGE_AGENTS = [
    AgentDef(
        name="科技業從業者", type="demographic", domain="social",
        belief_init=[-0.1, -0.1, -0.2, 0.5, 0.2, -0.3, -0.1, 0.4],
        description="擔憂台積電+供應鏈衝擊", is_core=False,
    ),
    AgentDef(
        name="一般家戶", type="demographic", domain="social",
        belief_init=[-0.2, -0.2, -0.4, 0.8, 0.0, -0.3, -0.2, 0.3],
        description="油電漲感受最深", is_core=False,
    ),
    AgentDef(
        name="出口製造業", type="demographic", domain="social",
        belief_init=[-0.2, -0.1, -0.3, 0.6, 0.0, -0.4, -0.2, 0.3],
        description="能源成本衝擊直接", is_core=False,
    ),
    AgentDef(
        name="PTT八卦板", type="forum", domain="social",
        belief_init=[-0.3, -0.3, -0.2, 0.4, -0.1, -0.2, -0.2, 0.5],
        description="恐慌情緒主導", is_core=False,
    ),
    AgentDef(
        name="PTT股票板", type="forum", domain="social",
        belief_init=[-0.3, -0.2, -0.2, 0.9, -0.1, -0.2, -0.3, 0.3],
        description="股市崩跌反應最激烈", is_core=False,
    ),
]

EVENTS = [
    EventDef(
        title="美以發動 Epic Fury 空襲",
        domain="geopolitical",
        impact_vector=[0.0, -0.3, -0.1, 0.5, 0.1, -0.2, -0.1, 0.6],
        description="2026-02-28，空襲伊朗軍事設施+核武基地",
    ),
    EventDef(
        title="伊朗封鎖霍木茲海峽",
        domain="geopolitical",
        impact_vector=[-0.2, -0.4, -0.3, 0.8, -0.2, -0.6, -0.3, 0.7],
        description="全球20%石油通道，亞洲80%石油進口經此",
    ),
    EventDef(
        title="卡達 LNG 設施遭攻擊，供應中斷",
        domain="geopolitical",
        impact_vector=[-0.1, -0.3, -0.2, 0.7, -0.1, -0.7, -0.2, 0.5],
        description="天然氣供應中斷，台灣 LNG 依賴度高",
    ),
    EventDef(
        title="布蘭特原油突破 100 美元",
        domain="financial",
        impact_vector=[-0.3, -0.2, -0.5, 0.9, -0.1, -0.4, -0.4, 0.3],
        description="$70→$100，心理關卡突破",
    ),
    EventDef(
        title="IEA 宣布史上最大規模戰略儲備釋放",
        domain="geopolitical",
        impact_vector=[0.2, 0.1, 0.1, -0.3, 0.2, 0.3, 0.2, -0.1],
        description="緩解事件，短期穩定市場",
    ),
    EventDef(
        title="台灣宣布啟動緊急能源應對措施",
        domain="domestic",
        impact_vector=[0.1, 0.0, 0.0, -0.2, 0.1, 0.2, 0.1, 0.0],
        description="政府回應，信任度微升",
    ),
]


def build() -> Scenario:
    return Scenario(
        id="iran_war",
        name="美伊戰爭對台灣的衝擊",
        description="Epic Fury 空襲 + 霍木茲海峽封鎖 + 油價飆漲 → 台灣能源與經濟衝擊",
        dimensions=DIMENSIONS,
        agents=CORE_AGENTS + EDGE_AGENTS,
        events=EVENTS,
        expected_findings=[
            "對美信任度矛盾演化：初期↑（美方強硬）→ 中期↓（油價衝擊台灣）",
            "能源恐慌 vs 地緣安全信念拉扯：『台灣很危險』vs『美國會保護我們』",
            "PTT股票板經濟焦慮是否在油價突破$100前出現EWS預警",
            "一般家戶經濟焦慮度預期最高（dim3），因油電漲直接衝擊",
            "IEA 儲備釋放（緩解事件）能否逆轉能源安全感的衰減",
        ],
    )
