"""
RAG Pipeline Data Models
RAG 管線資料結構

所有 Protocol 方法的輸入/輸出型別定義。
與 domain entities 分離，避免循環依賴。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import (
        CitationFormatter,
        IngestionProfile,
        IntentProfile,
        QualityGate,
        Reranker,
        Retriever,
        SafetyGate,
    )


class GateAction(Enum):
    """閘門動作"""

    CONTINUE = "continue"  # 繼續 pipeline
    SHORT_CIRCUIT = "short_circuit"  # 立即返回（Safety 觸發）
    DEGRADE = "degrade"  # 降級策略（CRAG Grade B）
    REFER = "refer"  # 轉介（CRAG Grade C / Confidence LOW）


@dataclass
class QueryFilters:
    """檢索過濾條件"""

    scenario: str | None = None
    age_group: str | None = None
    risk_level: str | None = None
    keywords: list[str] = field(default_factory=list)
    metadata_filters: dict = field(default_factory=dict)
    text_query: str | None = None
    top_k: int = 10


@dataclass
class ScoredChunk:
    """帶分數的檢索結果"""

    chunk_id: str
    content: str
    score: float
    source: str  # "vector" / "fulltext" / "structured"
    metadata: dict = field(default_factory=dict)
    # CCF 特有
    scenario: str | None = None
    age_groups: list[str] = field(default_factory=list)
    risk_level: str | None = None


@dataclass
class SafetyResult:
    """安全閘門結果"""

    action: GateAction
    message: str | None = None  # 短路時的回應內容
    referral_needed: bool = False
    referral_urgency: str | None = None
    emergency_resources: list[str] = field(default_factory=list)


@dataclass
class GateResult:
    """品質閘門結果"""

    action: GateAction
    grade: str | None = None  # A/B/C (CRAG) 或 HIGH/MEDIUM/LOW (Confidence)
    confidence: float = 0.0
    strategy: str | None = None  # NORMAL / CAUTIOUS / LLM_FALLBACK
    reasoning: str | None = None
    referral_needed: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class RetrievalLayer:
    """檢索層配置"""

    retriever: Retriever
    weight: float
    name: str


@dataclass
class PipelineProfile:
    """
    完整的 RAG Pipeline 配置。

    CCF 版本比 V4 多了 safety_gate 和雙層 quality_gates。
    每個 Profile 定義一套完整的 RAG 策略。
    """

    name: str
    intent: IntentProfile
    safety_gate: SafetyGate
    retrieval_layers: list[RetrievalLayer]
    reranker: Reranker | None = None  # 可選 — None 時跳過 rerank
    quality_gates: list[QualityGate] = field(default_factory=list)  # 可串聯（CRAG → Confidence）
    citation: CitationFormatter | None = None
    ingestion: IngestionProfile | None = None
    post_safety_gate: SafetyGate | None = None  # 可選 — KB 內容後處理安全檢查
