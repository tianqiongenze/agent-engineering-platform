"""BC7 · Feature Flag:布尔开关 + 一致性哈希百分比灰度(阶段六)。"""

from __future__ import annotations

import hashlib


def _bucket(key: str, user_id: str, buckets: int = 1000) -> int:
    digest = hashlib.sha256(f"{key}:{user_id}".encode()).hexdigest()
    return int(digest[:8], 16) % buckets


class FeatureFlags:
    def __init__(self) -> None:
        self._flags: dict[str, dict] = {}

    def set(self, key: str, *, enabled: bool, rollout_percent: int = 100) -> None:
        if not 0 <= rollout_percent <= 100:
            raise ValueError("rollout_percent must be within [0, 100]")
        self._flags[key] = {"enabled": enabled, "percent": rollout_percent}

    def is_enabled(self, key: str, *, user_id: str) -> bool:
        flag = self._flags.get(key)
        if not flag or not flag["enabled"]:
            return False
        threshold = flag["percent"] * 10  # 1000 桶
        return _bucket(key, user_id) < threshold
