# ADR 索引与顶层决策记录

> 状态标记:Proposed(待项目负责人确认)/ Accepted / Superseded
> 规则:任何重大技术转向必须新增 ADR 并标注 Supersedes 关系(架构文档单一事实源铁律)

## ADR 列表

| ADR | 主题 | 状态 |
|---|---|---|
| [ADR-001](ADR-001-course-scope-and-delivery.md) | 课程规模 64 课时、成套交付节奏 | **Proposed(默认值推进,待确认)** |
| [ADR-002](ADR-002-llm-provider-strategy.md) | LLM Provider:Mock 优先 + 可插拔真实 API | **Proposed(默认值推进,待确认)** |
| [ADR-003](ADR-003-industrial-stack.md) | Pulsar/PG 主从/Milvus/Redis 全真实容器落地 | **Proposed(默认值推进,待确认)** |
| [ADR-004](ADR-004-api-style-graphql-bff.md) | 对外 GraphQL BFF + 流式保留 REST/SSE | Accepted(依据负责人原始要求) |
| ADR-005 | Python 3.12 项目锁定(而非系统 3.14) | Accepted(pulsar-client 等二进制依赖兼容性) |
| ADR-006 | 多级缓存分层:L1 进程/L2 Redis/L3 语义/Tool Result | Accepted |

## 决策点与回退成本

| 决策 | 若负责人改选 | 回退成本 |
|---|---|---|
| D1=64 课时 | 96/48 课时 | 低:重排授课计划表格,讲次内容复用 |
| D2=Mock 优先 | 真实 API 优先 | 低:改 `.env` 即切,代码零改动(Provider 抽象) |
| D3=全真实落地 | 轻量抽象 | 中:Compose 基础设施保留为"生产拓扑演示",运行时换适配器 |
| D4=成套交付 | 工程/课件先行 | 低:已产出物全部复用,仅调整后续批次顺序 |
