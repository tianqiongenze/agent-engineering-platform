#!/usr/bin/env python3
"""生成 7 章授课 PPT(数据驱动,python-pptx)。

用法:uv run --with python-pptx python scripts/gen_pptx.py
输出:../../03-课件PPT/第N章-*.pptx
视觉规范:16:9 · 深空蓝封面 · 白底内容页 · 科技蓝主色 · 琥珀点缀
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

# ── 视觉规范 ────────────────────────────────────────────────
INK = RGBColor(0x0B, 0x1D, 0x3A)      # 深空蓝(封面/标题带)
BLUE = RGBColor(0x25, 0x63, 0xEB)     # 科技蓝(强调)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)    # 琥珀(点缀)
GREY = RGBColor(0x47, 0x55, 0x69)     # 正文灰
LIGHT = RGBColor(0xF1, 0xF5, 0xF9)    # 浅灰蓝(代码块底)
FONT = "PingFang SC"
W, H = Emu(12192000), Emu(6858000)     # 16:9

OUT = Path(__file__).resolve().parents[3] / "03-课件PPT"


def _set(box, text: str, size: int, color=GREY, bold=False, align=PP_ALIGN.LEFT):
    box.text_frame.word_wrap = True
    first = True
    for line in text.split("\n"):
        p = box.text_frame.paragraphs[0] if first else box.text_frame.add_paragraph()
        first = False
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color


def slide_cover(prs: Presentation, chapter_no: str, title: str, subtitle: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_shape(1, 0, 0, W, H).fill.solid()
    s.shapes[0].fill.fore_color.rgb = INK
    band = s.shapes.add_shape(1, 0, H - Emu(280000), W, Emu(280000))
    band.fill.solid(); band.fill.fore_color.rgb = AMBER
    _set(s.shapes.add_textbox(Emu(900000), Emu(1500000), W - Emu(1800000), Emu(700000)),
         f"第 {chapter_no} 章", 28, AMBER, True)
    _set(s.shapes.add_textbox(Emu(900000), Emu(2100000), W - Emu(1800000), Emu(1600000)),
         title, 44, RGBColor(255, 255, 255), True)
    _set(s.shapes.add_textbox(Emu(900000), Emu(3900000), W - Emu(1800000), Emu(900000)),
         subtitle, 18, RGBColor(0xCB, 0xD5, 0xE1))
    _set(s.shapes.add_textbox(Emu(900000), Emu(5300000), W - Emu(1800000), Emu(500000)),
         "AI Agent 全栈工程师训练营 · Agent Engineering Platform", 14,
         RGBColor(0x94, 0xA3, 0xB8))


def slide_content(prs: Presentation, title: str, body: str, note: str | None = None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(1, 0, 0, W, Emu(1100000))
    bar.fill.solid(); bar.fill.fore_color.rgb = INK
    tag = s.shapes.add_shape(1, 0, 0, Emu(160000), Emu(1100000))
    tag.fill.solid(); tag.fill.fore_color.rgb = AMBER
    _set(s.shapes.add_textbox(Emu(400000), Emu(180000), W - Emu(800000), Emu(760000)),
         title, 26, RGBColor(255, 255, 255), True)
    _set(s.shapes.add_textbox(Emu(700000), Emu(1550000), W - Emu(1400000), Emu(4200000)),
         body, 17, GREY)
    if note:
        box = s.shapes.add_shape(1, Emu(700000), Emu(5650000), W - Emu(1400000), Emu(800000))
        box.fill.solid(); box.fill.fore_color.rgb = LIGHT
        tf = box.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = "▶ " + note
        r.font.name = FONT; r.font.size = Pt(13); r.font.color.rgb = BLUE


def build(no: str, title: str, subtitle: str, pages: list[tuple[str, str, str | None]]):
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    slide_cover(prs, no, title, subtitle)
    for t, b, n in pages:
        slide_content(prs, t, b, n)
    out = OUT / f"第{no}章-{title.split(':')[0]}.pptx"
    prs.save(out)
    print("生成:", out.name, f"({len(prs.slides.__iter__.__self__._sldIdLst)} 页)")


CHAPTERS = {
    "1": ("LLM API、Prompt 与结构化输出", "从 HTTP 工程师到模型调用工程师 · 里程碑 M1", [
        ("本章定位与学习目标", "▎解决『如何稳定调用模型』\n• Chat Completions / Responses API 结构\n• 模型参数:temperature / top_p / max_tokens\n• Token 与 Context Window:成本与延迟的第一性约束\n• 岗位视角:把模型能力封装成稳定服务", "对应工程:gateway/domain.py(12 个 TDD 测试守护)"),
        ("错误与重试:LLM 调用的不确定性", "▎四类典型故障与对策\n• 超时 → 分级超时预算(本地/外部/模型)\n• 限流 429 → 指数退避 + jitter\n• 输出格式错误 → 校验反喂重试\n• 全链路失败 → ModelRouter fallback 到次模型", "工程:ModelRouter 全部失败抛 AllProvidersFailedError 并留痕"),
        ("Streaming 流式输出", "▎为什么必须流式:推理延迟高,串行等待毁体验\n• SSE 协议:HTTP 长连接 + data: 事件\n• FastAPI StreamingResponse 低延迟转发\n• 中断与取消:用户随时止损 Token\n• 末块携带 Usage → 成本留痕数据源", "实测:POST /v1/chat/completions 打字机输出(本平台已验证)"),
        ("Prompt Engineering", "▎System Prompt = 模型的岗位说明书\n• 角色定义与行为约束\n• Few-shot:2-3 个输入输出范例\n• 任务拆解降低幻觉率\n• 模板化 + 版本管理:Prompt 是代码资产\n• 注入风险:用户输入永不拼进 system", "坑:Prompt 改动必须过回归测试(第 5 章 Eval)"),
        ("Structured Output 结构化输出", "▎Agent 系统禁止裸解析自然语言\n• JSON Schema 定义契约\n• Pydantic:Schema + 校验 + 反序列化三合一\n• 校验失败 → 错误反喂模型自修复\n• 多次失败 → 降级到缓存/默认值", "工程:ChatRequest.response_schema 已预留接入位"),
        ("LLM Gateway 统一入口", "▎平台第一个基础设施\n• OpenAI Compatible 统一协议,屏蔽多厂商差异\n• Provider 抽象 = 防腐层(上层永不 import 厂商 SDK)\n• MockProvider:CI 零外部依赖的确定性回放\n• Token / Cost / Latency 每次调用留痕", "ADR-002:Mock 属测试域,生产配置出现 mock 即 CI 红"),
        ("TDD 实验走查(Lab1)", "▎红 → 绿 → 重构的真实节奏\n① 先写 12 个失败测试(域模型不变量)\n② 最小实现转绿\n③ 覆盖率门禁 ≥80%(实测 98%)\n④ 重构:Usage.total 派生化,不变量入校验器", "验收:pytest -m unit 全绿 + SSE 演示 + 故障 fallback 演示"),
        ("小结与下一章", "▎本章交付\n• LLM Gateway 域模型/Provider/Router(测试守护)\n• GraphQL 查询面 + SSE 流式入口\n• 作品集叙事:『我建的模型网关带成本留痕与自动降级』\n▶ 下一章:让模型长出手 —— Function Calling 与 Tool Runtime", None),
    ]),
    "2": ("Function Calling、Tool Runtime 与 MCP", "工具治理与安全边界 · 里程碑 M2", [
        ("本章定位与学习目标", "▎解决『工具如何被安全地治理』\n• Function Calling 机制:模型选工具并生成参数\n• Tool Registry:注册/发现/版本/启停\n• 权限与风险分级:只读/写/高危\n• MCP:工具标准化接入协议", "对应工程:tools/runtime.py(22 测试守护)"),
        ("工具即契约:ToolSchema", "▎每个工具至少九要素\n• 名称/说明/输入 Schema/输出 Schema/错误 Schema\n• 权限级别/风险等级/超时配置/重试策略\n• @tool 装饰器:从函数签名自动派生 Pydantic 模型", "设计理由:Schema 是模型、Runtime、审计三方共享的契约"),
        ("Tool Registry 设计", "▎注册中心的六项能力\n• 注册与发现(关键词检索)\n• 元数据管理(按业务/读写/风险分类)\n• 版本管理与灰度切换\n• 依赖声明(服务/密钥/外部资源)\n• 启停:高危工具一键下线", "教学案例:disable 是 Registry 的状态,不污染共享 Spec(测试隔离事故复盘)"),
        ("权限与风险分级(RBAC)", "▎三层防线\n• readonly 角色只能调用 READ 工具\n• WRITE 需 agent 以上角色\n• DANGEROUS:人工确认凭据制(confirmed=True)\n• SQL/Shell 类工具默认进黑名单模式", "实测:readonly 调高危工具 → PermissionDeniedError"),
        ("审计与脱敏", "▎每次调用全链路留痕\n• AuditEvent:工具/参数/状态/耗时/run_id\n• 敏感参数脱敏:mask_args 集合 → ***MASKED***\n• 审计事件总线 → Pulsar(第 6 章生产化接线)", "生产红线:API Key 永不出现在审计日志"),
        ("超时与失败恢复", "▎工具异常不拖垮 Agent\n• asyncio.wait_for 硬超时\n• 失败结果结构化返回(ok=False + error)\n• 重试/参数修正/降级/人工兜底四层策略", "实测:慢工具 0.05s 超时 → 失败事件入审计"),
        ("MCP:Model Context Protocol", "▎Function Calling 管『模型怎么选』,MCP 管『工具怎么接』\n• Client 发现并调用 Server 暴露的工具/资源/Prompt\n• 接入形态:文件系统/数据库/GitHub/内部 API\n• MCP 适配层 = DDD 防腐层实例\n• 权限控制与连接管理", "实验:接入一个文件系统 MCP Server 并纳入统一审计"),
        ("小结与 Lab2 验收", "▎验收清单\n① 注册 5+ 工具且可被关键词发现\n② 高危工具必须人工确认才能执行\n③ 审计事件可在消费端核对\n④ 非法参数被 Schema 拦截\n▶ 下一章:工具串成长程任务 —— Agent Loop 与状态机", None),
    ]),
    "3": ("Agent Loop、State Machine 与 Codebase Agent", "从单轮调用到长程任务 · 里程碑 M3", [
        ("本章定位与学习目标", "▎解决『多步连续执行与失败恢复』\n• 从 ReAct 到五段循环:observe→think/plan→act→observe→finalize\n• 任务状态机(9 态)与 Checkpoint\n• Sandbox 执行边界\n• Codebase Agent:十类代码工具", "对应工程:orchestration/loop.py + sandbox.py"),
        ("Agent Loop 骨架", "▎循环三要素\n• Decider 抽象 = LLM 决策的防腐层(测试注入脚本)\n• 每轮:决策 → 执行工具 → 观察结果回灌\n• 终止:Finish 动作 / max_iterations / 死循环检测", "实测:连续 3 个完全相同动作 → LoopFailedError(死循环熔断)"),
        ("Planning 与任务拆解", "▎不是所有任务都要 Planner\n• 一次性计划:目标明确步骤稳定\n• 动态计划:信息随执行演化\n• 计划与执行的偏差处理:根据工具结果/测试失败调整\n• 固定 Workflow vs Agent Loop 的选择标准", "经验:能用 Workflow 就别上 Loop(成本与可控性)"),
        ("State Machine 与 Checkpoint", "▎9 态:created/planning/running/tool_failed/waiting_tool/waiting_approval/completed/failed/cancelled\n• 步骤记录:工具/参数/输出/失败原因/重试\n• Checkpoint 每轮落盘 → 中断恢复/失败复现/人工接管", "实测:kill 进程后 resume_from 续跑,历史观察完整带回"),
        ("Sandbox 与执行边界", "▎Agent 有文件/Shell/网络能力就必须被关进笼子\n• 文件:可读根/可写根/禁止区三分离\n• Shell:命令白名单 + 危险模式硬拦截\n• 本地 vs Docker 沙箱的边界差异\n• 全量操作审计 → 风险回放", "实测:rm -rf --no-preserve-root / 被硬拦截,白名单外一律拒"),
        ("Agent Harness 与 LangGraph", "▎Harness = 模型+工具+状态+上下文+环境的组织框架\n• LangGraph:StateGraph/条件分支/循环/Interrupt\n• 与 Dify/OpenAI Agents SDK 的定位对比\n• Human-in-the-loop:高风险动作前等待确认", "概念图走查:把平台 Loop 映射到 LangGraph 节点"),
        ("Codebase Agent 实战", "▎两个典型任务\n• 代码理解:『找出登录逻辑并输出文档』\n• 测试修复:『补测试并按失败日志修复』\n• 十类工具:list_files/search_code/read_file/write_file/apply_patch/run_test/run_command/git_diff/git_status/read_directory", "验收以真实仓库为准:输出含文件路径与调用链"),
        ("小结与 Lab3 验收", "▎验收清单\n① 演示仓库完成代码理解任务\n② 进程中断后 Checkpoint 恢复\n③ 危险命令被 Sandbox 拦截\n④ 状态机流转全程可查\n▶ 下一章:Agent 的认知上限 —— Context/Memory/RAG", None),
    ]),
    "4": ("Context Engineering、Memory 与 Codebase RAG", "决定 Agent 上限的不是模型,是它看到了什么 · 里程碑 M4", [
        ("本章定位与学习目标", "▎解决『信息进得来、记得住、找得到』\n• Context Packing/Budget/Compression\n• 三层记忆:短期/长期/项目级\n• 现代 RAG 全链路\n• LLM Wiki 知识治理", "对应工程:context_memory/ 三模块"),
        ("Context Engineering 本质", "▎Prompt Engineering 写好一句话,Context Engineering 管好整个窗口\n• Packing:什么进上下文,什么留外部\n• Budget:Token 预算装箱(教学近似 1 token≈1 词)\n• Compression:中段摘要折叠,保留头尾\n• 污染:无关信息稀释关键信息\n• KV Cache:理解它对长上下文成本的影响", "工程:ContextWindow.fit 返回压缩比报告(Context Debug Report 雏形)"),
        ("Working Memory 与 Scratchpad", "▎当前任务的工作面板\n• 目标/已完成步骤/工具结果/未解决问题\n• 当前风险与用户约束\n• 与 Agent State 的边界:State 是事实,Memory 是认知\n• 生命周期:任务结束即回收", "工程:MemoryStore.task_summary() 生成恢复锚点"),
        ("三层 Memory 体系", "▎短期:会话与任务状态(dict 级)\n▎长期:偏好/历史/常用工具(可检索,带置信度)\n▎项目级:技术栈/构建命令/编码规范/历史修复经验\n• 写入/检索/更新/删除/可信度五操作\n• 策略对比:记忆越全不等于成功率越高(成本权衡)", "实验:给 Codebase Agent 注入项目记忆,观察行为差异"),
        ("现代 RAG:解析与分块", "▎垃圾进垃圾出\n• 解析:PDF/Markdown/HTML/表格\n• 分块六法:固定长度/段落/标题/语义/代码 AST/重叠\n• Chunk Metadata:来源/行号/类型(引用的基础)", "代码 AST 分块是 Codebase RAG 的关键差异点"),
        ("现代 RAG:检索与后处理", "▎检索三通道:Embedding 向量 / BM25 关键词 / Hybrid 融合\n• Query Rewrite/Decomposition/澄清\n• Rerank:Cross-Encoder 或 LLM 重排\n• RRF 融合:多通道排名倒数融合(工程:HybridRetriever)\n• Citation:回答必须带 文件+行号,证据一致性校验", "实测:『鉴权链路』查询命中 auth 模块双通道融合第一名"),
        ("LLM Wiki 与知识治理", "▎为 LLM 优化的知识库\n• 知识分类:制度/产品/技术/调研/项目\n• 版本与时效:防止 Agent 用过期知识\n• 来源追踪:作者/时间/引用路径\n• 质量运营:清理重复/冲突/低质\n• 权限:不同角色可见范围不同", "评估四维:完整性/可信度/时效性/可检索性"),
        ("小结与 Lab4 验收", "▎验收清单\n① 三个典型问题回答均带文件+行号引用\n② 长文件压缩后 Token 消耗下降可量化\n③ 项目记忆注入后任务行为改善\n④ Context Debug Report 可输出\n▶ 下一章:从单打独斗到团队作战 —— Multi-Agent 与 Eval", None),
    ]),
    "5": ("Multi-Agent、Skill 与 Agent Eval", "协作架构与质量护城河 · 里程碑 M5", [
        ("本章定位与学习目标", "▎解决『复杂任务协作』与『证明 Agent 变好』\n• Multi-Agent 三模式与边界\n• Subagent 委托八要素\n• Skill 能力包\n• Eval:Agent 的核心护城河", "对应工程:multi_agent/ + eval/"),
        ("Multi-Agent:先问要不要", "▎单 Agent 适用:目标明确/步骤短/上下文集中\n▎Multi-Agent 适用:多视角任务(代码审查/研究/安全扫描)\n• Supervisor:主控拆解调度决策\n• Planner/Executor:计划与执行分离\n• Reviewer:复核降幻觉\n• 隔离:上下文/工具/权限三隔离;预算与超时控制", "实测:慢 Worker 被超时隔离,不拖垮整体(0.2s 熔断)"),
        ("Subagent 委托八要素", "▎任务目标 / 输入上下文 / 可调用工具 / 权限边界\n▎预期输出 / 输出格式 / 超时限制 / 评价标准\n• 默认只读,写操作单独授权\n• 聚合:证据合并/去重排序/结论汇总\n• 冲突仲裁:同判断面(aspect)分歧才叫冲突,按证据数量仲裁", "实测:两 Worker 结论冲突 → 证据多者胜出并留仲裁记录"),
        ("Skill 系统", "▎把方法论封装成可复用能力包\n• 定义:输入/步骤/工具依赖/质量标准\n• 生命周期:注册/检索/匹配/执行/评估/版本/下线\n• 版本升级必须递增(工程强制)\n• 编排:顺序/并行/条件分支/人工确认", "工程:SkillRegistry 2-gram 场景匹配;版本倒退直接 ValueError"),
        ("为什么 Eval 是护城河", "▎能运行 ≠ 可靠,Demo 成功 ≠ 真实任务成功\n• 改 Prompt 可能旧任务退化\n• 换模型可能工具调用行为漂移\n• RAG 策略变化可能引用准确率下降\n• 没有数据,一切『变好』都是感觉", "Eval 是唯一能用数据证明迭代有效性的手段"),
        ("Eval 指标与方法", "▎14 项指标核心六项:\nTask Success Rate / Tool Call Accuracy / Answer Correctness\nCitation Accuracy / Hallucination Rate / Failure Recovery Rate\n▎方法:Rule-based / Schema / Snapshot / Golden Answer\nLLM-as-Judge(何时不可靠)/ Human Eval / Pairwise / 回归", "工程:EvalRunner + KeywordJudge 基线,LLM Judge 同协议接入"),
        ("Trace Analysis 失败诊断", "▎13 类失败归因四步定位\n① Prompt 问题(指令不清/约束冲突)\n② 上下文问题(缺失/污染)\n③ 工具问题(选错/参数错/权限/超时)\n④ 模型问题(能力不足/幻觉)\n• 失败样本聚类 → 修复优先级", "数据驱动迭代:每次改动跑回归 → improved/regressed 双清单"),
        ("小结与 Lab5 验收", "▎验收清单\n① 六角色 Agent 产出可维护性分析报告\n② Golden Dataset ≥20 题\n③ 一次 Prompt 改动的回归对比报告\n④ 失败样本聚类分析\n▶ 下一章:上线 —— 生产化与可观测性", None),
    ]),
    "6": ("工程化、生产部署与可观测性", "可部署/可监控/可灰度/可回滚/可治理 · 里程碑 M6", [
        ("本章定位与学习目标", "▎从『项目能跑』到『系统可运营』\n• 模型服务与推理部署选型\n• 性能与成本优化(四级缓存)\n• 可观测性三支柱\n• 版本/灰度/回滚体系", "对应工程:governance/ + docker-compose"),
        ("模型服务与推理部署", "▎云 API / 私有化 / 混合的权衡:能力·敏感·成本·延迟·合规\n• vLLM:PagedAttention + Continuous Batching(高吞吐首选)\n• TGI:部署简·流式好\n• Triton:多模型 GPU 编排\n• 全部提供 OpenAI Compatible API → 网关层零改动切换", "平台 Provider 抽象的意义:换引擎不动业务代码"),
        ("性能与成本优化", "▎四级缓存体系(本平台 ADR-006)\nL1 进程内 LRU(工具目录/模板)\nL2 Redis(状态/热点)\nL3 LLM 语义缓存(精确 hash + 向量语义)\nL4 Tool Result Cache\n▎批处理:Embedding/Rerank/Eval 批量化\n▎路由降级:小模型优先,缓存优先,人工兜底", "读写分离:报表/Trace 查询走 PG 从库,读己之写回主库"),
        ("可观测性:日志/Trace/Replay", "▎三类日志:模型调用/工具调用/Agent 运行\n• Span 树 → TraceRecord(failed span 即 unhealthy)\n• Replay:保存输入+输出+状态,回放=真实重执行验证修复\n• 指标四族:业务(成功率/接管率)/模型(P95/成本)/Agent(工具准确率)/安全(拦截率)", "实测:Replay 对同一输入重执行并比对输出一致性"),
        ("监控与告警", "▎告警触发线\n• 模型失败率/工具失败率升高\n• 成本异常 / 延迟 P95 异常\n• 越权拦截率异常 / 人工接管率异常\n• SLO 视角:任务成功率是北极星指标", "Runbook 里每条告警必须对应处置动作"),
        ("版本/灰度/回滚", "▎六类版本对象:模型/Prompt/工具/Skill/RAG 策略/知识库\n• Feature Flag 控制一切切换\n• 灰度:按用户/部门/任务类型/风险等级\n• 一致性哈希百分比灰度(工程:FeatureFlags,同用户结果稳定)\n• 回滚:Flag 一键回退 + 镜像回退", "实测:50% 灰度 1000 用户命中 400-600 区间,同用户判定恒定"),
        ("MCP 生产化与平台封装", "▎MCP Server 生产六件事\n部署/鉴权/网络隔离/白名单/日志审计/密钥管理\n▎平台封装三级\nSDK(内部库)/服务化(模型·工具·评测服务)/治理(限流·审计·成本分摊·质量门禁)", "Compose 拓扑:PG 主从+Redis+Pulsar+Milvus 已在仓库落地"),
        ("小结与 Lab6 验收", "▎验收清单\n① Feature Flag 完成 Prompt 灰度并按指标回滚\n② Trace 复现一次失败并 Replay 定位\n③ 成本报表按模型/工具分摊\n④ Runbook 演练:一条告警一条处置\n▶ 下一章:综合实战 —— 企业级项目与产品化", None),
    ]),
    "7": ("企业级综合项目与产品化落地", "DeerFlow 解析 · 深度研究 · 软件工厂 · 里程碑 M7", [
        ("本章定位与学习目标", "▎把前六章能力转化为可交付的业务成果\n• DeerFlow 九条架构线解析\n• 高阶案例:深度研究平台\n• 高阶案例:新一代软件工厂\n• Agent 产品化方法论与面试表达", "产物:Capstone 三选一 + 作品集叙事"),
        ("DeerFlow 架构线 1-3", "▎① 请求入口:用户输入如何被托管成可观察可控制的 run\n▎② 主智能体工厂:运行时配置 → 可运行的智能体图\n▎③ 工具组装:注册了 ≠ 本次能用(按任务动态装配)", "对照本平台:AgentRun 托管 / AgentLoop 装配 / Registry 动态发现"),
        ("DeerFlow 架构线 4-6", "▎④ 中间件管道 I:模型调用前的上下文准备\n▎⑤ 中间件管道 II:输出裁决/门控/清理\n▎⑥ 沙箱系统:本地与容器不是同一边界", "对照本平台:ContextWindow.fit / 结构化校验反喂 / LocalSandbox"),
        ("DeerFlow 架构线 7-9", "▎⑦ 子代理系统:受限的完整代理执行子任务\n▎⑧ 技能系统:经验 → 可安装可审查可复用的能力\n▎⑨ 持久化:什么可恢复/可查询/可审计", "对照本平台:SubagentTask 委托 / SkillRegistry / Checkpoint+AuditBus"),
        ("高阶案例一:企业级深度研究平台", "▎自动完成:资料搜集→交叉验证→结构化分析→报告生成\n• Skill 沉淀方法论:竞品分析/行业调研/投资尽调\n• Tool 接入:搜索/行业库/专利/Wiki/专家图谱\n• 证据链:来源/引用/工具调用/Trace 全程可审计\n• 产出:Markdown/HTML/交互文档\n• 价值:数天 → 数小时", "七步实施路径详见讲义(场景→Skill→Tool→工作流→证据链→输出→优化)"),
        ("高阶案例二:新一代软件工厂", "▎端到端流水线:需求分析→任务拆解→开发→审查→测试→CI\n• GitHub Channel:分支/提交/PR/CI 集成\n• 角色化 Agent:PM/架构师/开发/QA\n• ACP 本地工具:构建/环境/命令执行\n• 全程可追溯:需求/变更/测试/PR/Trace", "本质:第 3 章 Codebase Agent 的多角色工业化升级"),
        ("Agent 产品化:边界与拆解", "▎适合:检索/文档/研究/代码/客服/流程自动化\n▎不适合:强确定性/零容错/规则明确可脚本/不允许人审的决策\n• 边界判断:Chatbot/RAG/Workflow/Agent/脚本五选一\n• 业务拆解七步:SOP→Loop / 岗位→Tool / 知识→RAG / 经验→Skill / 风险→HITL / 失败→回滚 / 目标→Eval", "过度 Agent 化是最大的反模式"),
        ("作品集与面试表达 + Capstone", "▎平台写进简历的正确姿势\n• Tool Runtime:讲治理/权限/审计(不是『我调了 API』)\n• Codebase Agent:讲长程任务/失败恢复\n• RAG:讲引用准确率与压缩收益(带数字)\n• Eval:讲回归如何拦住一次退化\n▎Capstone 三选一:深度研究 MVP / 软件工厂 MVP / 自选业务 Agent\n▎结课:用数据讲业务价值", None),
    ]),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for no, (title, subtitle, pages) in CHAPTERS.items():
        build(no, title, subtitle, pages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
