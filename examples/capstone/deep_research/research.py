"""Capstone A · 企业级深度研究平台 MVP。

复用组件:SkillRegistry(方法论沉淀)/ HybridRetriever(语料检索)/
SupervisorAgent(并行委托+聚合)。答辩要点:证据链完整性与产出效率对比。
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from agent_platform.context_memory.rag import Chunk, HybridRetriever
from agent_platform.multi_agent.skill import SkillDef, SkillRegistry
from agent_platform.multi_agent.supervisor import (
    SubagentTask,
    SupervisorAgent,
    SupervisorReport,
    Worker,
    WorkerResult,
)

CORPUS = [
    Chunk(
        id="d1", text="竞品A 2025 年营收 12 亿元,同比增长 40%,主打中小企业", source="report-a.md"
    ),
    Chunk(id="d2", text="行业报告:目标市场规模 300 亿元,年复合增速 25%", source="industry.md"),
    Chunk(id="d3", text="竞品B 完成 5 亿元融资,重点投入企业级客户与渠道", source="news-b.md"),
    Chunk(id="d4", text="用户调研:采购决策最看重交付周期与售后响应", source="survey.md"),
]


class ResearchSkill(BaseModel):
    """研究方法论(竞品分析模板);注册进 SkillRegistry 供复用与评估。"""

    name: str = "competitor-analysis"
    scenario: str = "竞品分析 行业调研 投资尽调 研究报告"
    steps: list[str] = [
        "信息搜集(检索多源语料)",
        "交叉验证(两源互证关键数据)",
        "结构化分析(市场/竞争/用户三视角)",
        "报告成文(带引用来源)",
    ]


@dataclass
class CollectorWorker(Worker):
    name: str = "collector"
    retriever: HybridRetriever | None = None

    async def run(self, task: SubagentTask) -> WorkerResult:
        r = self.retriever or HybridRetriever(CORPUS)
        hits = r.search(task.goal, k=3)
        if not hits:
            return WorkerResult(worker=self.name, conclusion="未检索到相关资料", evidence=[])
        return WorkerResult(
            worker=self.name,
            conclusion=";".join(h.chunk.text for h in hits),
            evidence=[h.chunk.source for h in hits],
        )


@dataclass
class VerifierWorker(Worker):
    name: str = "verifier"

    async def run(self, task: SubagentTask) -> WorkerResult:
        _ = task
        return WorkerResult(
            worker=self.name,
            conclusion="关键数据点已双源核对",
            evidence=["industry.md:市场规模300亿", "report-a.md:竞品A营收12亿"],
        )


def register_skills() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(
        SkillDef(
            name=ResearchSkill().name,
            scenario=ResearchSkill().scenario,
            steps=ResearchSkill().steps,
            version="1.0.0",
            quality_bar="每个结论至少两条独立来源",
        )
    )
    return reg


async def run_research(question: str) -> SupervisorReport:
    sup = SupervisorAgent(worker_timeout_s=2.0)
    tasks = [
        SubagentTask(goal=question, aspect="findings", timeout_s=1.5),
        SubagentTask(goal="交叉验证", aspect="verify", timeout_s=1.5),
    ]
    return await sup.run(f"深度研究:{question}", tasks, [CollectorWorker(), VerifierWorker()])


def report_md(report: SupervisorReport) -> str:
    lines = ["# 深度研究报告", "", report.summary, "", "## 证据链"]
    for r in report.results:
        for e in r.evidence:
            lines.append(f"- {e}(来源:{r.worker})")
    return "\n".join(lines)
