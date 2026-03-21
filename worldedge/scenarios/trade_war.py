"""議題四：美中貿易戰 2.0（川普關稅）。

2025 川普關稅政策對台灣出口的直接衝擊 + 台積電赴美設廠爭議 + 供應鏈重組。
獨特分析角度：金融→輿論傳遞路徑（法說會→KOL→散戶→一般輿論）。
"""

from .base import AgentDef, DimensionDef, EventDef, Scenario

DIMENSIONS = [
    DimensionDef(0, "媒體信任度", "政府信任度",      "對政府貿易談判能力的信任"),
    DimensionDef(1, "社會安全感", "制度公信力",      "對 WTO/國際規則的信任"),
    DimensionDef(2, "身份認同",   "社會公平感",      "出口導向 vs 內需的利益分配"),
    DimensionDef(3, "經濟焦慮度", "經濟焦慮度",      "核心維度，關稅直接衝擊"),
    DimensionDef(4, "政策支持度", "對美信任度",      "覆蓋通用『政策支持度』"),
    DimensionDef(5, "資訊環境感知", "供應鏈韌性信心", "覆蓋通用『變革意願』"),
    DimensionDef(6, "群體凝聚度", "群體凝聚度",      "出口業 vs 內需業的利益衝突"),
    DimensionDef(7, "外部威脅感知", "外部威脅感知",  "美中博弈下台灣的地緣脆弱感"),
]

CORE_AGENTS = [
    AgentDef(
        name="台積電法說", type="institution", domain="financial",
        belief_init=[0.1, 0.1, 0.0, 0.2, 0.5, 0.4, 0.1, 0.2],
        description="樂觀但謹慎",
    ),
    AgentDef(
        name="鴻海/台灣電子業", type="institution", domain="financial",
        belief_init=[-0.1, -0.1, -0.2, 0.5, 0.2, -0.2, -0.1, 0.3],
        description="受衝擊大",
    ),
    AgentDef(
        name="財政部/經濟部", type="institution", domain="government",
        belief_init=[0.3, 0.2, 0.0, 0.1, 0.3, 0.3, 0.2, 0.1],
        description="官方偏樂觀",
    ),
    AgentDef(
        name="工商時報", type="media", domain="news",
        belief_init=[0.0, -0.1, -0.1, 0.4, 0.2, 0.0, -0.1, 0.2],
        description="財經媒體",
    ),
    AgentDef(
        name="財經YouTuber", type="kol", domain="social",
        belief_init=[-0.1, -0.1, -0.1, 0.5, 0.1, 0.1, -0.1, 0.2],
        description="影響散戶",
    ),
    AgentDef(
        name="財經分析師KOL", type="kol", domain="social",
        belief_init=[-0.2, -0.2, -0.2, 0.4, -0.1, -0.3, -0.1, 0.3],
        description="偏悲觀",
    ),
]

EDGE_AGENTS = [
    AgentDef(
        name="出口製造業族群", type="demographic", domain="social",
        belief_init=[-0.2, -0.2, -0.3, 0.7, -0.2, -0.2, -0.2, 0.3],
        description="直接受衝擊", is_core=False,
    ),
    AgentDef(
        name="股市散戶", type="demographic", domain="social",
        belief_init=[-0.1, -0.1, -0.1, 0.5, 0.1, 0.1, -0.1, 0.2],
        description="跟著法說走", is_core=False,
    ),
    AgentDef(
        name="一般受薪族", type="demographic", domain="social",
        belief_init=[0.0, 0.0, -0.1, 0.3, 0.0, 0.0, 0.0, 0.1],
        description="間接感受", is_core=False,
    ),
    AgentDef(
        name="PTT股票板", type="forum", domain="social",
        belief_init=[-0.2, -0.1, -0.1, 0.5, 0.0, 0.0, -0.2, 0.2],
        description="情緒波動大", is_core=False,
    ),
]

EVENTS = [
    EventDef(
        title="川普宣布對台灣加徵 32% 關稅",
        domain="geopolitical",
        impact_vector=[-0.4, -0.3, -0.2, 0.8, -0.5, -0.3, -0.2, 0.3],
        description="關稅衝擊 → 經濟焦慮暴增 + 對美信任度崩跌",
    ),
    EventDef(
        title="台積電亞利桑那廠量產達標",
        domain="financial",
        impact_vector=[0.2, 0.1, 0.0, -0.2, 0.3, 0.4, 0.1, -0.1],
        description="正面訊號 → 供應鏈韌性信心↑",
    ),
    EventDef(
        title="台灣出口連續三個月衰退",
        domain="domestic",
        impact_vector=[-0.2, -0.1, -0.2, 0.6, -0.1, -0.2, -0.2, 0.1],
        description="出口衰退 → 經濟焦慮持續升高",
    ),
]


def build() -> Scenario:
    return Scenario(
        id="trade_war",
        name="美中貿易戰 2.0（川普關稅）",
        description="川普關稅 + 台積電赴美 + 供應鏈重組",
        dimensions=DIMENSIONS,
        agents=CORE_AGENTS + EDGE_AGENTS,
        events=EVENTS,
        expected_findings=[
            "金融→輿論傳遞路徑：台積電法說→財經KOL→散戶→一般輿論（可量化 lag）",
            "川普關稅衝擊的傳遞時間：institution→media→demographic 約 3-5 步",
            "出口製造業 vs 一般受薪族的經濟焦慮度會明顯分歧",
            "對美信任度（dim 4）在關稅事件後衰減速度可校準 decay_rate",
        ],
    )
