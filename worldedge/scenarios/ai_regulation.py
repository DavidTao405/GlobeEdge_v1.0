"""議題二：AI 監管與就業衝擊。

全球 AI 監管浪潮 + 台灣 AI 基本法討論 + 生成式 AI 對白領工作的替代恐慌。
技術樂觀者 vs 勞工保護者的信念分裂。
"""

from .base import AgentDef, DimensionDef, EventDef, Scenario

DIMENSIONS = [
    DimensionDef(0, "媒體信任度", "政府信任度",      "對 AI 監管機構的信任"),
    DimensionDef(1, "社會安全感", "制度公信力",      "對 AI 基本法制定過程的信任"),
    DimensionDef(2, "身份認同",   "社會公平感",      "AI 利益分配是否公平"),
    DimensionDef(3, "經濟焦慮度", "經濟焦慮度",      "AI 取代工作的個人恐懼"),
    DimensionDef(4, "政策支持度", "AI監管支持度",    "覆蓋通用『政策支持度』"),
    DimensionDef(5, "資訊環境感知", "技術擁抱意願",  "覆蓋通用『變革意願』"),
    DimensionDef(6, "群體凝聚度", "群體凝聚度",      "技術派 vs 保守派的撕裂"),
    DimensionDef(7, "外部威脅感知", "外部威脅感知",  "中國 AI 追趕、美國管制的焦慮"),
]

CORE_AGENTS = [
    AgentDef(
        name="數位部官方", type="institution", domain="government",
        belief_init=[0.3, 0.3, 0.1, -0.1, 0.3, 0.6, 0.2, 0.1],
        description="官方偏樂觀",
    ),
    AgentDef(
        name="科技媒體", type="media", domain="news",
        belief_init=[0.1, 0.0, -0.1, -0.1, -0.1, 0.7, -0.1, 0.2],
        description="偏技術樂觀",
    ),
    AgentDef(
        name="勞工相關媒體", type="media", domain="news",
        belief_init=[-0.1, -0.1, -0.3, 0.6, 0.5, -0.2, -0.2, 0.1],
        description="強調就業衝擊",
    ),
    AgentDef(
        name="AI新創KOL", type="kol", domain="social",
        belief_init=[0.0, -0.1, 0.0, -0.2, -0.4, 0.9, -0.1, 0.3],
        description="反對監管",
    ),
    AgentDef(
        name="勞工團體KOL", type="kol", domain="social",
        belief_init=[-0.2, -0.1, -0.4, 0.7, 0.8, -0.3, -0.2, 0.1],
        description="要求保護",
    ),
    AgentDef(
        name="學術研究者", type="kol", domain="social",
        belief_init=[0.1, 0.2, 0.0, 0.1, 0.5, 0.4, 0.1, 0.2],
        description="中立偏謹慎",
    ),
    AgentDef(
        name="Bluesky台灣科技圈", type="forum", domain="social",
        belief_init=[0.0, 0.0, 0.0, 0.0, -0.1, 0.6, -0.1, 0.2],
        description="Bluesky 爬蟲已覆蓋",
    ),
]

EDGE_AGENTS = [
    AgentDef(
        name="科技業工程師", type="demographic", domain="social",
        belief_init=[0.0, 0.0, 0.0, -0.1, -0.2, 0.7, -0.1, 0.2],
        description="技術樂觀", is_core=False,
    ),
    AgentDef(
        name="白領辦公室族群", type="demographic", domain="social",
        belief_init=[-0.1, -0.1, -0.2, 0.5, 0.2, -0.1, -0.1, 0.1],
        description="有替代恐懼", is_core=False,
    ),
    AgentDef(
        name="傳統產業從業者", type="demographic", domain="social",
        belief_init=[-0.2, -0.2, -0.3, 0.7, 0.4, -0.3, -0.2, 0.1],
        description="威脅感強", is_core=False,
    ),
    AgentDef(
        name="PTT科技板", type="forum", domain="social",
        belief_init=[0.0, 0.0, 0.0, 0.0, -0.1, 0.5, -0.1, 0.2],
        description="工程師聚集", is_core=False,
    ),
]

EVENTS = [
    EventDef(
        title="OpenAI 發布 GPT-5 超越人類基準",
        domain="geopolitical",
        impact_vector=[0.0, -0.1, -0.2, 0.4, -0.1, 0.5, -0.2, 0.2],
    ),
    EventDef(
        title="台灣某大型企業宣布 AI 裁員計畫",
        domain="domestic",
        impact_vector=[-0.3, -0.2, -0.5, 0.8, 0.4, -0.3, -0.4, 0.1],
    ),
    EventDef(
        title="台灣 AI 基本法草案公告",
        domain="domestic",
        impact_vector=[0.2, 0.3, 0.1, -0.1, 0.4, 0.1, 0.2, 0.0],
    ),
    EventDef(
        title="中國 DeepSeek 超越美國模型",
        domain="geopolitical",
        impact_vector=[-0.1, -0.1, -0.1, 0.3, 0.1, 0.3, -0.1, 0.4],
    ),
]


def build() -> Scenario:
    return Scenario(
        id="ai_regulation",
        name="AI 監管與就業衝擊",
        description="AI 基本法 + 生成式 AI 替代恐慌 + 技術樂觀vs勞工保護",
        dimensions=DIMENSIONS,
        agents=CORE_AGENTS + EDGE_AGENTS,
        events=EVENTS,
        expected_findings=[
            "AI新創KOL→科技業工程師 影響力強，勞工KOL→傳統產業 反向同樣強",
            "兩群體信念向量 10-15 步後明顯發散（極化）",
            "CSD 可能在大型裁員事件後出現 Critical Slowing Down",
            "學術研究者的中立立場會被兩極拉扯",
        ],
    )
