"""PTT 政治輿論 Profile — Station 3b 的 PipelineProfile 實作。

對應 CCF-ORG 的 ccf_parenting.py。
定義 PTT 政治討論的：
  Intent → 議題維度分類
  Retrieval → fulltext + structured 雙層
  Quality → fact_check + ptt_quality
  Citation → 推噓比格式
"""

from __future__ import annotations

from globeedge.station3b.src.core.rag.gates.fact_check import FactCheckGate
from globeedge.station3b.src.core.rag.gates.ptt_quality import PTTQualityGate
from globeedge.station3b.src.core.rag.models import (
    PipelineProfile,
    QueryFilters,
    RetrievalLayer,
    ScoredChunk,
)
from globeedge.station3b.src.core.rag.retrievers.fulltext import FullTextRetriever
from globeedge.station3b.src.core.rag.retrievers.structured import StructuredRetriever


# ── 維度關鍵字對應 ──────────────────────────────────────────

DIM_KEYWORDS = {
    "dim0": {"name": "政府信任度",   "keywords": ["賴清德", "民進黨", "國民黨", "執政", "下台"]},
    "dim1": {"name": "制度公信力",   "keywords": ["柯文哲", "京華城", "判決", "司法", "違憲"]},
    "dim2": {"name": "社會公平感",   "keywords": ["貧富", "階級", "公平", "世代"]},
    "dim3": {"name": "經濟焦慮度",   "keywords": ["房價", "物價", "薪資", "通膨", "失業"]},
    "dim4": {"name": "對美信任度",   "keywords": ["美國", "川普", "軍售", "台美"]},
    "dim5": {"name": "政治改革意願", "keywords": ["罷免", "民主", "改革", "青鳥"]},
    "dim6": {"name": "群體凝聚度",   "keywords": ["黃國昌", "民眾黨", "李貞秀", "開除"]},
    "dim7": {"name": "外部威脅感知", "keywords": ["鄭習會", "鄭麗文", "習近平", "兩岸", "訪中"]},
}


class PTTPoliticsIntentProfile:
    """PTT 政治議題意圖分析。"""

    def analyze(self, query: str, dim: str | None = None) -> QueryFilters:
        if dim and dim in DIM_KEYWORDS:
            info = DIM_KEYWORDS[dim]
            return QueryFilters(
                topic=dim,
                keywords=info["keywords"],
                top_k=10,
            )
        # 無指定維度 → 全局搜尋
        return QueryFilters(
            topic=None,
            keywords=query.split()[:5],
            top_k=20,
        )


class PTTPoliticsCitation:
    """PTT 引用格式。"""

    def format(self, chunks: list[ScoredChunk]) -> str:
        lines = []
        for i, c in enumerate(chunks, 1):
            lines.append(
                f"[{i}] [{c.board}] {c.content[:60]} "
                f"(推{c.push_count}/噓{c.boo_count}, "
                f"ratio={c.push_boo_ratio:.0%})"
            )
        return "\n".join(lines)


def build_ptt_politics_profile(dim: str = "dim0") -> PipelineProfile:
    """建立 PTT 政治輿論 Pipeline Profile。"""
    dim_name = DIM_KEYWORDS.get(dim, {}).get("name", dim)
    return PipelineProfile(
        name=f"ptt_politics_{dim}",
        intent=PTTPoliticsIntentProfile(),
        safety_gate=None,
        retrieval_layers=[
            RetrievalLayer(
                retriever=FullTextRetriever(),
                weight=0.6,
                name="fulltext_jieba",
            ),
            RetrievalLayer(
                retriever=StructuredRetriever(),
                weight=0.4,
                name="structured_sql",
            ),
        ],
        reranker=None,
        quality_gates=[
            FactCheckGate(),
            PTTQualityGate(dim_name=dim_name),
        ],
        citation=PTTPoliticsCitation(),
    )
