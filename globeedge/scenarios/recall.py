"""議題六：全台大罷免潮 ★ 即時議題。

2026 年台灣大規模罷免運動，藍綠雙方相互發動罷免。
台灣民主制度史上規模最大的政治動員事件之一。

預期：λ_max 是六個議題中最高的。
原因：台灣政治議題的信念分裂比任何經濟或地緣議題都更深。
"""

from .base import AgentDef, DimensionDef, EventDef, Scenario

DIMENSIONS = [
    DimensionDef(0, "媒體信任度", "政府信任度",      "對執政黨施政能力的信任"),
    DimensionDef(1, "社會安全感", "制度公信力",      "對選舉、罷免等民主制度的信任"),
    DimensionDef(2, "身份認同",   "社會公平感",      "罷免是否被公平使用的感知"),
    DimensionDef(3, "經濟焦慮度", "經濟焦慮度",      "政治動盪對經濟信心的衝擊"),
    DimensionDef(4, "政策支持度", "罷免制度認同度",  "認為罷免是正當民主工具 vs 政治鬥爭工具"),
    DimensionDef(5, "資訊環境感知", "政治改革意願",  "希望透過罷免改變現狀的積極程度"),
    DimensionDef(6, "群體凝聚度", "群體凝聚度",      "社會是否因罷免而撕裂"),
    DimensionDef(7, "外部威脅感知", "外部威脅感知",  "內部政治混亂是否給外部勢力可趁之機"),
]

CORE_AGENTS = [
    AgentDef(
        name="民進黨媒體", type="media", domain="news",
        belief_init=[0.4, 0.2, 0.1, 0.0, -0.2, -0.3, -0.2, 0.1],
        description="執政黨立場，反對被罷免",
    ),
    AgentDef(
        name="國民黨媒體", type="media", domain="news",
        belief_init=[-0.4, -0.1, -0.2, 0.1, 0.5, 0.4, -0.3, 0.1],
        description="在野黨立場，推動罷免",
    ),
    AgentDef(
        name="中立媒體（公視）", type="media", domain="news",
        belief_init=[0.0, 0.2, 0.0, 0.0, 0.1, 0.1, -0.1, 0.0],
        description="強調程序正當性",
    ),
    AgentDef(
        name="罷免發起KOL", type="kol", domain="social",
        belief_init=[-0.6, -0.2, -0.3, 0.1, 0.7, 0.8, -0.4, 0.1],
        description="強烈動員，政府信任極低",
    ),
    AgentDef(
        name="護政KOL", type="kol", domain="social",
        belief_init=[0.5, 0.1, 0.2, 0.0, -0.5, -0.4, -0.2, 0.1],
        description="反罷免動員",
    ),
    AgentDef(
        name="憲政學者KOL", type="kol", domain="social",
        belief_init=[0.0, 0.3, 0.1, 0.0, 0.2, 0.1, 0.0, 0.0],
        description="中立，關注制度面",
    ),
]

EDGE_AGENTS = [
    AgentDef(
        name="深藍選民", type="demographic", domain="social",
        belief_init=[-0.7, -0.3, -0.4, 0.2, 0.7, 0.6, -0.5, 0.2],
        description="強烈動員，政府信任最低", is_core=False,
    ),
    AgentDef(
        name="深綠選民", type="demographic", domain="social",
        belief_init=[0.6, 0.2, 0.3, 0.0, -0.4, -0.3, -0.3, 0.1],
        description="反動員，政府信任高", is_core=False,
    ),
    AgentDef(
        name="中間選民", type="demographic", domain="social",
        belief_init=[0.0, -0.2, -0.1, 0.1, 0.0, 0.0, -0.3, 0.0],
        description="觀望但漸失信心，政治疲憊",  is_core=False,
    ),
    AgentDef(
        name="PTT政黑板", type="forum", domain="social",
        belief_init=[-0.5, -0.3, -0.3, 0.1, 0.3, 0.2, -0.4, 0.1],
        description="政治對立最激烈", is_core=False,
    ),
    AgentDef(
        name="Dcard時事", type="forum", domain="social",
        belief_init=[0.0, -0.1, -0.1, 0.0, 0.0, -0.1, -0.2, 0.0],
        description="年輕族群，政治疲憊明顯", is_core=False,
    ),
]

EVENTS = [
    EventDef(
        title="第一批罷免連署達標",
        domain="domestic",
        impact_vector=[-0.2, -0.1, -0.2, 0.0, 0.3, 0.4, -0.5, 0.0],
        description="連署達標 → 罷免認同↑ 群體凝聚度↓↓",
    ),
    EventDef(
        title="罷免投票日前大規模造勢",
        domain="domestic",
        impact_vector=[-0.1, -0.2, -0.3, 0.1, 0.2, 0.3, -0.6, 0.0],
        description="造勢 → 極化加劇 群體凝聚度崩跌",
    ),
    EventDef(
        title="罷免成立（通過門檻）",
        domain="domestic",
        impact_vector=[-0.4, -0.3, -0.4, 0.2, 0.5, 0.2, -0.7, 0.0],
        description="罷免成立 → 政府信任崩跌 群體凝聚度最低點",
    ),
    EventDef(
        title="WBC Team Taiwan + 島嶼天光哏化事件",
        domain="social",
        impact_vector=[0.0, 0.0, 0.1, 0.0, -0.2, -0.1, 0.3, 0.0],
        description=(
            "WBC 全民歡樂 → 群體凝聚度短暫↑ 罷免認同度↓ 政治改革意願↓ "
            "注意力被搶走，政治動員效果被稀釋。"
            "迷因傳播快(3x) 但衰退也快(S≈1)，不觸發 Backfire"
        ),
    ),
]


def build() -> Scenario:
    return Scenario(
        id="recall",
        name="全台大罷免潮",
        description="藍綠相互罷免，台灣民主制度最大規模政治動員",
        dimensions=DIMENSIONS,
        agents=CORE_AGENTS + EDGE_AGENTS,
        events=EVENTS,
        expected_findings=[
            "λ_max 預期是六個議題中最高的（深藍/深綠最對立）",
            "中間選民的政治疲憊：信念漂向哪個方向？還是直接下降（政治冷感）？",
            "罷免動員的 variance 暴增是否在投票日前 14 天出現 EWS",
            "深藍 vs 深綠的 dim4（罷免認同度）spread 預期 > 1.2",
            "Dcard 時事（年輕族群）的政治疲憊 → dim6 群體凝聚度持續下降",
            "憲政學者KOL 的中立立場是否能維持，或被兩極拉扯",
        ],
    )
