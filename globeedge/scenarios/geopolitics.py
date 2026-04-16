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
        belief_init=[0.1, 0.1, 0.0, 0.2, 0.5, 0.5, 0.59, 0.49],
        # b(0) PTT 校準：dim5 0.3→0.5, dim6 0.1→0.59, dim7 0.7→0.49
        description="偏鷹派",
    ),
    AgentDef(
        name="和平倡議KOL", type="kol", domain="social",
        belief_init=[-0.1, -0.1, 0.1, 0.1, -0.3, 0.55, 0.61, 0.29],
        # b(0) PTT 校準：dim5 0.4→0.55, dim6 0.2→0.61, dim7 -0.3→0.29
        description="偏鴿派",
    ),
]

EDGE_AGENTS = [
    AgentDef(
        name="役齡青年", type="demographic", domain="social",
        belief_init=[0.0, -0.2, -0.3, 0.2, 0.1, 0.4, 0.55, 0.43],
        # b(0) PTT 校準：dim5 0.1→0.4, dim6 -0.1→0.55, dim7 0.4→0.43
        description="兵役議題敏感", is_core=False,
    ),
    AgentDef(
        name="中老年族群", type="demographic", domain="social",
        belief_init=[0.1, 0.1, 0.0, 0.3, 0.2, 0.4, 0.63, 0.45],
        # b(0) PTT 校準：dim5 0.1→0.4, dim6 0.3→0.63, dim7 0.5→0.45
        description="歷史記憶影響", is_core=False,
    ),
    AgentDef(
        name="商業族群", type="demographic", domain="social",
        belief_init=[-0.1, -0.1, -0.2, 0.6, 0.0, 0.3, 0.55, 0.41],
        # b(0) PTT 校準：dim5 -0.1→0.3, dim6 -0.1→0.55, dim7 0.3→0.41
        description="憂商業衝擊", is_core=False,
    ),
    AgentDef(
        name="PTT軍武板", type="forum", domain="social",
        belief_init=[0.1, 0.1, 0.0, 0.1, 0.6, 0.49, 0.72, 0.63],
        # b(0) PTT 校準：dim5 0.4→0.49, dim6 0.2→0.72, dim7 0.7→0.63
        description="備戰意識高", is_core=False,
    ),
    AgentDef(
        name="PTT政黑板", type="forum", domain="social",
        belief_init=[-0.5, -0.3, -0.2, 0.2, -0.1, 0.19, 0.62, 0.44],
        # b(0) PTT 校準：dim5 0.0→0.19, dim6 -0.3→0.62, dim7 0.3→0.44
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
    # ── 2026-03 即時事件 ──────────────────────────────────
    EventDef(
        title="鄭習會宣布：鄭麗文 4/7 訪中",
        domain="geopolitical",
        impact_vector=[
            -0.05,  # dim0 政府信任度：藍綠雙方都對「政府整體」不信任加劇
            -0.05,  # dim1 制度公信力：在野黨「擅自外交」引發憲政爭議
             0.0,   # dim2 社會公平感
             0.0,   # dim3 經濟焦慮度
            -0.1,   # dim4 對美同盟信任度：靠近北京被視為破壞台美關係
             0.0,   # dim5 政治改革意願
            -0.1,   # dim6 群體凝聚度：推噓比 66:34，近期最高分歧
            -0.15,  # dim7 外部威脅感知：和緩訊號，連噓文也沒有說威脅更高
        ],
        description="爭議型事件：藍推綠噓，44篇/2377互動，推66%噓34%→55%",
        metadata={
            "date": "2026-03-30",
            "source_type": "diplomatic",
            "ptt_validation": {
                "articles": 44,
                "push_ratio": 0.30,
                "boo_ratio": 0.34,
                "neutral_ratio": 0.55,
                "event_type": "爭議型事件（藍綠對立衝擊）",
                "data_date": "2026-03-30 to 2026-03-31",
            },
            "calibration_note": (
                "★ 第二個有真實 PTT 資料支撐的 impact_vector。"
                "噓率 34% 是近期最高，dim6 群體凝聚度 -0.1 反映真實分裂。"
                "對比柯文哲判決（噓 11%，分裂型）→ 鄭習會是爭議型。"
            ),
        },
    ),
    EventDef(
        title="鄭習會進行/結果（4/7-4/12）",
        domain="geopolitical",
        impact_vector=[
            -0.03,  # dim0 政府信任度：比宣布時輕（-0.05 → -0.03），反彈降溫
            -0.03,  # dim1 制度公信力：同上
             0.0,   # dim2 社會公平感
             0.0,   # dim3 經濟焦慮度
            -0.05,  # dim4 對美同盟信任度：比宣布時輕（-0.1 → -0.05）
             0.0,   # dim5 政治改革意願
            -0.05,  # dim6 群體凝聚度：比宣布時輕（-0.1 → -0.05），事件落地後分裂降溫
            -0.20,  # dim7 外部威脅感知：比宣布更強（-0.15 → -0.20），「一家人」訊號明確
        ],
        description="★ 實際落地：爭議降溫（噓率 34%→27%），159 篇/11449 互動，推 73% 噓 27%",
        metadata={
            "date": "2026-04-12",
            "source_type": "diplomatic",
            "ptt_validation": {
                "articles": 159,
                "push_ratio": 0.342,
                "boo_ratio": 0.129,
                "neutral_ratio": 0.529,
                "push_boo_ratio": "73:27",
                "event_type": "爭議型（實際落地後反彈降溫）",
                "peak_date": "2026-04-10",
                "peak_day_articles": 73,
                "data_date": "2026-04-07 to 2026-04-12",
                "top_article": "習近平為何不想打台灣？（推448/噓62）",
            },
            "calibration_note": (
                "★ 第三個有真實 PTT 資料支撐的 impact_vector。"
                "比對『鄭習會宣布』：宣布時噓率 34%（高度爭議），實際會面 27%（爭議降溫）。"
                "關鍵：dim7 外部威脅感知從 -0.15 加強到 -0.20 — "
                "習近平親口『兩岸一家人』的和緩訊號效果明確，"
                "而 dim6 群體凝聚度從 -0.1 減輕到 -0.05 — 分裂程度降低。"
                "這是實際事件 vs 預期落差的重要案例。"
            ),
        },
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
