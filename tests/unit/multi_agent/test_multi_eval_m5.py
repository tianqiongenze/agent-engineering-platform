"""阶段五(M5)Multi-Agent / Skill / Eval 单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from agent_platform.eval.evaluator import (
    AgentAnswer,
    EvalReport,
    EvalRunner,
    GoldenCase,
    KeywordJudge,
)
from agent_platform.multi_agent.skill import SkillDef, SkillRegistry
from agent_platform.multi_agent.supervisor import (
    SubagentTask,
    SupervisorAgent,
    Worker,
    WorkerResult,
)

pytestmark = pytest.mark.unit


class OkWorker(Worker):
    def __init__(self, name: str, verdict: str, evidence_count: int = 2) -> None:
        self.name = name
        self._verdict = verdict
        self._evidence = evidence_count

    async def run(self, task: SubagentTask) -> WorkerResult:
        return WorkerResult(
            worker=self.name,
            conclusion=self._verdict,
            evidence=[f"e{i}" for i in range(self._evidence)],
            risk="low",
        )


class TimeoutWorker(Worker):
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, task: SubagentTask) -> WorkerResult:
        await asyncio.sleep(5)
        raise AssertionError("should not reach")


class TestSupervisor:
    async def test_parallel_delegation_and_aggregation(self) -> None:
        sup = SupervisorAgent(worker_timeout_s=1.0)
        tasks = [
            SubagentTask(goal="架构分析", allowed_tools=["list_files"], timeout_s=1),
            SubagentTask(goal="测试分析", allowed_tools=["run_test"], timeout_s=1),
            SubagentTask(goal="安全分析", allowed_tools=["search_code"], timeout_s=1),
        ]
        workers = [
            OkWorker("arch", "模块边界清晰"),
            OkWorker("test", "覆盖率不足"),
            OkWorker("sec", "无越权"),
        ]
        report = await sup.run("可维护性分析", tasks, workers)
        assert report.all_done
        assert len(report.results) == 3
        assert "架构分析" in report.summary
        assert report.conflicts == []

    async def test_conflict_detected_and_arbitrated(self) -> None:
        sup = SupervisorAgent(worker_timeout_s=1.0)
        tasks = [
            SubagentTask(goal="A 视角", aspect="verdict", timeout_s=1),
            SubagentTask(goal="B 视角", aspect="verdict", timeout_s=1),
        ]
        workers = [
            OkWorker("w1", "结论甲", evidence_count=1),
            OkWorker("w2", "结论乙", evidence_count=3),  # 证据更多,应赢得仲裁
        ]
        report = await sup.run("争议任务", tasks, workers)
        assert len(report.conflicts) == 1
        assert report.arbitrated_verdict == "结论乙"  # 按证据数量仲裁

    async def test_timeout_worker_isolated_not_blocking(self) -> None:
        sup = SupervisorAgent(worker_timeout_s=0.2)
        tasks = [
            SubagentTask(goal="慢任务", timeout_s=0.1),
            SubagentTask(goal="快任务", timeout_s=1),
        ]
        workers = [TimeoutWorker("slow"), OkWorker("fast", "ok")]
        report = await sup.run("混合任务", tasks, workers)
        # 隔离语义:慢 worker 以失败记录返回,不挂死整体;快任务结论完好
        assert len(report.results) == 2
        slow = next(r for r in report.results if r.worker == "slow")
        assert slow.error is not None and "timeout" in slow.error.lower()
        fast = next(r for r in report.results if r.worker == "fast")
        assert fast.conclusion == "ok"


class TestSkillRegistry:
    def test_register_and_match_by_scenario(self) -> None:
        reg = SkillRegistry()
        reg.register(
            SkillDef(
                name="code-review",
                scenario="代码审查 PR 质量把关",
                steps=["读 diff", "查规范", "输出审查意见"],
            )
        )
        reg.register(
            SkillDef(
                name="competitor-analysis",
                scenario="竞品分析 行业调研",
                steps=["收集资料", "交叉验证", "生成报告"],
            )
        )
        assert reg.find("帮我审查这个 PR") is not None
        assert reg.find("做一份竞品分析").name == "competitor-analysis"
        assert reg.find("今天天气") is None

    def test_skill_versioning(self) -> None:
        reg = SkillRegistry()
        scenario = "生产事故复盘 分析根因 输出改进项"
        reg.register(SkillDef(name="s", scenario=scenario, steps=["a"], version="1.0"))
        reg.register(SkillDef(name="s", scenario=scenario, steps=["a", "b"], version="2.0"))
        assert reg.find("帮我做一次生产事故复盘 分析根因").version == "2.0"


class TestEval:
    async def test_success_rate_and_tool_accuracy(self) -> None:
        cases = [
            GoldenCase(
                case_id="c1",
                input="查天气",
                expected_keywords=["sunny"],
                expected_tools=["get_weather"],
            ),
            GoldenCase(
                case_id="c2",
                input="查天气2",
                expected_keywords=["sunny"],
                expected_tools=["get_weather"],
            ),
            GoldenCase(
                case_id="c3",
                input="查天气3",
                expected_keywords=["rain"],
                expected_tools=["get_weather"],
            ),
        ]

        async def agent(inp: str) -> AgentAnswer:
            return AgentAnswer(text="it is sunny", tools_used=["get_weather"])

        report: EvalReport = await EvalRunner(judge=KeywordJudge()).run(cases, agent)
        assert report.task_success_rate == pytest.approx(2 / 3)
        assert report.tool_call_accuracy == 1.0

    async def test_regression_comparison(self) -> None:
        cases = [GoldenCase(case_id="c1", input="q", expected_keywords=["good"], expected_tools=[])]

        async def v1(inp: str) -> AgentAnswer:
            return AgentAnswer(text="bad", tools_used=[])

        async def v2(inp: str) -> AgentAnswer:
            return AgentAnswer(text="good", tools_used=[])

        runner = EvalRunner(judge=KeywordJudge())
        old = await runner.run(cases, v1)
        new = await runner.run(cases, v2)
        delta = EvalRunner.regression(old, new)
        assert delta.improved == ["c1"] and delta.regressed == []
