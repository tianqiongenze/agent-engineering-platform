"""AC6 真实联调(集成 profile):本地 ZCode 配置的真实供应商。

- TestAnthropicGLM53Live:APIS-glm-5.3(anthropic-messages,api.kjdfhl.school,glm-5.3)
- TestOpenAIGLM53Live:OpenAICompatibleProvider · nvidia · z-ai/glm-5.3-flash(AC6 原生验证)

运行:uv run pytest -m integration -v
证据:docs/specs/ac6-live-verification.md(自动生成,密钥全程掩码不落盘)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from agent_platform.gateway.anthropic_provider import (
    AnthropicMessagesProvider,
    load_provider_rule,
)
from agent_platform.gateway.domain import ChatMessage, ChatRequest
from agent_platform.gateway.openai_provider import OpenAICompatibleProvider

pytestmark = pytest.mark.integration

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "specs" / "ac6-live-verification.md"
_RECORDS: list[str] = []


def _record(line: str) -> None:
    print(line)
    _RECORDS.append(line)


@pytest.fixture(autouse=True)
def _dump_evidence(request: pytest.FixtureRequest) -> Any:
    yield
    if _RECORDS:
        rows = "\n".join(f"| {_RECORDS[i]} |" for i in range(len(_RECORDS)))
        EVIDENCE.write_text(
            "# AC6 真实联调证据(自动生成 · 密钥全程掩码)\n\n| 记录 |\n|---|\n" + rows + "\n"
        )


def _make_anthropic() -> AnthropicMessagesProvider:
    return AnthropicMessagesProvider.from_provider_rule(load_provider_rule("APIS-glm-5.3"))


def _make_openai_nvidia() -> OpenAICompatibleProvider:
    cfg = load_provider_rule("nvidia")["config"]
    return OpenAICompatibleProvider(
        base_url=cfg["api"]["baseUrl"],
        api_key=cfg["access"]["apiKey"],
        model="z-ai/glm-5.3-flash",
    )


def _req(prompt: str) -> ChatRequest:
    return ChatRequest(
        model="live",
        messages=[ChatMessage(role="user", content=prompt)],
        max_tokens=256,
    )


class TestAnthropicGLM53Live:
    """APIS-glm-5.3 · anthropic-messages 协议 · 模型 glm-5.3。"""

    async def test_complete_live(self) -> None:
        provider = _make_anthropic()
        started = time.perf_counter()
        resp = await provider.complete(_req("用一句话介绍什么是 AI Agent。"))
        elapsed = (time.perf_counter() - started) * 1000
        _record(
            f"APIS-glm-5.3 complete | {elapsed:.0f}ms | "
            f"tokens={resp.usage.total_tokens} | chars={len(resp.content)}"
        )
        assert resp.content.strip(), "真实响应不应为空"
        assert resp.usage.total_tokens > 0
        await provider.aclose()

    async def test_stream_live(self) -> None:
        provider = _make_anthropic()
        chunks: list[str] = []
        usage_tokens = 0
        started = time.perf_counter()
        async for event in provider.stream_events(_req("从 1 数到 5,用顿号分隔。")):
            if event.delta:
                chunks.append(event.delta)
            if event.usage:
                usage_tokens = event.usage.total_tokens
        elapsed = (time.perf_counter() - started) * 1000
        _record(
            f"APIS-glm-5.3 stream | {elapsed:.0f}ms | chunks={len(chunks)} | tokens={usage_tokens}"
        )
        assert len(chunks) >= 2, "流式应产出多帧"
        await provider.aclose()


class TestOpenAIGLM53Live:
    """AC6 原生验证:OpenAICompatibleProvider · nvidia · z-ai/glm-5.3-flash。"""

    async def test_complete_live(self) -> None:
        provider = _make_openai_nvidia()
        started = time.perf_counter()
        resp = await provider.complete(_req("Say 'OK' and nothing else."))
        elapsed = (time.perf_counter() - started) * 1000
        _record(
            f"nvidia/glm-5.3-flash complete | {elapsed:.0f}ms | "
            f"tokens={resp.usage.total_tokens} | chars={len(resp.content)}"
        )
        assert resp.content.strip()
        await provider.aclose()
