"""BC5 · Multi-Agent:Supervisor 委托 / 并行执行 / 聚合仲裁(阶段五)。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4


@dataclass
class SubagentTask:
    """任务委托八要素(大纲 §5.2)的教学最小完备集。"""

    goal: str
    aspect: str = ""  # 判断面:同 aspect 的结论分歧才算冲突
    input_context: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    permission: str = "readonly"  # 默认只读,写操作单独授权
    expected_output: str = "conclusion"
    output_format: str = "json"
    timeout_s: float = 30.0
    quality_bar: str = "evidence-backed"


@dataclass
class WorkerResult:
    worker: str
    conclusion: str = ""
    evidence: list[str] = field(default_factory=list)
    risk: str = "low"
    error: str | None = None


@dataclass
class Conflict:
    field_name: str
    conclusions: list[str]


class Worker(Protocol):
    name: str

    async def run(self, task: SubagentTask) -> WorkerResult: ...


@dataclass
class SupervisorReport:
    run_id: str
    goal: str
    results: list[WorkerResult]
    conflicts: list[Conflict]
    arbitrated_verdict: str | None
    summary: str
    all_done: bool = True


class SupervisorAgent:
    """Supervisor 模式:并行委托 → 隔离超时 → 聚合 → 冲突仲裁(证据多数)。"""

    def __init__(self, worker_timeout_s: float = 30.0) -> None:
        self.worker_timeout_s = worker_timeout_s

    async def _run_one(self, worker: Worker, task: SubagentTask) -> WorkerResult:
        try:
            return await asyncio.wait_for(
                worker.run(task), timeout=min(task.timeout_s, self.worker_timeout_s)
            )
        except TimeoutError:
            return WorkerResult(worker=worker.name, error="worker timeout")
        except Exception as exc:  # 隔离:单 worker 故障不拖垮整体
            return WorkerResult(worker=worker.name, error=f"worker failed: {exc}")

    async def run(
        self, goal: str, tasks: list[SubagentTask], workers: list[Worker]
    ) -> SupervisorReport:
        results = await asyncio.gather(
            *(self._run_one(w, t) for w, t in zip(workers, tasks, strict=False))
        )
        results = list(results)

        # 冲突检测:同一判断面(aspect)上的结论分歧;aspect 为空不参与
        conflicts: list[Conflict] = []
        arbitrated: str | None = None
        aspects: dict[str, list[WorkerResult]] = {}
        for task, res in zip(tasks, results, strict=False):
            if task.aspect and res.error is None:
                aspects.setdefault(task.aspect, []).append(res)
        for aspect, group in aspects.items():
            verdicts = list({r.conclusion for r in group})
            if len(verdicts) > 1:
                conflicts.append(Conflict(field_name=aspect, conclusions=verdicts))
                # 仲裁规则:证据数量最多者胜;平局取首个(教学演示,生产可人工介入)
                winner = max(group, key=lambda r: (len(r.evidence), r.worker))
                arbitrated = winner.conclusion

        summary_lines = [
            f"任务:{goal}",
            *[
                f"- {t.goal} → {r.conclusion if not r.error else f'[失败:{r.error}]'}"
                for t, r in zip(tasks, results, strict=False)
            ],
        ]
        if conflicts:
            summary_lines.append(f"冲突仲裁:{arbitrated}(按证据数量)")

        return SupervisorReport(
            run_id=uuid4().hex[:12],
            goal=goal,
            results=results,
            conflicts=conflicts,
            arbitrated_verdict=arbitrated,
            summary="\n".join(summary_lines),
            all_done=all(r.error is None for r in results),
        )
