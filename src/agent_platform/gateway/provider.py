"""BC1 · LLM Provider 抽象与 Mock 实现(阶段一)。

Provider 抽象是整个平台的"模型防腐层":上层 BC 永远不直接 import 任何厂商 SDK。
MockProvider 属测试/本地域(生产域 Mock 零残留铁律),由 LLM_PROVIDER 显式切换。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from agent_platform.gateway.domain import ChatRequest, ChatResponse, Usage

_approx_tokens_per_char = 0.25  # 教学近似:真实分词由 Provider 上报


class ProviderError(RuntimeError):
    """Provider 层错误:模型不存在/限流/超时等,可触发路由 fallback。"""


@dataclass
class StreamEvent:
    """流式事件:文本增量,末块携带 Usage(成本留痕数据源)。"""

    delta: str
    usage: Usage | None = None


class LLMProvider(Protocol):
    async def complete(self, req: ChatRequest) -> ChatResponse: ...

    def stream_events(self, req: ChatRequest) -> AsyncIterator[StreamEvent]: ...


@dataclass
class MockProvider:
    """确定性回放:按 prompt 关键词路由预设脚本,保证测试可重复。"""

    scripts: dict[str, str] = field(default_factory=dict)
    known_models: set[str] = field(default_factory=lambda: {"primary", "fast"})
    stream_chunk_size: int = 4
    call_count: int = 0

    def _resolve(self, req: ChatRequest) -> str:
        if req.model not in self.known_models:
            raise ProviderError(f"unknown model: {req.model}")
        prompt = req.messages[-1].content if req.messages else ""
        for keyword, reply in self.scripts.items():
            if keyword in prompt:
                return reply
        return f"mock-reply::{prompt[:64]}"

    async def complete(self, req: ChatRequest) -> ChatResponse:
        self.call_count += 1
        started = time.perf_counter()
        content = self._resolve(req)
        usage = Usage(
            prompt_tokens=max(
                1, round(sum(len(m.content) for m in req.messages) * _approx_tokens_per_char)
            ),
            completion_tokens=max(1, round(len(content) * _approx_tokens_per_char)),
        )
        return ChatResponse(
            model=req.model,
            content=content,
            usage=usage,
            latency_ms=(time.perf_counter() - started) * 1000,
            finish_reason="stop",
        )

    async def _chunks(self, content: str) -> AsyncIterator[str]:
        size = max(1, self.stream_chunk_size)
        for i in range(0, len(content), size):
            yield content[i : i + size]

    async def stream_events(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.call_count += 1
        content = self._resolve(req)
        async for chunk in self._chunks(content):
            yield StreamEvent(delta=chunk)
        yield StreamEvent(
            delta="",
            usage=Usage(
                prompt_tokens=max(
                    1, round(sum(len(m.content) for m in req.messages) * _approx_tokens_per_char)
                ),
                completion_tokens=max(1, round(len(content) * _approx_tokens_per_char)),
            ),
        )

    async def stream(self, req: ChatRequest) -> AsyncIterator[str]:
        """纯文本流(教学用最简形态);生产代码统一走 stream_events。"""
        async for event in self.stream_events(req):
            if event.delta:
                yield event.delta
