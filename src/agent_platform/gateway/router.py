"""BC1 · 模型路由:按优先级 fallback,并保留每次尝试的留痕(Trace 数据源)。"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_platform.gateway.domain import ChatRequest, ChatResponse
from agent_platform.gateway.provider import LLMProvider, ProviderError


class AllProvidersFailedError(RuntimeError):
    def __init__(self, attempted: list[str]) -> None:
        self.attempted = attempted
        super().__init__(f"all models failed, attempted={attempted}")


@dataclass
class AttemptRecord:
    model: str
    ok: bool
    error: str | None = None


@dataclass
class ModelRouter:
    chain: list[str]
    provider: LLMProvider
    attempts: list[AttemptRecord] = field(default_factory=list)

    async def complete(self, req: ChatRequest) -> ChatResponse:
        self.attempts.clear()
        errors: list[str] = []
        for model in self.chain:
            routed = req.model_copy(update={"model": model})
            try:
                resp = await self.provider.complete(routed)
            except ProviderError as exc:
                self.attempts.append(AttemptRecord(model=model, ok=False, error=str(exc)))
                errors.append(f"{model}: {exc}")
                continue
            self.attempts.append(AttemptRecord(model=model, ok=True))
            return resp
        raise AllProvidersFailedError([a.model for a in self.attempts])
