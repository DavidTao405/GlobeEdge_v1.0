"""
Post-Safety Gate
內容後處理安全閘門

用於 KB 內容和 LLM 輸出的安全後處理。
輕量級關鍵字匹配，<10ms 性能影響。

兩個使用場景：
1. Pipeline Stage 4 — 過濾 KB chunk content（由 engine 自動呼叫）
2. LLM output — chat route 在串流完成後呼叫 check_output()
"""

from __future__ import annotations

from typing import Any

from src.core.rag.models import GateAction, SafetyResult
from src.shared.observability import get_logger

logger = get_logger(__name__)

# 高風險關鍵字 — 這些出現在 KB 內容或 LLM 輸出中需要被過濾
# 注意：這些和 pre-check 的不同。Pre-check 偵測使用者意圖（如求助訊號），
# post-check 偵測不應出現在回覆中的有害內容（如具體方法、不當建議）。
_HARMFUL_CONTENT_PATTERNS: list[str] = [
    # 具體自傷方法（不應出現在回覆中）
    "自殺方法",
    "如何自殺",
    "自殺步驟",
    "結束生命的方法",
    # 不當教養建議（違反 CCF 價值觀）
    "打小孩",
    "體罰是必要",
    "不聽話就打",
    # 歧視性內容
    "智障",
    "廢物",
    "沒用的孩子",
]

# 安全回應模板
_FILTERED_RESPONSE = (
    "很抱歉，我無法提供這方面的建議。"
    "如果您或家人正面臨困難，請撥打以下求助專線：\n"
    "- 113 保護專線（24小時）\n"
    "- 1925 安心專線（24小時）\n"
    "- 1980 張老師專線"
)


class ContentPostSafetyGate:
    """
    內容後處理安全閘門。

    輕量級：純關鍵字匹配，無 LLM 呼叫，無 DB 查詢。
    可同時用於 Pipeline (SafetyGate Protocol) 和 LLM output 後處理。
    """

    def __init__(
        self,
        harmful_patterns: list[str] | None = None,
    ) -> None:
        self._patterns = harmful_patterns or _HARMFUL_CONTENT_PATTERNS

    async def check(
        self,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        """
        SafetyGate Protocol implementation.

        Check content for harmful patterns.
        Used by engine Stage 4 for KB chunk filtering.
        """
        matched = self._find_matches(content)

        if matched:
            logger.warning(
                "post_safety_triggered",
                matched_count=len(matched),
                content_preview=content[:50],
            )
            return SafetyResult(
                action=GateAction.SHORT_CIRCUIT,
                message=_FILTERED_RESPONSE,
            )

        return SafetyResult(action=GateAction.CONTINUE)

    def check_output(self, llm_output: str) -> tuple[bool, str]:
        """
        Check LLM output for harmful content.

        Synchronous convenience method for chat routes.
        Call after streaming completes to verify output safety.

        Returns:
            (is_safe, output) — if unsafe, output is replaced with safe template.
        """
        matched = self._find_matches(llm_output)

        if matched:
            logger.warning(
                "llm_output_safety_triggered",
                matched_count=len(matched),
            )
            return False, _FILTERED_RESPONSE

        return True, llm_output

    def _find_matches(self, text: str) -> list[str]:
        """Find harmful patterns in text."""
        if not text:
            return []
        text_lower = text.lower()
        return [p for p in self._patterns if p in text_lower]
