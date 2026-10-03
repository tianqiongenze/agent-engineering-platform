"""API 层共享装配(工具注册表单例等)。"""

from __future__ import annotations

from agent_platform.tools.runtime import (
    InMemoryAuditBus,
    RiskLevel,
    ToolContext,
    ToolExecutor,
    ToolRegistry,
    tool,
)


@tool(name="get_weather", description="查询城市天气(只读示例)", risk=RiskLevel.READ)
async def _weather(ctx: ToolContext, city: str) -> str:
    return f"sunny::{city}"


@tool(
    name="search_code",
    description="在代码库中搜索代码片段",
    risk=RiskLevel.READ,
    mask_args={"api_key"},
)
async def _search_code(ctx: ToolContext, keyword: str) -> str:
    return f"3 hits for {keyword}"


@tool(name="run_test", description="执行测试套件", risk=RiskLevel.WRITE)
async def _run_test(ctx: ToolContext, target: str = "all") -> str:
    return f"tests passed::{target}"


@tool(name="drop_table", description="删除数据表(高危演示)", risk=RiskLevel.DANGEROUS)
async def _drop_table(ctx: ToolContext, table: str) -> str:
    return f"dropped::{table}"


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for fn in (_weather, _search_code, _run_test, _drop_table):
        reg.register(fn.spec, fn.fn)  # type: ignore[attr-defined]
    return reg


def default_executor() -> ToolExecutor:
    return ToolExecutor(registry=default_registry(), audit=InMemoryAuditBus())
