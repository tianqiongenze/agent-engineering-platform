"""BC4 · Context Engineering(阶段四):压缩 / 预算 / 装配。"""

from __future__ import annotations

from dataclasses import dataclass


def compress_history(messages: list[str], keep_head: int = 1, keep_tail: int = 5) -> list[str]:
    """中段摘要压缩:保留头部(通常是 system/任务目标)与最近 N 条,中段折叠为一条摘要。"""
    if len(messages) <= keep_head + keep_tail + 1:
        return list(messages)
    head = messages[:keep_head]
    middle = messages[keep_head:-keep_tail]
    tail = messages[-keep_tail:]
    summarized = f"[summarized {len(middle)} messages: {middle[0][:24]}…{middle[-1][-24:]}]"
    return [*head, summarized, *tail]


@dataclass
class FitReport:
    original_count: int
    final_count: int
    compression_ratio: float


class ContextWindow:
    """Token 预算装箱:超出预算时从最旧的非头消息开始丢弃(教学近似 1 token≈1 词)。"""

    def __init__(self, budget_tokens: int) -> None:
        if budget_tokens <= 0:
            raise ValueError("budget must be positive")
        self.budget = budget_tokens

    @staticmethod
    def _tokens(message: str) -> int:
        return max(1, len(message.split()))

    def fit(self, messages: list[str]) -> tuple[list[str], FitReport]:
        kept = list(messages)
        while sum(self._tokens(m) for m in kept) > self.budget and len(kept) > 1:
            kept.pop(1)  # 先丢头之后最旧的
        report = FitReport(
            original_count=len(messages),
            final_count=len(kept),
            compression_ratio=len(kept) / max(1, len(messages)),
        )
        return kept, report
