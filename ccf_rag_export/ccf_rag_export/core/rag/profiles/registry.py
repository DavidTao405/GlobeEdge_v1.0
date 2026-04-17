"""
Profile Registry
Pipeline Profile 註冊表

與 V4 相同的 Registry Pattern。
禁止 Engine 裡出現 if profile_name == "xxx"。
"""

from __future__ import annotations

from src.core.rag.models import PipelineProfile


class ProfileRegistry:
    """
    Pipeline Profile 註冊表

    Usage:
        registry = ProfileRegistry()
        registry.register(ccf_profile)
        profile = registry.get("ccf_parenting")
    """

    def __init__(self) -> None:
        self._profiles: dict[str, PipelineProfile] = {}

    def register(self, profile: PipelineProfile) -> None:
        """註冊 Profile"""
        if profile.name in self._profiles:
            raise ValueError(f"Profile '{profile.name}' already registered")
        self._profiles[profile.name] = profile

    def get(self, name: str) -> PipelineProfile:
        """取得 Profile"""
        if name not in self._profiles:
            available = ", ".join(self._profiles.keys()) or "(none)"
            raise KeyError(
                f"Profile '{name}' not found. Available: {available}"
            )
        return self._profiles[name]

    def list_profiles(self) -> list[str]:
        """列出所有已註冊的 Profile 名稱"""
        return list(self._profiles.keys())
