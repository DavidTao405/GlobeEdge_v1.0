"""PTT 品質門 — 用 LLM 判斷文章是否反串。

替代 CCF-ORG 的 CRAG + Confidence gates。
用 Qwen3.5:9b 判斷 PTT 文章的真實立場。
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from globeedge.station3b.src.core.rag.models import GateAction, GateResult, ScoredChunk

logger = logging.getLogger(__name__)

OLLAMA_CHAT = "http://localhost:11434/api/chat"
CHAT_MODEL = "qwen3.5:9b"

# PTT 語境知識（嵌入 prompt）
PTT_CONTEXT = """【PTT 政黑板文化】
反串格式：用誇張正面語氣嘲諷、引用對方言論加諷刺結論、「推」跟在諷刺文後=認同諷刺。
真誠批評：直接指出具體問題、有數據或新聞佐證。
反串指標：語氣過度正面但無事實支撐、搭配嘲諷詞「笑死」「可憐哪」「超棒der」。"""


class PTTQualityGate:
    """PTT 反串品質門。"""

    def __init__(self, dim_name: str = "政府信任度"):
        self.dim_name = dim_name

    def evaluate(
        self,
        query: str,
        chunks: list[ScoredChunk],
        context: dict | None = None,
    ) -> GateResult:
        """評估 chunks 的整體品質。"""
        if not chunks:
            return GateResult(
                action=GateAction.DEGRADE,
                grade="C", confidence=0.0,
                strategy="NO_DATA", reasoning="無文章可評估",
            )

        # 對 top-3 文章做 LLM 判斷
        sarcasm_count = 0
        total_checked = min(3, len(chunks))
        for chunk in chunks[:total_checked]:
            result = self._classify_single(chunk)
            if result.get("is_sarcasm"):
                sarcasm_count += 1

        sarcasm_ratio = sarcasm_count / total_checked
        if sarcasm_ratio > 0.5:
            return GateResult(
                action=GateAction.DEGRADE,
                grade="C", confidence=0.3,
                strategy="HIGH_SARCASM",
                reasoning=f"Top-{total_checked} 文章中 {sarcasm_count} 篇疑似反串",
            )
        elif sarcasm_ratio > 0:
            return GateResult(
                action=GateAction.CONTINUE,
                grade="B", confidence=0.6,
                strategy="CAUTIOUS",
                reasoning=f"部分反串（{sarcasm_count}/{total_checked}），需謹慎",
            )
        else:
            return GateResult(
                action=GateAction.CONTINUE,
                grade="A", confidence=0.8,
                strategy="NORMAL",
                reasoning="無反串偵測",
            )

    def _classify_single(self, chunk: ScoredChunk) -> dict:
        """用 LLM 判斷單篇文章。"""
        prompt = f"""/no_think
{PTT_CONTEXT}

判斷以下 PTT 文章對「{self.dim_name}」的真實立場：

標題：{chunk.content[:100]}
推：{chunk.push_count}  噓：{chunk.boo_count}

回答 JSON（只回 JSON）：
{{"is_sarcasm": true/false, "stance": "positive/negative/neutral", "confidence": 0.0-1.0}}"""

        try:
            r = httpx.post(OLLAMA_CHAT, json={
                "model": CHAT_MODEL,
                "stream": False,
                "options": {"temperature": 0.05},
                "messages": [{"role": "user", "content": prompt}],
            }, timeout=30)
            r.raise_for_status()
            raw = r.json().get("message", {}).get("content", "")
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            match = re.search(r"\{[^}]+\}", raw)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.debug(f"LLM classify error: {e}")

        return {"is_sarcasm": False, "stance": "neutral", "confidence": 0.0}
