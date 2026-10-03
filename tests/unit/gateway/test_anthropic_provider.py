"""AnthropicMessagesProvider 单元测试(MockTransport,零外呼)。"""

from __future__ import annotations

import json

import httpx
import pytest

from agent_platform.gateway.anthropic_provider import AnthropicMessagesProvider
from agent_platform.gateway.domain import ChatMessage, ChatRequest
from agent_platform.gateway.provider import ProviderError

pytestmark = pytest.mark.unit


def make_provider(handler) -> AnthropicMessagesProvider:
    client = httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))
    return AnthropicMessagesProvider(
        base_url="http://test", api_key="k", model="glm-5.3", client=client
    )


def _req(prompt: str = "hi") -> ChatRequest:
    return ChatRequest(model="glm-5.3", messages=[ChatMessage(role="user", content=prompt)])


class TestComplete:
    async def test_parses_content_blocks_and_usage(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "glm-5.3"
            assert body["max_tokens"] == 1024
            assert request.headers["x-api-key"] == "k"
            return httpx.Response(
                200,
                json={
                    "model": "glm-5.3",
                    "content": [{"type": "text", "text": "你好"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 8, "output_tokens": 3},
                },
            )

        resp = await make_provider(handler).complete(_req())
        assert resp.content == "你好"
        assert resp.usage.total_tokens == 11
        assert resp.finish_reason == "end_turn"

    async def test_system_role_mapped_to_system_field(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {},
                },
            )

        req = ChatRequest(
            model="glm-5.3",
            messages=[
                ChatMessage(role="system", content="你是测试助手"),
                ChatMessage(role="user", content="hi"),
            ],
        )
        await make_provider(handler).complete(req)
        assert captured["system"] == "你是测试助手"
        assert all(m["role"] != "system" for m in captured["messages"])


class TestStream:
    async def test_sse_deltas_and_usage(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert json.loads(request.content)["stream"] is True
            frames = [
                {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "he"}},
                {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "llo"}},
                {"type": "message_delta", "usage": {"input_tokens": 5, "output_tokens": 2}},
                {"type": "message_stop"},
            ]
            payload = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=payload.encode()
            )

        events = [e async for e in make_provider(handler).stream_events(_req())]
        assert "".join(e.delta for e in events) == "hello"
        assert events[-1].usage is not None and events[-1].usage.total_tokens == 7


class TestErrors:
    async def test_http_error_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limited"})

        with pytest.raises(ProviderError, match="429"):
            await make_provider(handler).complete(_req())

    async def test_network_error_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        with pytest.raises(ProviderError, match="network"):
            await make_provider(handler).complete(_req())
