"""
RAG Pipeline Protocols
RAG 管線介面定義

所有可插拔元件的 Protocol 定義。
使用 @runtime_checkable 支援 isinstance() 驗證。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.domain.entities.kb_entry import KBEntry

    from .models import GateResult, QueryFilters, SafetyResult, ScoredChunk


# ─────────────────────────────────────────────────────────────
# 基礎 Protocol（與 V4 共用）
# ─────────────────────────────────────────────────────────────


@runtime_checkable
class IntentProfile(Protocol):
    """
    意圖分析策略

    負責：
    1. 提供意圖分析的 system prompt
    2. 定義意圖 metadata schema
    3. 從意圖分析結果提取檢索 filters
    """

    @property
    def name(self) -> str: ...

    def get_system_prompt(self) -> str: ...

    def get_metadata_schema(self) -> dict: ...

    def extract_filters(self, intent_result: dict) -> QueryFilters: ...


@runtime_checkable
class Retriever(Protocol):
    """
    單一檢索層

    每個 Retriever 負責一種檢索策略（向量/全文/結構化）。
    Pipeline Engine 透過 RetrievalLayer 組合多個 Retriever。
    """

    async def retrieve(
        self,
        query: str,
        filters: QueryFilters,
        top_k: int,
    ) -> list[ScoredChunk]: ...


@runtime_checkable
class Reranker(Protocol):
    """
    Reranker

    對檢索結果進行重新排序，提升相關性排序品質。
    可選元件 — Profile 中 reranker=None 時跳過。
    """

    async def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
    ) -> list[ScoredChunk]: ...


@runtime_checkable
class CitationFormatter(Protocol):
    """
    引用格式化

    將檢索結果格式化為 LLM 可用的引用文本。
    """

    def format(self, chunks: list[ScoredChunk]) -> str: ...


# ─────────────────────────────────────────────────────────────
# CCF 擴展 Protocol（V4 沒有）
# ─────────────────────────────────────────────────────────────


@runtime_checkable
class SafetyGate(Protocol):
    """
    安全閘門

    在 RAG 之前執行，可短路整個 Pipeline。
    V4 沒有這個概念（V4 用 Governance 審批，是 post-hoc）。
    CCF 的 Safety Pipeline 是 pre-emptive。
    """

    async def check(
        self,
        query: str,
        context: dict | None = None,
    ) -> SafetyResult: ...


@runtime_checkable
class QualityGate(Protocol):
    """
    品質閘門

    在檢索之後、生成之前執行。
    CCF 需要雙層: CRAG (規則) + Confidence (LLM)。
    V4 只需要一層 ComplianceGate。
    統一介面讓兩者可以串聯。
    """

    async def evaluate(
        self,
        query: str,
        chunks: list[ScoredChunk],
        context: dict | None = None,
    ) -> GateResult: ...


@runtime_checkable
class IngestionProfile(Protocol):
    """
    文件入庫策略

    定義如何準備嵌入文本和提取 metadata。
    不同 Profile 可以有不同的入庫策略。
    """

    def prepare_embedding_text(self, entry: KBEntry) -> str: ...

    def extract_metadata(self, entry: KBEntry) -> dict: ...
