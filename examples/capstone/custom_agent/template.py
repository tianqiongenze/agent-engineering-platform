"""Capstone C · 自选业务 Agent 模板(业务拆解七步)。

按第七章方法论给出"填空式"工作表:从业务 SOP 出发逐格推导
Loop/Tool/Skill/HITL/回滚/Eval,输出可评审的 Agent 设计草案。
样板:IT 工单处理 Agent。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SopWorksheet:
    """七步拆解工作表(对应课件 7-3 业务流程拆解)。"""

    name: str
    goal: str
    sop_steps: list[str]  # 业务 SOP → Agent Loop
    tools: list[str]  # 岗位任务 → Tool
    knowledge_sources: list[str]  # 知识资产 → RAG
    skills: list[str]  # 经验方法论 → Skill
    hitl_nodes: list[str]  # 风险节点 → Human-in-the-loop
    rollback: list[str]  # 失败场景 → 回滚
    eval_metrics: list[str] = field(
        default_factory=lambda: [
            "task_success_rate",
            "human_handoff_rate",
            "avg_cost",
            "p95_latency",
        ]
    )


def from_sop(
    name: str,
    goal: str,
    sop_steps: list[str],
    tools: list[str],
    knowledge_sources: list[str],
    skills: list[str],
    hitl_nodes: list[str],
    rollback: list[str],
) -> SopWorksheet:
    if not sop_steps or not tools:
        raise ValueError("SOP 步骤与工具清单不可为空(没有 SOP 就没有 Loop)")
    return SopWorksheet(
        name=name,
        goal=goal,
        sop_steps=sop_steps,
        tools=tools,
        knowledge_sources=knowledge_sources,
        skills=skills,
        hitl_nodes=hitl_nodes,
        rollback=rollback,
    )


def build_agent_plan(ws: SopWorksheet) -> dict[str, list[str]]:
    """把工作表固化为 Agent 设计草案(评审 + 开发排期输入)。"""
    return {
        "loop": list(ws.sop_steps),
        "tools": list(ws.tools),
        "rag": list(ws.knowledge_sources),
        "skills": list(ws.skills),
        "hitl": list(ws.hitl_nodes),
        "rollback": list(ws.rollback),
        "eval": list(ws.eval_metrics),
    }


def it_worksheet() -> SopWorksheet:
    """完整示例:IT 工单处理 Agent。"""
    return from_sop(
        name="it-ticket-agent",
        goal="自动处理 IT 工单,高危操作人工确认,处理时长从天级降到小时级",
        sop_steps=[
            "接收工单并分类分级",
            "检索知识库匹配历史方案",
            "生成处置方案",
            "高危操作等待人工确认",
            "执行处置并验证",
            "关闭工单并回访",
        ],
        tools=["search_kb", "query_cmdb", "reset_password", "restart_service"],
        knowledge_sources=["运维手册", "历史工单库", "CMDB 配置项"],
        skills=["troubleshooting", "incident-review"],
        hitl_nodes=["restart_service"],
        rollback=["变更回滚脚本", "工单退回人工队列"],
    )
