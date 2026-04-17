"""
CCF Parenting Profile
CCF 親職支持 Pipeline Profile

組裝 CCF 專用的 RAG Pipeline 配置：
- IntentProfile: 包裝 IntentAnalyzer（10 情境分析）
- CitationFormatter: CCF 引用格式
- IngestionProfile: CCF 入庫策略
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.services.intent_analyzer import (
    INTENT_ANALYSIS_SYSTEM,
    SCENARIO_DEFINITIONS,
    IntentAnalyzer,
)
from src.core.rag.models import QueryFilters, ScoredChunk
from src.shared.observability import get_logger

if TYPE_CHECKING:
    from src.domain.entities.kb_entry import KBEntry

logger = get_logger(__name__)


class CCFParentingIntentProfile:
    """
    CCF 親職意圖分析 Profile.

    Wraps IntentAnalyzer for use as IntentProfile Protocol.
    """

    def __init__(self, intent_analyzer: IntentAnalyzer) -> None:
        self._analyzer = intent_analyzer

    @property
    def name(self) -> str:
        return "ccf_parenting"

    def get_system_prompt(self) -> str:
        scenario_list = "\n".join(
            f"- {s.value}: {desc}" for s, desc in SCENARIO_DEFINITIONS.items()
        )
        return INTENT_ANALYSIS_SYSTEM.format(scenario_list=scenario_list)

    def get_metadata_schema(self) -> dict:
        return {
            "scenario": "Enum: 10 種親職情境",
            "age_group": "Enum: 7 種年齡群組",
            "risk_level": "Enum: NORMAL/MEDIUM/HIGH",
            "keywords": "list[str]: 從 query 提取的關鍵詞",
        }

    def extract_filters(self, intent_result: dict) -> QueryFilters:
        return QueryFilters(
            scenario=intent_result.get("scenario"),
            age_group=intent_result.get("age_group"),
            keywords=intent_result.get("keywords", []),
            top_k=10,
        )


class CCFParentingCitation:
    """CCF 引用格式化"""

    def format(self, chunks: list[ScoredChunk]) -> str:
        if not chunks:
            return ""

        lines: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            scenario_label = chunk.scenario or "未分類"
            age_label = ", ".join(chunk.age_groups) if chunk.age_groups else "全年齡"
            lines.append(
                f"[{i}] 情境: {scenario_label} | 適用年齡: {age_label}\n"
                f"{chunk.content}"
            )

        return "\n\n---\n\n".join(lines)


class CCFParentingIngestion:
    """CCF 入庫策略"""

    def prepare_embedding_text(self, entry: KBEntry) -> str:
        """Compose embedding text: title + body + keywords + scenario + age."""
        parts = [entry.title, entry.body]

        if entry.keywords:
            parts.append("關鍵字: " + ", ".join(entry.keywords))

        if entry.scenario:
            scenario_val = entry.scenario.value if hasattr(entry.scenario, "value") else str(entry.scenario)
            parts.append(f"情境: {scenario_val}")

        if entry.age_groups:
            age_str = ", ".join(
                ag.value if hasattr(ag, "value") else str(ag)
                for ag in entry.age_groups
            )
            parts.append(f"適用年齡: {age_str}")

        return "\n".join(parts)

    def extract_metadata(self, entry: KBEntry) -> dict:
        return {
            "scenario": entry.scenario.value if hasattr(entry.scenario, "value") else str(entry.scenario),
            "age_groups": [
                ag.value if hasattr(ag, "value") else str(ag)
                for ag in entry.age_groups
            ] if entry.age_groups else [],
            "risk_level": entry.risk_level.value if hasattr(entry.risk_level, "value") else str(entry.risk_level),
            "keywords": entry.keywords or [],
        }
