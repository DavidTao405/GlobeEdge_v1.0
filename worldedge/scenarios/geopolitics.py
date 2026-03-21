"""議題三：地緣政治與戰亂溢出效應。

烏俄戰爭持續、中東局勢、美中博弈、台海緊張。
國際戰亂如何透過媒體傳遞影響台灣民眾的外部威脅感知與社會信念。

特殊優勢：signals/ 的 AIS、GDELT、adsb.lol 可直接接入。
"""

from .base import AgentDef, DimensionDef, EventDef, Scenario

DIMENSIONS = [
    DimensionDef(0, "媒體信任度", "政府信任度",      "對政府防衛能力的信任"),
    DimensionDef(1, "社會安全感", "制度公信力",      "對兵役/國防制度的信任"),
    DimensionDef(2, "身份認同",   "社會公平感",      "戰爭代價分配的公平感"),
    DimensionDef(3, "經濟焦慮度", "經濟焦慮度",      "戰爭風險對台灣經濟的衝擊"),
    DimensionDef(4, "政策支持度", "政策支持度",      "對台灣軍事/外交政策的支持"),
    DimensionDef(5, "資訊環境感知", "變革意願",      "願意犧牲/改變現狀的意願"),
    DimensionDef(6, "群體凝聚度", "群體凝聚度",      "面對外部威脅的社會凝聚"),
    DimensionDef(7, "外部威脅感知", "外部威脅感知",  "核心維度，最直接受影響"),
]

CORE_AGENTS = [
    AgentDef(
        name="公視/中央社", type="media", domain="news",
        belief_init=[0.2, 0.2, 0.0, 0.1, 0.2, 0.1, 0.2, 0.4],
        description="較客觀",
    ),
    AgentDef(
        name="三立/民視", type="media", domain="news",
        belief_init=[0.3, 0.1, 0.0, 0.2, 0.3, 0.2, 0.2, 0.6],
        description="偏強調威脅",
    ),
    AgentDef(
        name="中天/旺旺", type="media", domain="news",
        belief_init=[-0.3, -0.2, -0.1, 0.2, -0.2, -0.1, -0.1, -0.2],
        description="偏兩岸友好",
    ),
    AgentDef(
        name="國防部官方", type="institution", domain="government",
        belief_init=[0.5, 0.4, 0.1, 0.1, 0.5, 0.3, 0.3, 0.3],
        description="強調備戰",
    ),
    AgentDef(
        name="軍事分析KOL", type="kol", domain="social",
        belief_init=[0.1, 0.1, 0.0, 0.2, 0.5, 0.3, 0.1, 0.7],
        description="偏鷹派",
    ),
    AgentDef(
        name="和平倡議KOL", type="kol", domain="social",
        belief_init=[-0.1, -0.1, 0.1, 0.1, -0.3, 0.4, 0.2, -0.3],
        description="偏鴿派",
    ),
]

EDGE_AGENTS = [
    AgentDef(
        name="役齡青年", type="demographic", domain="social",
        belief_init=[0.0, -0.2, -0.3, 0.2, 0.1, 0.1, -0.1, 0.4],
        description="兵役議題敏感", is_core=False,
    ),
    AgentDef(
        name="中老年族群", type="demographic", domain="social",
        belief_init=[0.1, 0.1, 0.0, 0.3, 0.2, 0.1, 0.3, 0.5],
        description="歷史記憶影響", is_core=False,
    ),
    AgentDef(
        name="商業族群", type="demographic", domain="social",
        belief_init=[-0.1, -0.1, -0.2, 0.6, 0.0, -0.1, -0.1, 0.3],
        description="憂商業衝擊", is_core=False,
    ),
    AgentDef(
        name="PTT軍武板", type="forum", domain="social",
        belief_init=[0.1, 0.1, 0.0, 0.1, 0.6, 0.4, 0.2, 0.7],
        description="備戰意識高", is_core=False,
    ),
    AgentDef(
        name="PTT政黑板", type="forum", domain="social",
        belief_init=[-0.5, -0.3, -0.2, 0.2, -0.1, 0.0, -0.3, 0.3],
        description="普遍懷疑政府", is_core=False,
    ),
]

EVENTS = [
    EventDef(
        title="共軍環台軍演（2022-08 級別）",
        domain="geopolitical",
        impact_vector=[-0.2, -0.3, -0.1, 0.5, 0.3, 0.2, 0.4, 0.9],
        description="軍演 → 外部威脅感知暴增 + 群體凝聚度短暫升高",
    ),
    EventDef(
        title="台海出現不明軍艦群（AIS 偵測）",
        domain="geopolitical",
        impact_vector=[0.0, -0.1, 0.0, 0.3, 0.1, 0.1, 0.1, 0.7],
        description="AIS 即時訊號觸發",
    ),
    EventDef(
        title="美國對台軍售案通過",
        domain="geopolitical",
        impact_vector=[0.2, 0.2, 0.0, -0.1, 0.3, 0.1, 0.2, -0.2],
        description="軍售 → 安全感短暫提升",
    ),
    EventDef(
        title="中東戰火升級影響能源供應",
        domain="geopolitical",
        impact_vector=[0.0, -0.1, -0.1, 0.4, 0.0, 0.0, -0.1, 0.3],
        description="間接影響：能源安全焦慮",
    ),
]


def build() -> Scenario:
    return Scenario(
        id="geopolitics",
        name="地緣政治與戰亂溢出效應",
        description="台海緊張 + 美中博弈 + 國際戰亂溢出",
        dimensions=DIMENSIONS,
        agents=CORE_AGENTS + EDGE_AGENTS,
        events=EVENTS,
        expected_findings=[
            "三立/民視→中老年族群 vs 中天/旺旺→商業族群 產生反向信念演化",
            "外部軍事事件（AIS）的衝擊比新聞報導更快影響外部威脅感知（dim 7）",
            "可量化『台灣海峽軍事緊張 → 民眾感知傳遞時間』",
            "軍演事件會讓群體凝聚度短暫升高，但很快回落",
        ],
    )
