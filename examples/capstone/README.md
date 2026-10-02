# Capstone 三案例(Capstone 项目骨架)

> 对应课程第 7 章;三选一答辩。**答辩要求:用数据说话**——任务成功率 / 单任务成本 / P95 延迟,
> 对照 Eval 报告讲解一次迭代决策(improved/regressed 双清单)。

| 案例 | 定位 | 核心复用组件 | 运行 |
|---|---|---|---|
| [deep_research/](deep_research/) | 企业级深度研究平台 MVP:搜集→交叉验证→结构化→报告 | SkillRegistry / HybridRetriever / SupervisorAgent | `python -m examples.capstone.deep_research.research`(或照 tests 调用) |
| [software_factory/](software_factory/) | 新一代软件工厂 MVP:PM→架构→开发→QA 流水线 | SubagentTask / AgentLoop / ToolExecutor / EvalRunner | `await run("订单服务")` |
| [custom_agent/](custom_agent/) | 自选业务 Agent 模板:业务拆解七步填空 | 全组件自由组合 | `build_agent_plan(it_worksheet())` |

每个案例:README(架构蓝图+七步路径+验收标准)+ 可运行最小 demo + 单元测试
(`tests/unit/capstone/test_capstone.py`,10 例,CI 同款门禁)。
