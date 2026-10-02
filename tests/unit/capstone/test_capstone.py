"""Capstone 三案例骨架测试。"""

from __future__ import annotations

import pytest
from examples.capstone.custom_agent.template import (
    build_agent_plan,
    from_sop,
    it_worksheet,
)
from examples.capstone.deep_research.research import (
    register_skills,
    report_md,
    run_research,
)
from examples.capstone.software_factory.factory import run as run_factory

pytestmark = pytest.mark.unit


class TestDeepResearch:
    async def test_skill_registered_and_matchable(self) -> None:
        reg = register_skills()
        assert reg.find("帮我做一份竞品分析") is not None

    async def test_research_report_has_evidence(self) -> None:
        report = await run_research("竞品A 市场表现")
        assert report.results and all(r.evidence for r in report.results)
        md = report_md(report)
        assert "## 证据链" in md and "来源" in md

    async def test_no_hit_still_aggregates(self) -> None:
        report = await run_research("量子物理实验设计")
        assert len(report.results) == 2  # collector 空结果也被聚合留痕


class TestSoftwareFactory:
    async def test_pipeline_all_done(self) -> None:
        report = await run_factory("工单中心")
        assert all(s.done for s in report.steps)
        assert len(report.steps) == 4

    async def test_qa_verdict_full_pass(self) -> None:
        report = await run_factory("订单服务")
        assert report.verdict_success_rate == 1.0
        assert report.artifacts and "变更说明" in report.artifacts[0]


class TestCustomAgent:
    def test_from_sop_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="SOP"):
            from_sop("x", "g", [], [], [], [], [], [])

    def test_plan_has_all_sections(self) -> None:
        plan = build_agent_plan(it_worksheet())
        for key in ("loop", "tools", "rag", "skills", "hitl", "rollback", "eval"):
            assert plan[key], f"{key} 不可为空"
        assert "restart_service" in plan["hitl"]

    def test_it_sample_walkthrough(self) -> None:
        ws = it_worksheet()
        assert ws.name == "it-ticket-agent"
        assert len(ws.sop_steps) >= 5
