"""BC7 · 成本账本:按模型计价与分摊报表(阶段六)。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


class CostLedger:
    def __init__(self, pricing: dict[str, float]) -> None:
        """pricing: {model: 元/千token}(教学简化:输入输出同价)。"""
        self._pricing = pricing
        self._usage: dict[str, _Usage] = {}

    def record(self, *, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        u = self._usage.setdefault(model, _Usage())
        u.prompt_tokens += prompt_tokens
        u.completion_tokens += completion_tokens

    def report(self) -> dict[str, float | list[str]]:
        out: dict[str, float | list[str]] = {}
        total = 0.0
        unpriced: list[str] = []
        for model, u in self._usage.items():
            tokens_k = (u.prompt_tokens + u.completion_tokens) / 1000
            if model in self._pricing:
                cost = round(tokens_k * self._pricing[model], 6)
                out[model] = cost
                total += cost
            else:
                unpriced.append(model)
        out["_total"] = round(total, 6)
        if unpriced:
            out["_unpriced_models"] = unpriced
        return out
