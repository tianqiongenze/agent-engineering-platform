"""BC1 · 平台 API:GraphQL BFF + REST/SSE + 前端控制台 + Prometheus。

- GraphQL:平台统一查询面(健康/模型目录/工具目录);
- REST /v1/chat/completions:OpenAI 风格入口(SSE 流式);
- 风控栈:JWT/租户 → 注入 → 重放 → 限流(顺序不可变);
- /metrics:Prometheus(OSW 铁律:代码注册+路由+真实数据三步闭环);
- /:Web 控制台 MVP(设计 Tokens 暗色主题,PWA 可安装)。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import strawberry
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from agent_platform.gateway import (
    ChatMessage,
    ChatRequest,
    MockProvider,
    ModelRouter,
    OpenAICompatibleProvider,
)
from agent_platform.observability import metrics as M
from agent_platform.security import (
    AuthError,
    InjectionDetected,
    JwtCodec,
    Principal,
    RateLimitExceeded,
    ReplayDetected,
    SecurityStack,
)

_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
_STATIC_DIR = Path(__file__).resolve().parent / "static"


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
class ToolInfo:
    name: str
    description: str
    risk: str
    enabled: bool


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

    @strawberry.field
    def tools(self) -> list[ToolInfo]:
        from agent_platform.api.deps import default_registry

        reg = default_registry()
        return [
            ToolInfo(
                name=s.name,
                description=s.description,
                risk=s.risk.value,
                enabled=reg.is_enabled(s.name),
            )
            for s in reg.all_specs()
        ]


schema = strawberry.Schema(query=Query)


# ── REST:OpenAI 风格 chat 入口(SSE 流式)───────────────────


class ChatCompletionBody(BaseModel):
    model: str = "primary"
    messages: list[ChatMessage]
    stream: bool = True


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Engineering Platform", version="0.3.0")
    limiter = SecurityStack.limiter_factory(
        capacity=int(os.getenv("SEC_RATE_CAPACITY", "10")),
        refill_per_s=float(os.getenv("SEC_RATE_REFILL", "2")),
    )
    security = SecurityStack(limiter=limiter)
    jwt_codec = JwtCodec(os.getenv("SEC_JWT_SECRET", "dev-secret-change-me"))
    jwt_required = os.getenv("SEC_JWT_REQUIRED", "0") == "1"
    provider = build_provider()
    router = ModelRouter(chain=["primary", "fast"], provider=provider)

    from strawberry.fastapi import GraphQLRouter

    app.include_router(GraphQLRouter(schema), prefix="/graphql")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "llm_provider": _LLM_PROVIDER}

    @app.get("/metrics")
    async def metrics(request: Request) -> Response:
        # OSW:受保护指标端点(业界共识;/metrics 泄露运维细节)
        if os.getenv("METRICS_PROTECTED", "0") == "1":
            try:
                authenticate_or_401(request, jwt_codec)
            except AuthError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
        body, ctype = M.render_metrics()
        return Response(content=body, media_type=ctype)

    def authenticate_or_401(request: Request, codec: JwtCodec) -> Principal:
        from agent_platform.security.auth import authenticate

        return authenticate(request.headers.get("authorization"), codec, required=jwt_required)

    @app.get("/v1/tools")
    async def list_tools() -> list[dict[str, str]]:
        from agent_platform.api.deps import default_registry

        reg = default_registry()
        return [
            {
                "name": s.name,
                "description": s.description,
                "risk": s.risk.value,
                "enabled": str(reg.is_enabled(s.name)).lower(),
            }
            for s in reg.discover("")
        ]

    @app.post("/v1/chat/completions")
    async def chat_completions(body: ChatCompletionBody, request: Request) -> StreamingResponse:
        # ① JWT/租户(可配置强制;开发态降级)
        try:
            principal = authenticate_or_401(request, jwt_codec)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        client_key = f"{principal.tenant_id}:{request.client.host if request.client else 'anon'}"
        idem = request.headers.get("x-idempotency-key", "")
        prompt_text = "\n".join(m.content for m in body.messages)
        # ②③④ 注入→重放→限流
        try:
            security.check_request(client_key=client_key, text=prompt_text, idempotency_key=idem)
        except (RateLimitExceeded, ReplayDetected) as exc:
            M.track_security_block(type(exc).__name__)
            M.track_rate_limit_rejected()
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except InjectionDetected as exc:
            M.track_security_block("injection")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        req = ChatRequest(model=body.model, messages=body.messages)
        M.track_llm(_LLM_PROVIDER, "started")

        async def sse() -> AsyncIterator[bytes]:
            started = time.perf_counter()
            if body.stream:
                async for event in provider.stream_events(req):
                    payload: dict[str, Any] = {"delta": event.delta, "usage": None}
                    if event.usage:
                        payload = {"delta": "", "usage": event.usage.model_dump()}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
                yield b"data: [DONE]\n\n"
            else:
                resp = await router.complete(req)
                payload = resp.model_dump()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
                yield b"data: [DONE]\n\n"
            M.track_llm(_LLM_PROVIDER, "ok", time.perf_counter() - started)

        return StreamingResponse(sse(), media_type="text/event-stream")

    # ── Web 控制台(PWA 可安装,设计 Tokens 暗色主题)─────────
    if _STATIC_DIR.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="console")

    return app


app = create_app()
