# ADR-004:API 风格 —— GraphQL BFF + REST/SSE 流式端点

- 状态:Accepted(依据负责人原始要求:"采用读写分离、GraphQL、Pulsar MQ、多级缓存")
- 日期:2026-10-01

## 决策
- 对外统一查询面:**GraphQL**(strawberry-graphql + FastAPI),覆盖任务/Trace/Eval 报告/工具目录/成本报表等聚合查询场景——一图多端、按需取字段、避免 REST N+1;
- 流式与事件:SSE(`/v1/chat/stream`)与 Webhook 保留 REST 端点(GraphQL SSE 协议作为第 6 章选学进阶);
- 服务间内部调用:进程内直调(单体内模块化,按 DDD 限界上下文划界),预留拆分接缝。

## 理由
- Agent 平台的消费端(控制台/CLI/报表)查询形态天然多样,GraphQL 收敛 BFF 层;
- 流式 LLM 响应在 SSE 上语义最直白,浏览器兼容性最好。

## 后果
- 需维护 GraphQL schema 与 Pydantic 模型的映射层(strawberry 原生集成 Pydantic 可控);
- 缓存策略:GraphQL 查询缓存不做(教学聚焦),数据层缓存走四级缓存体系。
