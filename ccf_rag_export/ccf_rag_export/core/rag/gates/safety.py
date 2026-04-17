"""
Safety Gate
安全閘門

包裝 CCFSafetyFilter + SafetyService，
在 RAG Pipeline 之前執行 pre-emptive 安全檢查。
統一為 SafetyGate Protocol。
"""

from __future__ import annotations

from typing import Any

from src.application.services.safety_service import SafetyService
from src.core.rag.models import GateAction, SafetyResult
from src.domain.entities.sensitive_keyword import KeywordAction, SensitiveKeyword
from src.infrastructure.shield.ccf_safety_filter import (
    CCFSafetyFilter,
    ReferralAction,
)
from src.shared.observability import get_logger

logger = get_logger(__name__)


class CCFSafetyGate:
    """
    CCF 安全閘門

    合併兩條現有安全路徑：
    1. CCFSafetyFilter.filter() — 同步關鍵字偵測（配置檔驅動）
    2. SafetyService.check_content() — DB 敏感詞偵測（DB 驅動）

    任一觸發 REQUIRED/EMERGENCY → SHORT_CIRCUIT + referral
    """

    def __init__(
        self,
        safety_filter: CCFSafetyFilter,
        safety_service: SafetyService,
        sensitive_keywords: list[SensitiveKeyword] | None = None,
    ) -> None:
        self._filter = safety_filter
        self._service = safety_service
        self._keywords = sensitive_keywords or []

    async def check(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        context = context or {}

        # Path 1: CCFSafetyFilter (sync, config-driven keywords)
        filter_result = self._filter.filter(query, context)

        if filter_result.referral_action in (
            ReferralAction.REQUIRED,
            ReferralAction.EMERGENCY,
        ):
            return SafetyResult(
                action=GateAction.SHORT_CIRCUIT,
                message=filter_result.response_message,
                referral_needed=True,
                referral_urgency=filter_result.referral_action.value,
                emergency_resources=[
                    r.get("phone", "") for r in filter_result.emergency_resources
                ],
            )

        # Path 2: SafetyService (async, DB-driven keywords)
        if self._keywords:
            svc_result = await self._service.check_content(
                query,
                self._keywords,
                context=context,
            )

            if self._service.should_require_referral(svc_result.result):
                return SafetyResult(
                    action=GateAction.SHORT_CIRCUIT,
                    message=svc_result.response_message,
                    referral_needed=True,
                    referral_urgency=svc_result.result.recommended_action.value,
                    emergency_resources=[
                        r.phone for r in svc_result.emergency_resources
                    ],
                )

            # Suggest referral → DEGRADE (don't short-circuit, but flag)
            if self._service.should_suggest_referral(svc_result.result):
                return SafetyResult(
                    action=GateAction.CONTINUE,
                    message=svc_result.response_message,
                    referral_needed=True,
                    referral_urgency="suggest",
                )

        # Safe — continue pipeline
        return SafetyResult(action=GateAction.CONTINUE)
