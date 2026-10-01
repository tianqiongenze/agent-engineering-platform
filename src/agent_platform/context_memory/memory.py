"""BC4 · Memory 体系(阶段四):短期 / 长期 / 项目级 + 任务恢复摘要。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class LongTermMemory:
    content: str
    source: str
    confidence: float
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class MemoryStore:
    def __init__(self) -> None:
        self._short: dict[str, str] = {}
        self._long: list[LongTermMemory] = []
        self.project: dict[str, str] = {}  # 项目级记忆:构建命令/技术栈/约定等

    # 短期(当前任务/会话)
    def set_short(self, key: str, value: str) -> None:
        self._short[key] = value

    def get_short(self, key: str) -> str | None:
        return self._short.get(key)

    # 长期(跨任务检索)
    def add_long(self, content: str, source: str, confidence: float = 0.8) -> None:
        self._long.append(LongTermMemory(content=content, source=source, confidence=confidence))

    def search_long(self, keyword: str) -> list[LongTermMemory]:
        return [m for m in self._long if keyword.lower() in m.content.lower()]

    # 项目级(技术栈/构建命令/约定,随仓库持久化)
    def set_project(self, key: str, value: str) -> None:
        self.project[key] = value

    # 任务恢复摘要(Context 被截断后继续执行的锚点)
    def task_summary(self) -> str:
        lines = [f"{k}: {v}" for k, v in self._short.items()]
        return "任务状态摘要\n" + "\n".join(lines) if lines else "任务状态摘要(空)"
