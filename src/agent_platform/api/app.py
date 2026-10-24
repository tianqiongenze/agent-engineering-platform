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


async def _stream_with_fallback(provider, router, req):
    """流式 fallback:主链逐模型尝试(P1-4);与 router.complete 同降级语义。"""
    from agent_platform.gateway.provider import ProviderError

    last_exc: Exception | None = None
    for model in router.chain:
        try:
            async for event in provider.stream_events(req.model_copy(update={"model": model})):
                yield event
            return
        except ProviderError as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
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
    # P1-3: 生产/强鉴权下默认密钥必须 fail-fast(SCS 铁律:禁伪密钥)
    jwt_secret = os.getenv("SEC_JWT_SECRET", "")
    jwt_required = os.getenv("SEC_JWT_REQUIRED", "0") == "1"
    if not jwt_secret:
        if jwt_required or _LLM_PROVIDER != "mock":
            raise RuntimeError(
                "SEC_JWT_SECRET must be set when SEC_JWT_REQUIRED=1 or real provider is on "
                "(refusing to run with a forgeable default secret)"
            )
        jwt_secret = "dev-secret-change-me"  # noqa: S105 - 仅 dev(mock+匿名)路径可达
    jwt_codec = JwtCodec(jwt_secret)
    provider = build_provider()
    # P2-17: 进程优雅关停(GSD 铁律)
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _lifespan(_app):
        yield
        if hasattr(provider, "aclose"):
            await provider.aclose()

    app.router.lifespan_context = _lifespan
    # P0-1c: 路由链与 GraphQL models 查询同源(单一事实源)
    chain = [
        m.strip()
        for m in os.getenv("LLM_MODEL_CHAIN", "primary,fast").split(",")
        if m.strip()
    ]

    from strawberry.fastapi import GraphQLRouter

    app.include_router(GraphQLRouter(schema), prefix="/graphql")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "llm_provider": _LLM_PROVIDER}

    @app.get("/metrics")
    async def metrics(request: Request) -> Response:
        # OSW:受保护指标端点;P1-2 修复:保护开启即强制持证,不随全局开关旁路
        if os.getenv("METRICS_PROTECTED", "0") == "1":
            try:
                authenticate_or_401(request, jwt_codec, required=True)
            except AuthError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
        body, ctype = M.render_metrics()
        return Response(content=body, media_type=ctype)

    def authenticate_or_401(
        request: Request, codec: JwtCodec, required: bool | None = None
    ) -> Principal:
        from agent_platform.security.auth import authenticate

        return authenticate(
            request.headers.get("authorization"), codec,
            required=jwt_required if required is None else required,
        )

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
            try:
                if body.stream:
                    # P1-4: 流式与路由降级同语义;末帧 usage 保证成本留痕
                    events = _stream_with_fallback(provider, chain, req)
                    async for event in events:
                        payload: dict[str, Any] = {"delta": event.delta, "usage": None}
                        if event.usage:
                            payload = {"delta": "", "usage": event.usage.model_dump()}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
                    yield b"data: [DONE]\n\n"
                else:
                    resp = await ModelRouter(chain=chain, provider=provider).complete(req)
                    payload = resp.model_dump()
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
                    yield b"data: [DONE]\n\n"
                M.track_llm(_LLM_PROVIDER, "ok", time.perf_counter() - started)
            except Exception as exc:
                # P2-11: 指标闭合——错误必须计入 result="error" 并向客户端发结构化错误帧
                M.track_llm(_LLM_PROVIDER, "error", time.perf_counter() - started)
                err = {"error": str(exc)[:200]}
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode()
                yield b"data: [DONE]\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    # ── Web 控制台(PWA 可安装,设计 Tokens 暗色主题)─────────
    if _STATIC_DIR.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="console")

    return app


app = create_app()
