# Spec · 阶段五(M5):Multi-Agent、Skill 与 Agent Eval

> 对应课程第 5 章;实现:`src/agent_platform/multi_agent/` + `src/agent_platform/eval/`

## 1. 目标(In Scope)
Supervisor 并行委托与结果聚合、同判断面冲突仲裁、Skill 能力包生命周期、
Golden Dataset 评测、核心指标、回归对比。

## 2. 接口契约
- `SubagentTask` 委托八要素:goal / aspect(判断面) / input_context / allowed_tools /
  permission(默认 readonly) / expected_output / output_format / timeout_s / quality_bar
- `Worker` 协议(name + async run(task)->WorkerResult);`WorkerResult(worker,conclusion,evidence,risk,error)`
- `SupervisorAgent.run(goal,tasks,workers) -> SupervisorReport`:
  - `asyncio.gather` 并行;单 Worker `wait_for(min(task.timeout, worker_timeout))` 超时隔离(→ error 记录,不拖垮整体)
  - 冲突:仅**同一 aspect** 内多结论分歧才记 `Conflict`;仲裁按证据数量(教学规则,生产可人工介入)
- `SkillDef(name,scenario,steps,version,quality_bar)`;`SkillRegistry`:
  - 场景匹配:任务与场景 2-gram 重叠数最大者胜(阈值 2)
  - 版本管理:同名重注册必须版本递增,否则 ValueError
- `GoldenCase(case_id,input,expected_keywords,expected_tools)`;`AgentAnswer(text,tools_used,latency_ms,tokens)`
- `Judge` 协议(`KeywordJudge`:全部期望关键词命中);`EvalRunner.run(cases,agent_fn) -> EvalReport`
  指标:`task_success_rate` / `tool_call_accuracy`;`EvalRunner.regression(old,new) -> RegressionDelta(improved,regressed)`

## 3. 验收标准
- [x] AC1 并行委托与聚合:`test_parallel_delegation_and_aggregation`
- [x] AC2 同判断面冲突+证据仲裁:`test_conflict_detected_and_arbitrated`(不同 aspect 不误报冲突)
- [x] AC3 超时隔离:`test_timeout_worker_isolated_not_blocking`(快 Worker 结论完好)
- [x] AC4 Skill 匹配与版本递增:`TestSkillRegistry` 2 例
- [x] AC5 成功率/工具准确率:`test_success_rate_and_tool_accuracy`
- [x] AC6 回归双清单:`test_regression_comparison`(improved/regressed)
- [ ] AC7 LLM-as-Judge(同 Judge 协议接入;依赖真实模型,单测用 MockJudge)
- [ ] AC8 六角色 Worker 实装(Architecture/Test/Security/Performance/Docs/Report;第 5 章实验课)
- [ ] AC9 失败样本聚类(Trace Analysis 联动;第 5 章实验课)

## 4. Out of Scope
子 Agent 上下文隔离的进程级实现(教学进程内隔离);A/B 平台化(第 6 章 Feature Flag 联动)。
