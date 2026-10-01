"""阶段二(M2)Tool Runtime 单元测试 —— 工具注册/校验/权限/审计/超时。

对应大纲第 2 章;spec 验收 AC:注册与发现、Schema 拦截、RBAC、
高危人工确认、审计事件、超时失败恢复。
"""

from __future__ import annotations

import asyncio

import pytest

from agent_platform.tools.runtime import (
    InMemoryAuditBus,
    PermissionDeniedError,
    RiskLevel,
    ToolContext,
    ToolExecutor,
    ToolRegistry,
    ToolResult,
    ValidationFailedError,
    tool,
)

pytestmark = pytest.mark.unit


# ── 内置示例工具(教学与测试共用)──────────────────────────


@tool(
    name="get_weather",
    description="查询城市天气(只读)",
    risk=RiskLevel.READ,
)
async def get_weather(ctx: ToolContext, city: str) -> str:
    return f"sunny::{city}"


@tool(
    name="drop_database",
    description="删除数据库(高危演示)",
    risk=RiskLevel.DANGEROUS,
)
async def drop_database(ctx: ToolContext, table: str) -> str:
    return f"dropped::{table}"


class TestRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        reg.register(get_weather.spec, get_weather.fn)
        assert reg.get("get_weather").name == "get_weather"

    def test_discover_by_keyword(self) -> None:
        reg = ToolRegistry()
        reg.register(get_weather.spec, get_weather.fn)
        reg.register(drop_database.spec, drop_database.fn)
        found = reg.discover("天气")
        assert [s.name for s in found] == ["get_weather"]

    def test_disable_hides_tool(self) -> None:
        reg = ToolRegistry()
        reg.register(drop_database.spec, drop_database.fn)
        reg.disable("drop_database")
        assert reg.is_enabled("drop_database") is False
        assert reg.discover("删除") == []


class TestExecutorValidation:
    async def test_happy_path_returns_result_and_audits(self) -> None:
        reg = ToolRegistry()
        reg.register(get_weather.spec, get_weather.fn)
        bus = InMemoryAuditBus()
        executor = ToolExecutor(registry=reg, audit=bus)
        result = await executor.execute(
            "get_weather", {"city": "Beijing"}, ToolContext(role="agent", run_id="r1")
        )
        assert isinstance(result, ToolResult)
        assert result.ok and result.output == "sunny::Beijing"
        events = bus.events
        assert len(events) == 1
        assert events[0].tool == "get_weather" and events[0].ok

    async def test_invalid_args_blocked_by_schema(self) -> None:
        reg = ToolRegistry()
        reg.register(get_weather.spec, get_weather.fn)
        executor = ToolExecutor(registry=reg, audit=InMemoryAuditBus())
        with pytest.raises(ValidationFailedError):
            await executor.execute(
                "get_weather", {"city": 123}, ToolContext(role="agent", run_id="r1")
            )

    async def test_timeout_recovers_as_failure(self) -> None:
        @tool(name="slow_tool", description="慢工具", risk=RiskLevel.READ, timeout_s=0.05)
        async def slow(ctx: ToolContext) -> str:
            await asyncio.sleep(1)
            return "never"

        reg = ToolRegistry()
        reg.register(slow.spec, slow.fn)
        bus = InMemoryAuditBus()
        executor = ToolExecutor(registry=reg, audit=bus)
        result = await executor.execute("slow_tool", {}, ToolContext(role="agent", run_id="r2"))
        assert not result.ok
        assert "timeout" in result.error
        assert bus.events[0].ok is False


class TestPermission:
    async def test_readonly_role_cannot_write(self) -> None:
        reg = ToolRegistry()
        reg.register(drop_database.spec, drop_database.fn)
        executor = ToolExecutor(registry=reg, audit=InMemoryAuditBus())
        with pytest.raises(PermissionDeniedError):
            await executor.execute(
                "drop_database", {"table": "t"}, ToolContext(role="readonly", run_id="r3")
            )

    async def test_dangerous_tool_requires_confirmation(self) -> None:
        reg = ToolRegistry()
        reg.register(drop_database.spec, drop_database.fn)
        executor = ToolExecutor(registry=reg, audit=InMemoryAuditBus())
        with pytest.raises(PermissionDeniedError, match="confirmation"):
            await executor.execute(
                "drop_database", {"table": "t"}, ToolContext(role="agent", run_id="r4")
            )

    async def test_dangerous_tool_passes_with_confirmation(self) -> None:
        reg = ToolRegistry()
        reg.register(drop_database.spec, drop_database.fn)
        executor = ToolExecutor(registry=reg, audit=InMemoryAuditBus())
        result = await executor.execute(
            "drop_database",
            {"table": "t"},
            ToolContext(role="agent", run_id="r5", confirmed=True),
        )
        assert result.ok


class TestAudit:
    async def test_audit_event_masks_sensitive_args(self) -> None:
        @tool(name="query_user", description="查用户", risk=RiskLevel.READ, mask_args={"api_key"})
        async def query_user(ctx: ToolContext, api_key: str, q: str) -> str:
            return "u1"

        reg = ToolRegistry()
        reg.register(query_user.spec, query_user.fn)
        bus = InMemoryAuditBus()
        executor = ToolExecutor(registry=reg, audit=bus)
        await executor.execute(
            "query_user",
            {"api_key": "sk-secret", "q": "joel"},
            ToolContext(role="agent", run_id="r6"),
        )
        assert bus.events[0].args["api_key"] == "***MASKED***"
        assert bus.events[0].args["q"] == "joel"
