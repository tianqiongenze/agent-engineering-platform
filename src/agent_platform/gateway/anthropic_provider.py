"""AnthropicMessagesProvider:anthropic-messages 协议适配(与 OpenAICompatibleProvider 同构)。

复用 LLMProvider 协议 → ModelRouter 可混排两种协议的供应商。
错误统一收敛 ProviderError;单测经 httpx.MockTransport,零真实外呼。
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

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicMessagesProvider:
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
        # P0 修复:req.model(路由链)必须映射到物理模型
        self.logical_map = logical_map or {}
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_s)
        # 认证头幂等合并:注入的 client 也必须带凭据(MockTransport 注入同样受益)
        self._client.headers.update(
            {
                "x-api-key": api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            }
        )
        self.call_count = 0

    @classmethod
    def from_provider_rule(cls, rule: dict[str, Any]) -> AnthropicMessagesProvider:
        """从 ZCode provider_config.json 的 providerRule 直接装配。"""
        cfg = rule["config"]
        order = cfg.get("modelOrder") or []
        model = order[0] if order else "glm-5.3"
        logical = {"primary": model}
        if len(order) > 1:
            logical["fast"] = order[1]
        return cls(
            base_url=cfg["api"]["baseUrl"],
            api_key=cfg["access"]["apiKey"],
            model=model,
            logical_map=logical,
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

    def _payload(self, req: ChatRequest) -> dict[str, Any]:
        system_parts = [m.content for m in req.messages if m.role == "system"]
        messages = [
            {"role": m.role, "content": m.content} for m in req.messages if m.role != "system"
        ]
        payload: dict[str, Any] = {
            "model": self.resolve_model(req.model),
            "max_tokens": req.max_tokens,
            "messages": messages,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        payload["temperature"] = req.temperature  # 显式透传,便于联调观察
        return payload

    async def complete(self, req: ChatRequest) -> ChatResponse:
        self.call_count += 1
        started = time.perf_counter()
        try:
            resp = await self._client.post("/v1/messages", json=self._payload(req))
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:120]
            raise ProviderError(f"HTTP {exc.response.status_code}: {body}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}") from exc
        try:
            data = resp.json()
        except Exception as exc:  # P2-10: 畸形 200 统一收敛
            raise ProviderError(f"malformed 200 response: {exc}") from exc
        text = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        return ChatResponse(
            model=data.get("model", req.model),
            content=text,
            usage=Usage(
                prompt_tokens=int(usage.get("input_tokens", 0)),
                completion_tokens=int(usage.get("output_tokens", 0)),
            ),
            latency_ms=(time.perf_counter() - started) * 1000,
            finish_reason=data.get("stop_reason", "stop"),
        )

    async def stream_events(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.call_count += 1
        payload = self._payload(req) | {"stream": True}
        saw_usage = False
        content_len = 0
        try:
            async with self._client.stream("POST", "/v1/messages", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if not data:
                        continue
                    try:
                        chunk = json.loads(data)
                    except Exception as exc:  # P2-10
                        raise ProviderError(f"malformed stream frame: {exc}") from exc
                    ctype = chunk.get("type")
                    if ctype == "content_block_delta":
                        delta = (chunk.get("delta") or {}).get("text") or ""
                        if delta:
                            content_len += len(delta)
                            yield StreamEvent(delta=delta)
                    elif ctype == "message_delta":
                        usage = chunk.get("usage") or {}
                        if usage:
                            saw_usage = True
                            yield StreamEvent(
                                delta="",
                                usage=Usage(
                                    prompt_tokens=int(usage.get("input_tokens", 0)),
                                    completion_tokens=int(usage.get("output_tokens", 0)),
                                ),
                            )
                    elif ctype == "message_stop":
                        break
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc}") from exc
        if not saw_usage:
            yield StreamEvent(delta="", usage=Usage(prompt_tokens=0, completion_tokens=content_len))

    async def stream(self, req: ChatRequest) -> AsyncIterator[str]:
        async for event in self.stream_events(req):
            if event.delta:
                yield event.delta

    async def aclose(self) -> None:
        await self._client.aclose()


def load_provider_rule(name: str, config_path: str | None = None) -> dict[str, Any]:
    """从本地 ZCode 配置读取指定 providerRule(联调用,密钥不落日志)。"""
    from pathlib import Path

    path = Path(config_path or os.path.expanduser("~/.zcode/v2/provider_config.json"))
    data = json.loads(path.read_text())
    rules = data.get("config", {}).get("providerConfigRules", {}).get("providerRules", [])
    for rule in rules:
        if rule.get("providerName") == name:
            return rule
    raise ProviderError(f"provider rule not found: {name}")
