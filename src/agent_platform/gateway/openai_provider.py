"""OpenAICompatibleProvider:任何 OpenAI 兼容端点(云 API / 网关 / 本地 vLLM)。

ADR-002:与 MockProvider 同构 LLMProvider 协议;错误统一收敛为 ProviderError
供 ModelRouter fallback。单测经 httpx.MockTransport 注入,零真实外呼。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from agent_platform.gateway.domain import ChatRequest, ChatResponse, Usage
from agent_platform.gateway.provider import ProviderError, StreamEvent


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        logical_map: dict[str, str] | None = None,
        timeout_s: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        # 路由逻辑名(primary/fast)→ 物理模型映射;P0 修复:req.model 必须影响实际请求
        self.logical_map = logical_map or {}
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_s)
        self._client.headers.update({"Authorization": f"Bearer {api_key}"})
        self.call_count = 0

    @classmethod
    def from_env(cls) -> OpenAICompatibleProvider:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:  # 复审 #9:空密钥 fail-fast(与 JWT fail-fast 对称)
            raise RuntimeError(
                "OPENAI_API_KEY must be set when LLM_PROVIDER=openai_compatible"
            )
        model = os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini")
        fast = os.getenv("LLM_MODEL_FAST", model)
        return cls(
            base_url=base_url, api_key=api_key, model=model,
            logical_map={"primary": model, "fast": fast},
        )

    def resolve_model(self, logical: str) -> str:
        """路由契约:链上逻辑名必须映射到物理模型(P0 修复)。

        复审 #4:未映射的逻辑名显式报错(触发链上 fallback 并留痕),
        禁止静默回落 primary 导致客户端指定模型被偷换。
        """
        from agent_platform.gateway.provider import ProviderError

        if logical not in self.logical_map:
            raise ProviderError(f"unmapped logical model: {logical!r}")
        return self.logical_map[logical]

    def _payload(self, req: ChatRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.resolve_model(req.model),
            "messages": [{"role": m.role, "content": m.content} for m in req.messages],
            "temperature": req.temperature,
            "top_p": req.top_p,
            "max_tokens": req.max_tokens,
        }
        if req.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": req.response_schema},
            }
        if stream:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
        return payload

    @staticmethod
    def _usage(data: dict[str, Any]) -> Usage:
        raw = data.get("usage") or {}
        return Usage(
            prompt_tokens=int(raw.get("prompt_tokens", 0)),
            completion_tokens=int(raw.get("completion_tokens", 0)),
        )

    async def complete(self, req: ChatRequest) -> ChatResponse:
        self.call_count += 1
        started = time.perf_counter()
        try:
            resp = await self._client.post(
                "/chat/completions", json=self._payload(req, stream=False)
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:120]
            raise ProviderError(f"HTTP {exc.response.status_code}: {body}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}") from exc
        try:
            data = resp.json()
            choice = data["choices"][0]
        except Exception as exc:  # P2-10: 畸形 200 统一收敛,fallback 可触发
            raise ProviderError(f"malformed 200 response: {exc}") from exc
        return ChatResponse(
            model=data.get("model", req.model),
            content=choice["message"]["content"],
            usage=self._usage(data),
            latency_ms=(time.perf_counter() - started) * 1000,
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def stream_events(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.call_count += 1
        saw_usage = False
        content_len = 0
        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=self._payload(req, stream=True)
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            break
                        continue
                    try:
                        chunk = json.loads(data)
                    except Exception as exc:  # P2-10
                        raise ProviderError(f"malformed stream frame: {exc}") from exc
                    usage = chunk.get("usage")
                    if usage:
                        saw_usage = True
                        yield StreamEvent(delta="", usage=self._usage(chunk))
                        continue
                    delta = (chunk["choices"][0].get("delta") or {}).get("content") or ""
                    if delta:
                        content_len += len(delta)
                        yield StreamEvent(delta=delta)
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}") from exc
        if not saw_usage:  # 上游未带 usage 时合成,保住成本留痕链路
            yield StreamEvent(delta="", usage=Usage(prompt_tokens=0, completion_tokens=content_len))

    async def stream(self, req: ChatRequest) -> AsyncIterator[str]:
        async for event in self.stream_events(req):
            if event.delta:
                yield event.delta

    async def aclose(self) -> None:
        await self._client.aclose()
