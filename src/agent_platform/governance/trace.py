"""BC7 · Trace 与 Replay(阶段六)。

Span 树 → TraceRecord;Replay 保存"输入+输出",回放=用同一输入真实重执行并比对。
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


def _short_id() -> str:
    return uuid4().hex[:10]


@dataclass
class Span:
    span_id: str
    name: str
    parent_id: str | None
    started_at: float
    ended_at: float | None = None
    ok: bool = True
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def set_meta(self, **kw: Any) -> None:
        self.meta.update(kw)

    def set_ok(self, ok: bool, error: str | None = None) -> None:
        self.ok = ok
        self.error = error

    @property
    def duration_ms(self) -> float:
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at) * 1000


@dataclass
class TraceRecord:
    trace_id: str
    spans: list[Span]

    @property
    def healthy(self) -> bool:
        return all(s.ok for s in self.spans)


class _SpanCtx:
    def __init__(self, collector: TraceCollector, span: Span) -> None:
        self._collector = collector
        self.span = span

    @property
    def span_id(self) -> str:
        return self.span.span_id

    def set_meta(self, **kw: Any) -> None:
        self.span.set_meta(**kw)

    def set_ok(self, ok: bool, error: str | None = None) -> None:
        self.span.set_ok(ok, error)

    def __enter__(self) -> _SpanCtx:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.span.ended_at = time.perf_counter()
        if exc is not None:
            self.span.set_ok(False, error=str(exc))
        # 返回 None(等价 False):不吞异常


class TraceCollector:
    def __init__(self) -> None:
        self._spans: list[Span] = []

    def span(self, name: str, parent: str | None = None) -> _SpanCtx:
        s = Span(span_id=_short_id(), name=name, parent_id=parent, started_at=time.perf_counter())
        self._spans.append(s)
        return _SpanCtx(self, s)

    def build(self) -> TraceRecord:
        return TraceRecord(trace_id=_short_id(), spans=list(self._spans))


@dataclass
class ReplayRecording:
    prompt: str
    output: str


class ReplayStore:
    def __init__(self) -> None:
        self._recordings: list[ReplayRecording] = []

    def record(self, prompt: str, output: str) -> None:
        self._recordings.append(ReplayRecording(prompt=prompt, output=output))

    def recordings(self) -> list[ReplayRecording]:
        return list(self._recordings)

    async def replay(self, prompt: str, fn: Callable[[str], Awaitable[str]]) -> str:
        """回放即真实重执行:失败任务修复后,用同一输入验证行为是否变化。"""
        return await fn(prompt)
