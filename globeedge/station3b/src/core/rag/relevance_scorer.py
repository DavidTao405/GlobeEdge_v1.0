"""Station 3b 相關性評分 — 加入 PTT push_boo_ratio 維度。

基於 CCF-ORG relevance_scorer.py，新增：
  weight_pushboo: PTT 推噓比權重（高推噓比 = 高社會共識 = 更可靠的立場訊號）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ScoredChunk


@dataclass
class RelevanceConfig:
    weight_retrieval: float = 0.35   # 原始檢索分數
    weight_topic: float = 0.20      # 議題匹配度（替代 scenario）
    weight_overlap: float = 0.15    # 字詞重疊度
    weight_pushboo: float = 0.30    # ★ PTT 推噓比權重（新增）
    top_k: int = 5


def score_relevance(
    chunks: list[ScoredChunk],
    query: str,
    intent_topic: str | None = None,
    config: RelevanceConfig | None = None,
) -> list[ScoredChunk]:
    """對 chunks 進行多維度評分，回傳 top-K。"""
    if config is None:
        config = RelevanceConfig()
    if not chunks:
        return []

    scored = []
    max_retrieval = max(c.score for c in chunks) if chunks else 1.0
    max_retrieval = max(max_retrieval, 1e-9)

    query_bigrams = _bigrams(query)

    for chunk in chunks:
        # 1. 檢索分數（正規化）
        s_retrieval = chunk.score / max_retrieval

        # 2. 議題匹配
        s_topic = 0.0
        if intent_topic and chunk.metadata.get("topic"):
            s_topic = 1.0 if chunk.metadata["topic"] == intent_topic else 0.0

        # 3. 字詞重疊
        chunk_bigrams = _bigrams(chunk.content)
        if query_bigrams and chunk_bigrams:
            overlap = len(query_bigrams & chunk_bigrams)
            s_overlap = overlap / max(len(query_bigrams), 1)
        else:
            s_overlap = 0.0

        # 4. ★ 推噓比 — PTT 特有
        # 高推噓互動 + 明確方向（遠離 0.5）= 更可靠的立場訊號
        total_pb = chunk.push_count + chunk.boo_count
        if total_pb >= 3:
            # 方向明確度：距離 0.5 越遠越好
            direction_clarity = abs(chunk.push_boo_ratio - 0.5) * 2  # [0, 1]
            # 互動量加權（log scale）
            import math
            volume_bonus = min(math.log(total_pb + 1) / 5, 1.0)  # cap at 1
            s_pushboo = direction_clarity * 0.7 + volume_bonus * 0.3
        else:
            s_pushboo = 0.0  # 互動太少，不可靠

        # 加權合計
        final_score = (
            config.weight_retrieval * s_retrieval
            + config.weight_topic * s_topic
            + config.weight_overlap * s_overlap
            + config.weight_pushboo * s_pushboo
        )
        chunk.score = round(final_score, 4)
        scored.append(chunk)

    scored.sort(key=lambda c: -c.score)
    return scored[:config.top_k]


def _bigrams(text: str) -> set[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    bg = set()
    for t in tokens:
        for i in range(len(t) - 1):
            bg.add(t[i:i+2])
    return bg
