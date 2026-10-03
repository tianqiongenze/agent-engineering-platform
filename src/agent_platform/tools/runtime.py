"""BC2 · Tool Runtime(阶段二):注册中心 + 参数校验 + RBAC + 审计 + 超时恢复。

教学主线为内存实现;Pulsar 审计适配器与 MCP 接入在 spec-phase2 后段接线。
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, ClassVar, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, create_model


class RiskLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


class ToolNotFoundError(KeyError):
    pass


class ValidationFailedError(ValueError):
    pass


class PermissionDeniedError(PermissionError):
    pass


class ToolSpec(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_model: type[BaseModel]
    risk: RiskLevel = RiskLevel.READ
    timeout_s: float = 10.0
    version: str = "1.0.0"
    enabled: bool = True
    mask_args: set[str] = frozenset()  # type: ignore[assignment]


class ToolContext(BaseModel):
    role: str = "agent"  # agent / readonly / admin
    run_id: str = ""
    confirmed: bool = False  # 高危工具的人工确认凭据


class ToolResult(BaseModel):
    ok: bool
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    tool: str = ""


class AuditEvent(BaseModel):
    event_id: str
    run_id: str
    tool: str
    args: dict[str, Any]
    ok: bool
    error: str | None = None
    latency_ms: float = 0.0
    meta: dict[str, str] = {}  # 扩展位(租户/链式哈希等)


class AuditBus(Protocol):
    def publish(self, event: AuditEvent) -> None: ...


class InMemoryAuditBus:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def publish(self, event: AuditEvent) -> None:
        self.events.append(event)


ToolFn = Callable[..., Awaitable[Any]]


def tool(
    *,
    name: str,
    description: str,
    risk: RiskLevel = RiskLevel.READ,
    timeout_s: float = 10.0,
    mask_args: set[str] | None = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Any]:
    """装饰器:从函数签名派生 Pydantic 输入模型并挂载 spec。"""

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Any:
        fields: dict[str, Any] = {}
        for pname, param in inspect.signature(fn).parameters.items():
            if pname == "ctx":
                continue
            if param.default is inspect.Parameter.empty:
                fields[pname] = (param.annotation, ...)
            else:
                fields[pname] = (param.annotation, param.default)
        input_model = create_model(f"{name}_input", **fields)
        spec = ToolSpec(
            name=name,
            description=description,
            input_model=input_model,
            risk=risk,
            timeout_s=timeout_s,
            mask_args=mask_args or frozenset(),  # type: ignore[arg-type]
        )

        async def wrapper(ctx: ToolContext, **kwargs: Any) -> Any:
            return await fn(ctx, **kwargs)

        wrapper.spec = spec  # type: ignore[attr-defined]
        wrapper.fn = wrapper  # type: ignore[attr-defined]
        return wrapper

    return decorator


class ToolRegistry:
    """注册/发现/启停。启停是 Registry 的运行态,不污染共享的 ToolSpec(测试隔离)。"""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, ToolFn]] = {}
        self._disabled: set[str] = set()

    def register(self, spec: ToolSpec, fn: ToolFn) -> None:
        self._tools[spec.name] = (spec, fn)
        self._disabled.discard(spec.name)

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name][0]

    def discover(self, keyword: str) -> list[ToolSpec]:
        hits = []
        for name, (spec, _fn) in self._tools.items():
            if name in self._disabled or not spec.enabled:
                continue
            if keyword in spec.name or keyword in spec.description:
                hits.append(spec)
        return hits

    def disable(self, name: str) -> None:
        self._disabled.add(name)

    def is_enabled(self, name: str) -> bool:
        return name not in self._disabled and self.get(name).enabled

    def all_specs(self) -> list[ToolSpec]:
        """全部工具 spec(管理面用;调用仍走 Executor 权限管线)。"""
        return [spec for spec, _ in self._tools.values()]

    def get_fn(self, name: str) -> ToolFn:
        """受控取执行函数(教学:避免外部直达私有字典)。"""
        return self._tools[name][1]


class ToolExecutor:
    """执行管线:权限 → 参数校验 → 超时执行 → 审计(全链路留痕)。"""

    _ROLE_MAX_RISK: ClassVar[dict[str, set[RiskLevel]]] = {
        "readonly": {RiskLevel.READ},
        "agent": {RiskLevel.READ, RiskLevel.WRITE},
        "admin": {RiskLevel.READ, RiskLevel.WRITE, RiskLevel.DANGEROUS},
    }

    def __init__(self, registry: ToolRegistry, audit: AuditBus) -> None:
        self.registry = registry
        self.audit = audit

    def _check_permission(self, spec: ToolSpec, ctx: ToolContext) -> None:
        # 高危工具:凭人工确认放行(readonly 一律拒);其余按角色风险上限
        if spec.risk is RiskLevel.DANGEROUS:
            if ctx.role == "readonly":
                raise PermissionDeniedError(
                    f"role={ctx.role} cannot invoke dangerous tool {spec.name}"
                )
            if not ctx.confirmed:
                raise PermissionDeniedError(
                    f"tool {spec.name} requires human confirmation before execution"
                )
            return
        allowed = self._ROLE_MAX_RISK.get(ctx.role, {RiskLevel.READ})
        if spec.risk not in allowed:
            raise PermissionDeniedError(
                f"role={ctx.role} cannot invoke risk={spec.risk.value} tool {spec.name}"
            )

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        import time

        started = time.perf_counter()
        spec = self.registry.get(name)
        if not self.registry.is_enabled(name):
            result = ToolResult(ok=False, error="tool disabled", tool=name)
            self._audit(spec, args, ctx, result, started)
            return result
        try:
            self._check_permission(spec, ctx)
            validated = spec.input_model.model_validate(args)
        except PermissionDeniedError as exc:
            result = ToolResult(ok=False, error=str(exc), tool=name)
            self._audit(spec, args, ctx, result, started)
            raise
        except Exception as exc:  # 参数校验失败
            self._audit(
                spec,
                args,
                ctx,
                ToolResult(ok=False, error=f"invalid args: {exc}", tool=name),
                started,
            )
            raise ValidationFailedError(str(exc)) from exc

        fn = self.registry.get_fn(name)
        try:
            output = await asyncio.wait_for(
                fn(ctx, **validated.model_dump()), timeout=spec.timeout_s
            )
            result = ToolResult(
                ok=True, output=output, tool=name, latency_ms=(time.perf_counter() - started) * 1000
            )
        except TimeoutError:
            result = ToolResult(
                ok=False,
                error=f"timeout after {spec.timeout_s}s",
                tool=name,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        self._audit(spec, args, ctx, result, started)
        return result

    def _audit(
        self, spec: ToolSpec, args: dict, ctx: ToolContext, result: ToolResult, started: float
    ) -> None:
        masked = {k: ("***MASKED***" if k in spec.mask_args else v) for k, v in args.items()}
        self.audit.publish(
            AuditEvent(
                event_id=uuid4().hex,
                run_id=ctx.run_id,
                tool=spec.name,
                args=masked,
                ok=result.ok,
                error=result.error,
                latency_ms=result.latency_ms,
            )
        )
