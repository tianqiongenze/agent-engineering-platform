"""阶段一(M1)LLM Gateway 单元测试 —— TDD 先行。

对应 spec-phase1.md 验收标准 AC1~AC5。
运行:uv run pytest -m unit
"""

from __future__ import annotations

import pytest

from agent_platform.gateway.domain import ChatMessage, ChatRequest, Usage
from agent_platform.gateway.provider import MockProvider, ProviderError
from agent_platform.gateway.router import AllProvidersFailedError, ModelRouter

pytestmark = pytest.mark.unit


# ── AC1:域模型不变量 ──────────────────────────────────────


class TestDomainModels:
    def test_usage_total_is_derived(self) -> None:
        usage = Usage(prompt_tokens=100, completion_tokens=50)
        assert usage.total_tokens == 150

    def test_usage_rejects_negative_tokens(self) -> None:
        with pytest.raises(ValueError):
            Usage(prompt_tokens=-1, completion_tokens=0)

    def test_chat_message_roles_are_constrained(self) -> None:
        with pytest.raises(ValueError):
            ChatMessage(role="wizard", content="hi")  # type: ignore[arg-format]

    def test_chat_request_defaults(self) -> None:
        req = ChatRequest(
            model="primary",
            messages=[ChatMessage(role="user", content="hello")],
        )
        assert req.temperature == 0.7
        assert req.top_p == 1.0
        assert req.max_tokens == 1024
        assert req.response_schema is None


# ── AC2/AC3:MockProvider 确定性行为 ────────────────────────


def _req(prompt: str, model: str = "primary") -> ChatRequest:
    return ChatRequest(model=model, messages=[ChatMessage(role="user", content=prompt)])


class TestMockProvider:
    async def test_complete_returns_scripted_content(self) -> None:
        provider = MockProvider(scripts={"hello": "world"})
        resp = await provider.complete(_req("hello"))
        assert resp.content == "world"
        assert resp.model == "primary"
        assert resp.latency_ms >= 0
        assert resp.finish_reason == "stop"

    async def test_complete_counts_calls(self) -> None:
        provider = MockProvider(scripts={"a": "1"})
        await provider.complete(_req("a"))
        await provider.complete(_req("a"))
        assert provider.call_count == 2

    async def test_complete_unknown_model_raises(self) -> None:
        provider = MockProvider(scripts={"hello": "world"}, known_models={"primary"})
        with pytest.raises(ProviderError):
            await provider.complete(_req("hello", model="ghost"))

    async def test_stream_chunks_join_to_full_content(self) -> None:
        provider = MockProvider(scripts={"hello": "world"}, stream_chunk_size=2)
        chunks = [c async for c in provider.stream(_req("hello"))]
        assert chunks == ["wo", "rl", "d"]
        assert "".join(chunks) == "world"

    async def test_stream_reports_usage_on_final_chunk(self) -> None:
        """流式结束必须能拿到 Usage(成本留痕的数据源)。"""
        provider = MockProvider(scripts={"hello": "world"})
        events = [e async for e in provider.stream_events(_req("hello"))]
        assert events[-1].usage is not None
        assert events[-1].usage.total_tokens > 0


# ── AC4:ModelRouter fallback ───────────────────────────────


class FlakyProvider(MockProvider):
    """首模型永远失败,演示路由降级。"""

    async def complete(self, req: ChatRequest):  # type: ignore[override]
        if req.model == "primary":
            raise ProviderError("simulated primary outage")
        return await super().complete(req)


class TestModelRouter:
    async def test_falls_back_to_next_model(self) -> None:
        provider = FlakyProvider(scripts={"hello": "from-fast"})
        router = ModelRouter(chain=["primary", "fast"], provider=provider)
        resp = await router.complete(_req("hello"))
        assert resp.content == "from-fast"
        assert len(router.attempts) == 2  # 两次尝试均留痕

    async def test_all_failed_raises_aggregate(self) -> None:
        provider = MockProvider(scripts={}, known_models=set())
        router = ModelRouter(chain=["primary", "fast"], provider=provider)
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await router.complete(_req("hello"))
        assert exc_info.value.attempted == ["primary", "fast"]

    async def test_first_model_success_no_fallback(self) -> None:
        provider = MockProvider(scripts={"hello": "direct"})
        router = ModelRouter(chain=["primary", "fast"], provider=provider)
        resp = await router.complete(_req("hello"))
        assert resp.content == "direct"
        assert len(router.attempts) == 1
