"""AI 輔助 b(0) 參數估計 — 用本地 LLM 從文本推斷 Agent 初始信念向量。

使用 Ollama + Qwen3.5:9b（/no_think 模式，快速穩定 JSON 輸出）。
temperature=0.1，要穩定不要創意。

用法:
    estimator = BeliefEstimator()
    result = estimator.estimate(
        agent_name="台電官方",
        agent_type="institution",
        topic="台灣能源政策",
        texts=["台電宣布電費調漲...", "核電重啟爭議..."],
    )
    print(result.vector)     # [0.2, 0.1, ...]
    print(result.confidence) # 0.75
"""

import json
import logging
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3.5:9b"

# ── 系統提示 ──────────────────────────────────────────────

SYSTEM_PROMPT = """/no_think
You are a social science research assistant. Your task is to estimate the initial belief vector for a social agent based on provided context.

## Belief Dimensions (8 dimensions, each from -1.0 to +1.0)

| Index | Name | -1.0 means | +1.0 means |
|-------|------|------------|------------|
| 0 | 政府信任度 (Government Trust) | Deep distrust | Strong trust |
| 1 | 制度公信力 (Institutional Credibility) | Institutions failing | Institutions working |
| 2 | 社會公平感 (Social Fairness) | Very unfair | Very fair |
| 3 | 經濟焦慮度 (Economic Anxiety) | No anxiety | Extreme anxiety |
| 4 | [Issue-specific A] (Policy Support) | Strong opposition | Strong support |
| 5 | [Issue-specific B] (Change Willingness) | Resist change | Embrace change |
| 6 | 群體凝聚度 (Social Cohesion) | Deeply divided | Strongly united |
| 7 | 外部威脅感知 (External Threat) | No threat | Extreme threat |

## Rules
1. Output ONLY valid JSON. No markdown, no explanation outside JSON.
2. Each value must be between -1.0 and +1.0 (two decimal places).
3. Confidence (0.0 to 1.0): how certain you are based on available evidence.
4. Reasoning: ONE sentence in Traditional Chinese, max 50 characters.
5. Consider the agent's TYPE: media tends to amplify, institutions are conservative, KOLs are opinionated, demographics are moderate, forums are volatile.

## Output Format
{"vector": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "confidence": 0.5, "reasoning": "簡短說明"}
"""


def _build_user_prompt(
    agent_name: str,
    agent_type: str,
    topic: str,
    texts: list[str],
    dimension_labels: list[str] | None = None,
) -> str:
    """組合 user prompt。"""
    # 截斷文本避免超出上下文
    text_block = ""
    for i, t in enumerate(texts[:5]):  # 最多 5 篇
        text_block += f"\n[Article {i+1}]: {t[:500]}"

    dim_info = ""
    if dimension_labels:
        dim_info = f"\nDimension 4 = {dimension_labels[4]}\nDimension 5 = {dimension_labels[5]}\n"

    return f"""Estimate the initial belief vector for this agent:

Agent: {agent_name}
Type: {agent_type}
Topic: {topic}
{dim_info}
Reference texts:{text_block}

Output JSON only:"""


# ── 資料結構 ──────────────────────────────────────────────

@dataclass
class BeliefEstimate:
    """LLM 估計結果。"""
    vector: list[float]         # 8 維，-1 到 1
    confidence: float           # 0 到 1
    reasoning: str              # LLM 簡短說明
    sources: list[str] = field(default_factory=list)
    model: str = MODEL
    raw_response: str = ""


# ── 估計器 ────────────────────────────────────────────────

class BeliefEstimator:
    """AI 輔助 b(0) 參數估計器。"""

    def __init__(
        self,
        ollama_url: str = OLLAMA_URL,
        model: str = MODEL,
        temperature: float = 0.1,
    ):
        self.ollama_url = ollama_url
        self.model = model
        self.temperature = temperature

    def estimate(
        self,
        agent_name: str,
        agent_type: str,
        topic: str,
        texts: list[str],
        dimension_labels: list[str] | None = None,
    ) -> BeliefEstimate:
        """呼叫 LLM 估計信念向量。"""
        user_prompt = _build_user_prompt(
            agent_name, agent_type, topic, texts, dimension_labels
        )

        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_p": 0.9,
            },
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            r = httpx.post(self.ollama_url, json=payload, timeout=180)
            r.raise_for_status()
            data = r.json()
            raw = data.get("message", {}).get("content", "")
        except Exception as e:
            logger.exception("Ollama request failed")
            return BeliefEstimate(
                vector=[0.0] * 8,
                confidence=0.0,
                reasoning=f"LLM request failed: {e}",
                sources=[t[:60] for t in texts[:3]],
            )

        return self._parse_response(raw, texts)

    def _parse_response(self, raw: str, texts: list[str]) -> BeliefEstimate:
        """解析 LLM JSON 回應。"""
        # 清理：去掉 markdown code fence 和 think 標籤
        cleaned = raw.strip()
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"```json\s*", "", cleaned)
        cleaned = re.sub(r"```\s*$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # 嘗試從 raw 中提取 JSON
            match = re.search(r"\{[^{}]*\"vector\"[^{}]*\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning("Failed to parse LLM response: %s", cleaned[:200])
                    return BeliefEstimate(
                        vector=[0.0] * 8,
                        confidence=0.0,
                        reasoning="JSON parse failed",
                        sources=[t[:60] for t in texts[:3]],
                        raw_response=raw,
                    )
            else:
                return BeliefEstimate(
                    vector=[0.0] * 8,
                    confidence=0.0,
                    reasoning="No JSON found in response",
                    sources=[t[:60] for t in texts[:3]],
                    raw_response=raw,
                )

        # 驗證並修正 vector
        vector = parsed.get("vector", [0.0] * 8)
        if not isinstance(vector, list) or len(vector) != 8:
            vector = (vector + [0.0] * 8)[:8]
        vector = [round(max(-1.0, min(1.0, float(v))), 2) for v in vector]

        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
        reasoning = str(parsed.get("reasoning", ""))[:100]

        return BeliefEstimate(
            vector=vector,
            confidence=round(confidence, 2),
            reasoning=reasoning,
            sources=[t[:60] for t in texts[:3]],
            model=self.model,
            raw_response=raw,
        )
