"""Station 3b 資料模型 — 適配 PTT 政治輿論分析。

基於 CCF-ORG models.py，修改：
  QueryFilters: scenario → topic, age_group → board
  ScoredChunk: 加入 push_boo_ratio
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .protocols import (
        CitationFormatter,
        IngestionProfile,
        IntentProfile,
        QualityGate,
        Reranker,
        SafetyGate,
    )


class GateAction(Enum):
    CONTINUE = "continue"
    SHORT_CIRCUIT = "short_circuit"
    DEGRADE = "degrade"
    REFER = "refer"


@dataclass
class QueryFilters:
    """PTT 政治輿論的查詢過濾參數。"""
    topic: str | None = None          # 議題（dim0/dim1/.../dim7）
    board: str | None = None          # PTT 看板（Gossiping/HatePolitics）
    keywords: list[str] = field(default_factory=list)
    top_k: int = 10
    date_from: str | None = None      # ISO date string
    date_to: str | None = None
    min_interactions: int = 3          # 最少推噓互動數


@dataclass
class ScoredChunk:
    """PTT 文章的評分結果。"""
    chunk_id: str                     # ptt_article URL
    content: str                      # 文章標題
    score: float                      # 檢索分數
    # PTT 特有欄位
    board: str = ""
    push_count: int = 0
    boo_count: int = 0
    arrow_count: int = 0
    push_boo_ratio: float = 0.5       # 推噓比 [0, 1]
    author: str = ""
    date: str = ""
    # 通用 metadata
    metadata: dict = field(default_factory=dict)


@dataclass
class SafetyResult:
    action: GateAction
    message: str = ""
    referral_urgency: str | None = None
    emergency_resources: list[str] = field(default_factory=list)


@dataclass
class GateResult:
    action: GateAction
    grade: str = ""
    confidence: float = 0.0
    strategy: str = "NORMAL"
    reasoning: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class RetrievalLayer:
    """單一檢索層的設定。"""
    retriever: Any  # Retriever protocol
    weight: float = 1.0
    name: str = ""


@dataclass
class PipelineProfile:
    """PTT 政治輿論 RAG 的完整設定。"""
    name: str
    intent: Any                        # IntentProfile
    safety_gate: Any | None = None     # SafetyGate
    retrieval_layers: list[RetrievalLayer] = field(default_factory=list)
    reranker: Any | None = None        # Reranker
    quality_gates: list[Any] = field(default_factory=list)  # QualityGate[]
    citation: Any | None = None        # CitationFormatter
    ingestion: Any | None = None       # IngestionProfile
    post_safety_gate: Any | None = None  # SafetyGate
