# Capstone C · 自选业务 Agent 模板

**定位一句话**:用第七章"业务拆解七步"方法论,把任意业务 SOP 填空式地转化为
可评审、可开发的 Agent 设计草案。

对应课程:第 7 章讲 7-3(产品化落地)。

## 七步拆解(模板核心)

| 业务要素 | 转化为 |
|---|---|
| 业务 SOP | Agent Loop 步骤 |
| 岗位任务 | Tool 清单 |
| 知识资产 | RAG 来源 |
| 经验方法论 | Skill |
| 风险节点 | Human-in-the-loop |
| 失败场景 | 回滚方案 |
| 业务目标 | Eval 指标 |

## 内置样板:IT 工单处理 Agent

`it_worksheet()` 返回完整填好的示例:接收工单→分类分级→检索知识库→生成方案→
高危确认(restart_service)→执行回访;工具含 search_kb/query_cmdb/reset_password/restart_service;
回滚含变更回滚脚本与退回人工队列。

## 使用方式

1. 参照 `it_worksheet()` 逐格填写你的业务(必须先有 SOP——没有 SOP 就没有 Loop);
2. `build_agent_plan(ws)` 生成设计草案(loop/tools/rag/skills/hitl/rollback/eval 七键);
3. 评审后按平台组件逐项实现,并用 EvalRunner 建立该业务的 Golden Dataset。

## 验收标准

- [ ] SOP 与工具清单非空(入口校验)
- [ ] 设计草案七键齐备且非空
- [ ] 高危工具全部出现在 hitl 节点
- [ ] 答辩:用该业务的 Eval 数据讲一次迭代决策
