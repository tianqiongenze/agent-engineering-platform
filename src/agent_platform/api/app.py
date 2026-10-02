"""BC1 · 平台 API:GraphQL BFF + REST/SSE。

- GraphQL:平台统一查询面(健康/模型目录;后续阶段扩展任务/Trace/Eval);
- REST /v1/chat/completions:OpenAI 风格入口(SSE 流式),供教学演示与 CLI 消费。
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import strawberry
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_platform.gateway import (
    ChatMessage,
    ChatRequest,
    MockProvider,
    ModelRouter,
    OpenAICompatibleProvider,
)

_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")


def build_provider():
    """工厂:按环境变量装配 Provider(ADR-002)。

    mock:CI/单测/离线开发;openai_compatible:真实 OpenAI 兼容端点(含本地 vLLM)。
    """
    if _LLM_PROVIDER == "openai_compatible":
        return OpenAICompatibleProvider.from_env()
    if _LLM_PROVIDER != "mock":
        raise ValueError(f"unsupported LLM_PROVIDER: {_LLM_PROVIDER}")
    return MockProvider(scripts={"hello": "world, from Agent Engineering Platform"})


# ── GraphQL Schema ─────────────────────────────────────────


@strawberry.type
class ModelInfo:
    name: str
    role: str


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> str:
        return "ok"

    @strawberry.field
    def models(self) -> list[ModelInfo]:
        chain = os.getenv("LLM_MODEL_CHAIN", "primary,fast").split(",")
        return [
            ModelInfo(name=m.strip(), role="fallback" if i else "primary")
            for i, m in enumerate(chain)
        ]


schema = strawberry.Schema(query=Query)


# ── REST:OpenAI 风格 chat 入口(SSE 流式)───────────────────


class ChatCompletionBody(BaseModel):
    model: str = "primary"
    messages: list[ChatMessage]
    stream: bool = True


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Engineering Platform", version="0.1.0")
    provider = build_provider()
    router = ModelRouter(chain=["primary", "fast"], provider=provider)

    from strawberry.fastapi import GraphQLRouter

    app.include_router(GraphQLRouter(schema), prefix="/graphql")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "llm_provider": _LLM_PROVIDER}

    @app.post("/v1/chat/completions")
    async def chat_completions(body: ChatCompletionBody) -> StreamingResponse:
        req = ChatRequest(model=body.model, messages=body.messages)

        async def sse() -> AsyncIterator[bytes]:
            if body.stream:
                async for event in provider.stream_events(req):
                    payload: dict[str, Any] = {"delta": event.delta, "usage": None}
                    if event.usage:
                        payload = {
                            "delta": "",
                            "usage": event.usage.model_dump(),
                        }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
                yield b"data: [DONE]\n\n"
            else:
                resp = await router.complete(req)
                payload = resp.model_dump()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
                yield b"data: [DONE]\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    return app


app = create_app()
