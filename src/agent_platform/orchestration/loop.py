"""BC3 · Agent Loop / State Machine / Checkpoint(阶段三)。

Decider 抽象 = "LLM 决策"的防腐层:生产由 Gateway 驱动,测试注入确定性脚本。
循环骨架:observe → think(decide) → act(tool/finish) → observe …,含死循环检测与断点续跑。
"""

from __future__ import annotations

import copy
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from agent_platform.tools.runtime import (
    InMemoryAuditBus,
    RiskLevel,
    ToolContext,
    ToolExecutor,
    ToolRegistry,
    tool,
)

DeadLoopThreshold = 3


class AgentState(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    TOOL_FAILED = "tool_failed"
    WAITING_TOOL = "waiting_tool"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LoopFailedError(RuntimeError):
    pass


@dataclass
class Action:
    kind: str  # "tool" | "finish"
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    content: str = ""

    @staticmethod
    def call_tool(name: str, args: dict[str, Any]) -> Action:
        return Action(kind="tool", tool=name, args=args)

    @staticmethod
    def finish(content: str) -> Action:
        return Action(kind="finish", content=content)

    def signature(self) -> str:
        return json.dumps([self.kind, self.tool, self.args], sort_keys=True, ensure_ascii=False)


Decider = Callable[[list[str]], Awaitable[Action]]


@dataclass
class StepRecord:
    tool: str
    args: dict[str, Any]
    output: Any = None
    ok: bool = True
    error: str | None = None


@dataclass
class AgentRun:
    run_id: str
    goal: str
    state: AgentState = AgentState.CREATED
    steps: list[StepRecord] = field(default_factory=list)
    obs_history: list[str] = field(default_factory=list)
    final_output: str = ""
    error: str | None = None


class CheckpointStore:
    """内存 Checkpoint;生产实现换 PG/对象存储(接口不变)。"""

    def __init__(self) -> None:
        self._data: dict[str, AgentRun] = {}

    def save(self, run: AgentRun) -> None:
        self._data[run.run_id] = copy.deepcopy(run)

    def load(self, run_id: str) -> AgentRun:
        return copy.deepcopy(self._data[run_id])


@tool(name="get_weather", description="查询城市天气(只读)", risk=RiskLevel.READ)
async def _get_weather(ctx: ToolContext, city: str) -> str:
    return f"sunny::{city}"


def default_executor() -> ToolExecutor:
    reg = ToolRegistry()
    reg.register(_get_weather.spec, _get_weather.fn)  # type: ignore[attr-defined]
    return ToolExecutor(registry=reg, audit=InMemoryAuditBus())


class AgentLoop:
    def __init__(
        self,
        decider: Decider,
        checkpoint: CheckpointStore,
        max_iterations: int = 8,
        resume_from: str | None = None,
        executor: ToolExecutor | None = None,
    ) -> None:
        self.decider = decider
        self.checkpoint = checkpoint
        self.max_iterations = max_iterations
        self.executor = executor or default_executor()
        self._prior: AgentRun | None = (
            checkpoint.load(resume_from) if resume_from is not None else None
        )

    async def run(self, goal: str) -> AgentRun:
        if self._prior is not None:
            run = AgentRun(
                run_id=self._prior.run_id,
                goal=goal,
                state=AgentState.RUNNING,
                steps=list(self._prior.steps),
                obs_history=list(self._prior.obs_history),
            )
        else:
            run = AgentRun(run_id=uuid4().hex[:12], goal=goal, state=AgentState.RUNNING)

        last_signatures: list[str] = []
        for _ in range(self.max_iterations):
            action = await self.decider(run.obs_history)
            if action.kind == "finish":
                run.state = AgentState.COMPLETED
                run.final_output = action.content
                self.checkpoint.save(run)
                return run

            # 死循环检测:连续 N 个完全相同的动作
            last_signatures.append(action.signature())
            if (
                len(last_signatures) >= DeadLoopThreshold
                and len(set(last_signatures[-DeadLoopThreshold:])) == 1
            ):
                run.state = AgentState.FAILED
                run.error = f"dead loop: repeated identical action x{DeadLoopThreshold}"
                self.checkpoint.save(run)
                raise LoopFailedError(run.error)

            run.state = AgentState.WAITING_TOOL
            ctx = ToolContext(role="agent", run_id=run.run_id)
            result = await self.executor.execute(action.tool, action.args, ctx)
            step = StepRecord(
                tool=action.tool,
                args=action.args,
                output=result.output,
                ok=result.ok,
                error=result.error,
            )
            run.steps.append(step)
            run.obs_history.append(
                f"{action.tool} -> {result.output if result.ok else result.error}"
            )
            if not result.ok:
                run.state = AgentState.TOOL_FAILED
            self.checkpoint.save(run)

        run.state = AgentState.FAILED
        run.error = f"max iterations ({self.max_iterations}) exceeded"
        self.checkpoint.save(run)
        return run
