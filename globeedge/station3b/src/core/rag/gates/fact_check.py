"""事實查核門 — 輕量級規則式過濾。

過濾明顯不可靠的 PTT 文章：
  推噓互動太少（< 3）
  標題太短（< 5 字）
  明顯無關（如廣告、徵人）
"""

from __future__ import annotations

import re

from globeedge.station3b.src.core.rag.models import GateAction, GateResult, ScoredChunk

# 無關標題模式
IRRELEVANT_PATTERNS = [
    r"^\[公告\]",
    r"^\[徵\s*(求|人|才)\]",
    r"^\[廣告\]",
    r"^\[贈送\]",
    r"^\[交易\]",
]
_IRRELEVANT_RE = [re.compile(p) for p in IRRELEVANT_PATTERNS]


class FactCheckGate:
    """輕量級事實查核 / 品質過濾。"""

    def evaluate(
        self,
        query: str,
        chunks: list[ScoredChunk],
        context: dict | None = None,
    ) -> GateResult:
        """過濾低品質 chunks。"""
        if not chunks:
            return GateResult(action=GateAction.DEGRADE, grade="C")

        filtered = []
        removed = 0
        for c in chunks:
            # 互動太少
            if (c.push_count + c.boo_count) < 3:
                removed += 1
                continue
            # 標題太短
            if len(c.content.strip()) < 5:
                removed += 1
                continue
            # 無關模式
            if any(p.search(c.content) for p in _IRRELEVANT_RE):
                removed += 1
                continue
            filtered.append(c)

        if not filtered:
            return GateResult(
                action=GateAction.DEGRADE, grade="C",
                reasoning=f"全部 {len(chunks)} 篇被過濾（互動不足或無關）",
            )

        # 更新 chunks in-place
        chunks.clear()
        chunks.extend(filtered)

        return GateResult(
            action=GateAction.CONTINUE, grade="A",
            confidence=0.9,
            reasoning=f"保留 {len(filtered)}/{len(filtered)+removed} 篇",
        )
