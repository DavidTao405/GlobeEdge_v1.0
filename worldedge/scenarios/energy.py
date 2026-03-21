"""議題一：台灣能源政策。

AI 算力需求爆增 + 淨零排放壓力 + 核電公投爭議。
PTT 資料最豐富，維度最清晰，建議第一個執行。
"""

from .base import AgentDef, DimensionDef, EventDef, Scenario

DIMENSIONS = [
    DimensionDef(0, "媒體信任度", "政府信任度",      "對台電、能源局的信任"),
    DimensionDef(1, "社會安全感", "制度公信力",      "對能源政策制定過程的信任"),
    DimensionDef(2, "身份認同",   "社會公平感",      "電費漲價的階層衝擊感知"),
    DimensionDef(3, "經濟焦慮度", "經濟焦慮度",      "電費上漲 + 缺電對產業的衝擊"),
    DimensionDef(4, "政策支持度", "核電接受度",      "覆蓋通用『政策支持度』"),
    DimensionDef(5, "資訊環境感知", "再生能源意願",  "覆蓋通用『變革意願』"),
    DimensionDef(6, "群體凝聚度", "群體凝聚度",      "能源議題是否造成社會撕裂"),
    DimensionDef(7, "外部威脅感知", "外部威脅感知",  "能源安全 / 對中依賴的恐懼"),
]

# ── 核心節點 ──────────────────────────────────────────────

CORE_AGENTS = [
    AgentDef(
        name="台電官方", type="institution", domain="government",
        belief_init=[0.2, 0.3, 0.0, 0.1, -0.3, 0.5, 0.2, 0.1],
        description="官方立場偏綠能",
    ),
    AgentDef(
        name="工商時報", type="media", domain="news",
        belief_init=[-0.1, -0.1, -0.2, 0.4, 0.4, 0.1, -0.1, 0.2],
        description="財經媒體憂缺電",
    ),
    AgentDef(
        name="自由時報", type="media", domain="news",
        belief_init=[0.1, 0.1, 0.1, 0.2, -0.5, 0.6, 0.1, 0.1],
        description="反核立場明顯",
    ),
    AgentDef(
        name="聯合報", type="media", domain="news",
        belief_init=[0.0, 0.0, 0.0, 0.3, 0.3, 0.2, 0.0, 0.1],
        description="較中立",
    ),
    AgentDef(
        name="台積電法說", type="institution", domain="financial",
        belief_init=[-0.1, -0.1, -0.1, 0.7, 0.3, 0.2, -0.1, 0.2],
        description="用電需求龐大",
    ),
    AgentDef(
        name="反核KOL", type="kol", domain="social",
        belief_init=[0.0, 0.1, 0.2, 0.2, -0.8, 0.7, -0.1, 0.0],
        description="立場鮮明",
    ),
    AgentDef(
        name="擁核KOL", type="kol", domain="social",
        belief_init=[-0.1, -0.1, -0.1, 0.3, 0.7, -0.2, -0.1, 0.3],
        description="工程師族群",
    ),
]

# ── 邊緣群組 ──────────────────────────────────────────────

EDGE_AGENTS = [
    AgentDef(
        name="科技業從業者", type="demographic", domain="social",
        belief_init=[-0.1, -0.1, -0.2, 0.6, 0.3, 0.1, -0.1, 0.2],
        description="憂缺電影響競爭力", is_core=False,
    ),
    AgentDef(
        name="一般家戶", type="demographic", domain="social",
        belief_init=[-0.2, -0.1, -0.3, 0.5, 0.0, 0.1, -0.1, 0.1],
        description="電費漲痛感強", is_core=False,
    ),
    AgentDef(
        name="環保族群", type="demographic", domain="social",
        belief_init=[0.1, 0.1, 0.2, 0.1, -0.6, 0.8, 0.2, 0.1],
        description="偏年輕", is_core=False,
    ),
    AgentDef(
        name="PTT八卦板", type="forum", domain="social",
        belief_init=[-0.4, -0.3, -0.2, 0.3, 0.1, 0.0, -0.2, 0.2],
        description="對政策普遍懷疑", is_core=False,
    ),
]

# ── 外部事件 ──────────────────────────────────────────────

EVENTS = [
    EventDef(
        title="台電宣布電費調漲",
        domain="domestic",
        impact_vector=[-0.3, -0.2, -0.4, 0.6, -0.1, 0.1, -0.2, 0.0],
        description="電費調漲 → 政府信任↓ 經濟焦慮↑ 社會公平感↓",
    ),
    EventDef(
        title="台灣大規模停電事件",
        domain="domestic",
        impact_vector=[-0.5, -0.4, -0.3, 0.8, 0.4, 0.1, -0.3, 0.2],
        description="停電 → 核電接受度急升 政府信任崩跌",
    ),
    EventDef(
        title="AI 資料中心用電需求報告",
        domain="domestic",
        impact_vector=[0.0, -0.1, -0.2, 0.5, 0.3, 0.0, -0.1, 0.1],
        description="AI 用電暴增 → 經濟焦慮↑ 核電接受度↑",
    ),
]


def build() -> Scenario:
    """建立能源政策情境。"""
    return Scenario(
        id="energy_policy",
        name="台灣能源政策",
        description="AI 算力需求 + 淨零排放 + 核電爭議",
        dimensions=DIMENSIONS,
        agents=CORE_AGENTS + EDGE_AGENTS,
        events=EVENTS,
        expected_findings=[
            "λ_max 預期高（兩個強烈對立陣營：反核 vs 擁核）",
            "科技業 vs 環保族群的信念向量會發散",
            "停電事件對『核電接受度』的影響速度比『再生能源意願』快",
            "台電官方→一般家戶的影響力因信任度低而有限",
        ],
    )
