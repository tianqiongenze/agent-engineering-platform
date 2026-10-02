"""OpenAICompatibleProvider 单元测试(TDD 先行)—— httpx.MockTransport 注入,零真实外呼。"""

from __future__ import annotations

import json

import httpx
import pytest

from agent_platform.gateway.domain import ChatMessage, ChatRequest
from agent_platform.gateway.openai_provider import OpenAICompatibleProvider
from agent_platform.gateway.provider import ProviderError

pytestmark = pytest.mark.unit


def make_provider(handler) -> OpenAICompatibleProvider:
    client = httpx.AsyncClient(
        base_url="http://test/v1",
        transport=httpx.MockTransport(handler),
    )
    return OpenAICompatibleProvider(
        base_url="http://test/v1", api_key="k", model="gpt-x", client=client
    )


def _req(prompt: str = "hi", model: str = "gpt-x") -> ChatRequest:
    return ChatRequest(model=model, messages=[ChatMessage(role="user", content=prompt)])


class TestComplete:
    async def test_parses_choices_and_usage(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "gpt-x"
            assert body["messages"][0]["content"] == "hi"
            return httpx.Response(
                200,
                json={
                    "model": "gpt-x",
                    "choices": [{"message": {"content": "hello!"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                },
            )

        resp = await make_provider(handler).complete(_req())
        assert resp.content == "hello!"
        assert resp.usage.prompt_tokens == 10
        assert resp.usage.total_tokens == 14
        assert resp.finish_reason == "stop"

    async def test_schema_forwarded_as_response_format(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )

        req = ChatRequest(
            model="gpt-x",
            messages=[ChatMessage(role="user", content="q")],
            response_schema={"type": "object"},
        )
        await make_provider(handler).complete(req)
        assert captured["response_format"]["json_schema"]["schema"] == {"type": "object"}


class TestStream:
    async def test_sse_frames_and_final_usage(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["stream"] is True
            frames = [
                {"choices": [{"delta": {"content": "he"}}]},
                {"choices": [{"delta": {"content": "llo"}}]},
                {"choices": [{"delta": {}}]},
                {"usage": {"prompt_tokens": 6, "completion_tokens": 3}},
            ]
            payload = "".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n"
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=payload.encode()
            )

        events = [e async for e in make_provider(handler).stream_events(_req())]
        deltas = "".join(e.delta for e in events)
        assert deltas == "hello"
        assert events[-1].usage is not None
        assert events[-1].usage.total_tokens == 9

    async def test_stream_synthesizes_usage_when_absent(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            frames = [{"choices": [{"delta": {"content": "abc"}}]}, {"choices": [{"delta": {}}]}]
            payload = "".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n"
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=payload.encode()
            )

        events = [e async for e in make_provider(handler).stream_events(_req("abcd"))]
        assert events[-1].usage is not None
        assert events[-1].usage.completion_tokens > 0


class TestErrors:
    @pytest.mark.parametrize("status", [429, 500])
    async def test_http_error_raises_provider_error(self, status: int) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json={"error": {"message": "overloaded"}})

        with pytest.raises(ProviderError, match=str(status)):
            await make_provider(handler).complete(_req())

    async def test_network_error_raises_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        with pytest.raises(ProviderError, match="network"):
            await make_provider(handler).complete(_req())


class TestConfig:
    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL_PRIMARY", "gpt-x")
        p = OpenAICompatibleProvider.from_env()
        assert p.model == "gpt-x"
        assert str(p._client.base_url).rstrip("/") == "https://api.example.com/v1"
        assert p._client.headers["Authorization"] == "Bearer sk-test"
