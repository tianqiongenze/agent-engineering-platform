#!/usr/bin/env python3
"""第四轮 PPT 注入(审查驱动):前沿趋势 14 页 + 企业案例 7 页 + QUIZ 补 6 + CODE 补 5。幂等。"""

from __future__ import annotations

import sys
from pathlib import Path

DIR = Path(__file__).parent / "ppt_content"

TRENDS = {
"ch1.txt": [
 ("M1 里程碑:平台已有能力", """#GRID 2026 前沿①:提示词工程新范式|DSPy:Prompt 编译器(程序化优化);Prompt Caching 经济学:官方缓存省 50~90% 输入费;结构化输出已成为 API 原生能力;A/B→多臂老虎机自动择优|cols=2|企业案例:Cursor 的 Cursor Rules 生态"""),
 ("本章小结", """#GRID 2026 前沿②:模型生态与案例|国产双雄:GLM-5(1M 上下文)/DeepSeek-V4(推理强);编码代理:Claude Code/Cursor/Devin(任务级自主);国内平台:扣子(Coze)/百炼(阿里);本课程:双协议实测 GLM-5.3|cols=2|2026-10 实测数据在册"""),
],
"ch2.txt": [
 ("MCP 是什么", """#GRID 2026 前沿①:MCP 生态演进|Streamable HTTP 取代 stdio 为主流传输;Server 目录化:一次接入处处复用;企业网关:集中鉴权/审计/配额;本平台:PulsarAuditBus+三层权限|cols=2|与 OWASP LLM Top10 联动"""),
 ("MCP 审计与连接管理", """#GRID 2026 前沿②:Agent 安全框架|OWASP LLM Top10(2025 版):提示注入/敏感泄露/供应链/越权;Agent 身份:服务账号+短期凭证(M2M);审计防篡改:哈希链(平台已实现);等保 2.0:日志留存≥6 个月|cols=2|面试高频:安全三件套"""),
],
"ch3.txt": [
 ("LangGraph 核心对象", """#GRID 2026 前沿①:编排生态|LangGraph 1.0:生产化里程碑(Checkpointer 原生);OpenAI Agents SDK:Handoffs 范式;A2A 协议:跨厂商 Agent 互操作( discovery/card);本平台:Decider 防腐层可对接任一框架|cols=2|A2A=Agent 界的 HTTP"""),
 ("本章小结", """#GRID 2026 前沿②:Computer Use 与多模态|Computer Use:GUI 操作型 Agent(浏览器/桌面);Browser Use:结构化网页操作;多模态输入:截图理解→操作决策;本平台延伸:Sandbox 内跑无头浏览器|cols=2|案例:Manus 通用任务代理"""),
],
"ch4.txt": [
 ("混合检索的工程实现", """#GRID 2026 前沿①:RAG 演进|Agentic RAG:检索器作为工具被 Loop 调度;GraphRAG:知识图谱+社区摘要(全局问题);Contextual Retrieval:块级上下文预生成;长上下文≠免检索:成本仍 10x+|cols=2|企业案例:百炼企业知识库"""),
 ("LLM Wiki 的定义", """#GRID 2026 前沿②:记忆与知识新范式|Agentic Memory:记忆写入/检索/遗忘自治;向量库→混合库:向量+图+倒排一体;课程记忆:技能库即长期记忆;平台:MemoryStore 三层已对齐|cols=2|LangSmith/AgentOps=记忆可观测"""),
],
"ch5.txt": [
 ("六角色协作分析任务", """#GRID 2026 前沿①:多 Agent 互操作|A2A 协议:Agent Card 发现+任务委派;Anthropic.subagents:子代理即一等公民;Supervisor→Handoffs 范式融合;平台对照:SubagentTask+aspect 仲裁|cols=2|评测平台:LangSmith/AgentOps 对比讲义"""),
 ("Eval 平台能力清单", """#GRID 2026 前沿②:评测即基础设施|LLM-as-Judge 标准化(评分卡+理由);在线评测:流量抽样回流;成本评测:每任务 $ 曲线;平台对照:EvalRunner+回归门禁|cols=2|案例:Devin 的回放式评测"""),
],
"ch6.txt": [
 ("vLLM:为什么是主流", """#GRID 2026 前沿①:推理服务演进|vLLM v1 引擎:零开销前缀缓存;PD 分离:Prefill/Decode 独立扩缩;国产推理:GLM/DeepSeek 官方端点 OpenAI 兼容;评测:tokens/s/卡 为采购指标|cols=2|案例:百炼/火山方舟企业部署"""),
 ("MCP Server 生产化清单", """#GRID 2026 前沿②:安全与身份生产化|OWASP LLM Top10 落地清单(注入/越权/供应链);Agent 身份:每 Agent 独立凭证+最小权;等保 2.0 三级:审计留存/边界防护;平台:WAF 模板+哈希链+JWT/M2M 可扩展|cols=2|企业案例:金融 Agent 合规落地"""),
],
"ch7.txt": [
 ("案例一:企业级深度研究平台", """#GRID 2026 前沿①:研究类产品图谱|Manus:通用任务代理(多工具长任务);DeepResearch 类:OpenAI/Gemini 深研模式;企业内:尽调/竞品/行研平台化;本课 Capstone A=同类 MVP|cols=2|差异化:证据链+可审计"""),
 ("五选一边界判断", """#GRID 2026 前沿②:编码代理与选型|Devin/Claude Code/Cursor:三条路线对比;国内:通义灵码/CodeGeeX;选型:任务自主度×可控性矩阵;本课:Codebase Agent=自主度可控版|cols=2|面试:能讲清三者差异即加分"""),
],
}

QUIZ = {
"ch1.txt": ("Lab1 验收清单", "#QUIZ 自测 · 结构化输出与 Gateway\nQ1 为什么禁止裸解析自然语言?\nQ2 反喂重试的 Prompt 怎么构造?\nQ3 语义缓存阈值为什么 0.92?\nQ4 Gateway 单点怎么防?"),
"ch2.txt": ("Lab2 实战指引", "#QUIZ 自测 · MCP 与集成\nQ1 MCP 与 FC 的分工边界?\nQ2 三层权限如何收敛?\nQ3 Server 版本漂移如何防控?\nQ4 CLI 调试为何要先于接模型?"),
"ch3.txt": ("Lab3 验收清单", "#QUIZ 自测 · Harness 与 LangGraph\nQ1 Harness 五要素如何注入测试?\nQ2 LangGraph 与本平台 Loop 的映射?\nQ3 Computer Use 型 Agent 的沙箱要求?\nQ4 何时选 A2A 而非进程内子代理?"),
"ch4.txt": ("Lab4 验收清单", "#QUIZ 自测 · RAG 前沿\nQ1 Agentic RAG 与管线式 RAG 差异?\nQ2 GraphRAG 适合哪类问题?\nQ3 记忆如何防污染?\nQ4 检索回归四指标如何组合?"),
"ch5.txt": ("Lab5 验收清单", "#QUIZ 自测 · 评测平台化\nQ1 LLM-as-Judge 三偏置的对策?\nQ2 在线评测如何抽样回流?\nQ3 A2A 的 Agent Card 含什么?\nQ4 成本评测的曲线怎么画?"),
"ch7.txt": ("本章小结", "#QUIZ 自测 · 产品化与案例\nQ1 Cursor/Devin/Claude Code 路线差异?\nQ2 扣子/百炼的定位区别?\nQ3 你的 Capstone 对标哪个产品?"),
}

CODE = {
"ch1.txt": ("应用:会议纪要模板", "src/agent_platform/security/guard.py:118-138", "SecurityStack:风控组合入口"),
"ch2.txt": ("MCP 权限控制", "src/agent_platform/tools/pulsar_audit.py:56-88", "PulsarAuditBus:异步安全投递"),
"ch4.txt": ("混合检索的工程实现", "src/agent_platform/shared/semantic_cache.py:44-88", "SemanticCache:精确+语义双段"),
"ch6.txt": ("灰度发布维度", "src/agent_platform/security/auth.py:36-70", "JwtCodec:HS256 签发与校验"),
"ch3.txt": ("中断恢复实战", "src/agent_platform/shared/dao.py:34-52", "DatabaseRouter:异步写会话+锚定"),
}


def enrich(fname: str, blocks: list[tuple[str, str]]) -> int:
    path = DIR / fname
    lines = path.read_text().splitlines()
    inserted = 0
    for anchor, block in blocks:
        head = block.splitlines()[0].strip()
        if any(ln.strip() == head for ln in lines):
            continue
        pos = None
        for i, ln in enumerate(lines):
            if ln.startswith("#") and anchor in ln:
                pos = i
                break
        if pos is None:
            print(f"  ⚠ {fname} miss: {anchor[:30]}")
            continue
        j = pos + 1
        while j < len(lines) and not lines[j].startswith("#"):
            j += 1
        lines[j:j] = block.strip().splitlines() + [""]
        inserted += 1
    path.write_text("\n".join(lines) + "\n")
    return inserted


def main() -> int:
    total = 0
    for fname, blocks in TRENDS.items():
        n = enrich(fname, blocks)
        total += n
    print(f"趋势+案例: +{total}")
    # QUIZ 补 6
    q = 0
    for fname, (anchor, block) in QUIZ.items():
        q += enrich(fname, [(anchor, block)])
    print(f"QUIZ 补: +{q}")
    # CODE 补 5
    c = 0
    for fname, (anchor, spec, title) in CODE.items():
        c += enrich(fname, [(anchor, f"#CODE {title}|{spec}")])
    print(f"CODE 补: +{c}")
    print(f"第四轮合计 +{total + q + c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
