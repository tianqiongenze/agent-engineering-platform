"""BC6 · Agent Eval(阶段五):Golden Set / 指标 / Judge / 回归对比。

Judge 抽象:KeywordJudge 为规则基线;LLM-as-Judge 与人工评测按同一协议接入。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel


class GoldenCase(BaseModel):
    case_id: str
    input: str
    expected_keywords: list[str]
    expected_tools: list[str] = []
    meta: dict[str, str] = {}


class AgentAnswer(BaseModel):
    text: str
    tools_used: list[str] = []
    latency_ms: float = 0.0
    tokens: int = 0


@dataclass
class CaseVerdict:
    case_id: str
    passed: bool
    tool_hit_rate: float
    notes: str = ""


@dataclass
class EvalReport:
    total: int
    passed: int
    task_success_rate: float
    tool_call_accuracy: float
    verdicts: list[CaseVerdict] = field(default_factory=list)


@dataclass
class RegressionDelta:
    improved: list[str]
    regressed: list[str]


class Judge(Protocol):
    def judge(self, case: GoldenCase, answer: AgentAnswer) -> bool: ...


class KeywordJudge:
    """规则基线:全部期望关键词命中才算通过。"""

    def judge(self, case: GoldenCase, answer: AgentAnswer) -> bool:
        return all(kw in answer.text for kw in case.expected_keywords)


AgentFn = Callable[[str], Awaitable[AgentAnswer]]


class EvalRunner:
    def __init__(self, judge: Judge) -> None:
        self.judge = judge

    async def run(self, cases: list[GoldenCase], agent_fn: AgentFn) -> EvalReport:
        verdicts: list[CaseVerdict] = []
        tool_hits: list[float] = []
        for case in cases:
            answer = await agent_fn(case.input)
            passed = self.judge.judge(case, answer)
            if case.expected_tools:
                hit = len(set(case.expected_tools) & set(answer.tools_used)) / len(
                    case.expected_tools
                )
            else:
                hit = 1.0
            tool_hits.append(hit)
            verdicts.append(CaseVerdict(case_id=case.case_id, passed=passed, tool_hit_rate=hit))
        passed_n = sum(1 for v in verdicts if v.passed)
        return EvalReport(
            total=len(cases),
            passed=passed_n,
            task_success_rate=passed_n / max(1, len(cases)),
            tool_call_accuracy=sum(tool_hits) / max(1, len(tool_hits)),
            verdicts=verdicts,
        )

    @staticmethod
    def regression(old: EvalReport, new: EvalReport) -> RegressionDelta:
        old_map = {v.case_id: v.passed for v in old.verdicts}
        new_map = {v.case_id: v.passed for v in new.verdicts}
        improved = [cid for cid, ok in new_map.items() if ok and not old_map.get(cid, False)]
        regressed = [cid for cid, ok in new_map.items() if not ok and old_map.get(cid, False)]
        return RegressionDelta(improved=improved, regressed=regressed)
