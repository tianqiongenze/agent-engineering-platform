"""Capstone B · 新一代软件工厂 MVP。

角色流水线:PM(拆任务)→ 架构师(选技能)→ 开发(AgentLoop 产出变更)→ QA(Eval 验收)。
GitHub Channel / ACP 集成点在 README,教学本地以模拟器替身。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from agent_platform.eval.evaluator import AgentAnswer, EvalRunner, GoldenCase, KeywordJudge
from agent_platform.multi_agent.skill import SkillDef, SkillRegistry
from agent_platform.multi_agent.supervisor import SubagentTask
from agent_platform.orchestration.loop import (
    Action,
    AgentLoop,
    CheckpointStore,
    Decider,
)
from agent_platform.tools.runtime import (
    InMemoryAuditBus,
    RiskLevel,
    ToolContext,
    ToolExecutor,
    ToolRegistry,
    tool,
)


@dataclass
class PipelineStep:
    name: str
    owner_role: str
    outputs: list[str] = field(default_factory=list)
    done: bool = False


@tool(name="scaffold_module", description="按模块名生成代码骨架(演示)", risk=RiskLevel.WRITE)
async def scaffold_module(ctx: ToolContext, name: str) -> str:
    return f"src/{name}.py created"


async def _dev_loop(feature: str) -> str:
    """开发角色:用 AgentLoop 走 拆解→生成→收尾 一轮,产出变更说明。"""

    def decider_factory() -> Decider:
        calls = {"n": 0}

        async def decide(obs: list[str]) -> Action:
            _ = obs
            calls["n"] += 1
            if calls["n"] == 1:
                return Action.call_tool("scaffold_module", {"name": feature})
            return Action.finish(f"变更说明:新增模块 {feature} 与配套单测,并通过 QA 验收")

        return decide

    reg = ToolRegistry()
    reg.register(scaffold_module.spec, scaffold_module.fn)  # type: ignore[attr-defined]
    executor = ToolExecutor(registry=reg, audit=InMemoryAuditBus())
    loop = AgentLoop(
        decider=decider_factory(),
        checkpoint=CheckpointStore(),
        max_iterations=3,
        executor=executor,
    )
    run = await loop.run(f"实现 {feature}")
    return run.final_output


class FactoryReport(BaseModel):
    spec: str
    steps: list[PipelineStep]
    verdict_success_rate: float
    artifacts: list[str]


def register_architecture_skill() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(
        SkillDef(
            name="layered-architecture",
            scenario="系统设计 模块划分 分层架构 接口契约",
            steps=["识别领域模型", "划分模块边界", "定义接口契约", "输出结构决策"],
            version="1.0.0",
        )
    )
    return reg


async def run(spec: str) -> FactoryReport:
    steps = [
        PipelineStep(name="需求拆解", owner_role="pm"),
        PipelineStep(name="架构设计", owner_role="architect"),
        PipelineStep(name="代码开发", owner_role="developer"),
        PipelineStep(name="测试验收", owner_role="qa"),
    ]

    # PM:拆任务(委托八要素的工厂化应用)
    tasks = [
        SubagentTask(goal=f"{spec}-领域建模", aspect="design", timeout_s=1),
        SubagentTask(goal=f"{spec}-接口契约", aspect="design", timeout_s=1),
    ]
    _ = tasks  # PM 产物交给架构师,教学演示保留委托结构

    # 架构师:匹配技能并输出结构决策
    skill = register_architecture_skill().find(f"{spec} 分层架构 模块划分")
    steps[1].outputs = list(skill.steps) if skill else []

    # 开发:AgentLoop 产出变更
    change_note = await _dev_loop("user_service")
    steps[2].outputs = [change_note]

    # QA:Golden 用例验收
    cases = [
        GoldenCase(case_id="qa1", input=spec, expected_keywords=["模块"], expected_tools=[]),
        GoldenCase(case_id="qa2", input=spec, expected_keywords=["测试"], expected_tools=[]),
    ]

    async def agent_fn(_: str) -> AgentAnswer:
        return AgentAnswer(text=f"模块边界清晰,测试齐全,验收通过:{change_note}")

    report = await EvalRunner(judge=KeywordJudge()).run(cases, agent_fn)
    steps[3].outputs = [f"QA 通过率 {report.task_success_rate:.0%}"]
    steps[0].done = steps[1].done = steps[2].done = True
    steps[3].done = report.task_success_rate == 1.0

    return FactoryReport(
        spec=spec,
        steps=steps,
        verdict_success_rate=report.task_success_rate,
        artifacts=[change_note, f"skill={skill.name if skill else 'none'}"],
    )
