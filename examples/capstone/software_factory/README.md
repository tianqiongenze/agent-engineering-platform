# Capstone B · 新一代软件工厂 MVP

**定位一句话**:端到端自动化开发流水线——需求分析、任务拆解、代码开发、
代码审查、测试验收,软件交付从手工流程升级为智能工厂。

对应课程:第 7 章讲 7-2(高阶案例二)。

## 架构蓝图

```
需求 spec ─▶ PM Agent(拆任务,委托八要素)
         ─▶ 架构师 Agent(SkillRegistry 匹配 layered-architecture 技能)
         ─▶ 开发 Agent(AgentLoop:拆解→scaffold_module→变更说明)
         ─▶ QA Agent(EvalRunner+GoldenCase 验收,通过率 100% 方可 done)
全程可追溯:PipelineStep 記錄各角色输出;审计走 InMemoryAuditBus(可换 PulsarAuditBus)
```

## GitHub Channel / ACP 集成点(生产化扩展)

- GitHub Channel:分支创建/代码提交/PR 发起/CI 检查回调(替换 `_dev_loop` 的本地执行)
- ACP 本地工具:本地构建/环境配置/测试命令接入(替换 scaffold_module 演示工具)

## 七步实施路径

① 明确场景(需求分析/功能开发/Bug修复/代码审查/测试生成/CI)→ ② 定义多角色 Agent
(PM/架构师/开发/QA 职责表)→ ③ 接入 GitHub Channel → ④ 构建自动化工作流 →
⑤ 集成 ACP 本地工具 → ⑥ 流程追踪(需求/变更/测试/PR/Trace)→ ⑦ 优化交付效率与质量。

## 验收标准

- [ ] 四步流水线全部 done,QA 通过率 100%
- [ ] 变更说明含"模块"与"测试"关键词(结构化产物)
- [ ] 架构技能按场景匹配命中
- [ ] 扩展:接入真实 GitHub 仓库完成一次 分支→PR→CI 闭环(答辩加分)
