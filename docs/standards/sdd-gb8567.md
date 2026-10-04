# 概要设计 + 详细设计说明书(SDD)· GB/T 8567 结构

> Agent Engineering Platform v1.3 · 2026-10-04 · 与 ADR/审计报告构成设计三件套

## 1 引言
目的:把 SRS 需求映射为可实现的软件结构(概要)与模块规格(详细)。范围:七大 BC+API+基础设施。参考:GB/T 8567-2006、TOGAF 视图。

## 2 总体设计
### 2.1 需求映射(概要)
FR-1→gateway;FR-2→tools;FR-3→orchestration;FR-4→context_memory;FR-5/6→multi_agent+eval;FR-7→governance+security+observability;横切→shared+api。
### 2.2 设计原则(架构原则,TOGAF 对齐)
P1 意图与执行分离(模型不执行) P2 防腐层优先(Provider/MCP) P3 一切皆版本 P4 默认拒绝+最小权限 P5 事件同事务(Outbox) P6 读写分离+读己之写 P7 缓存键归一优先于扩容 P8 可观测一等公民(metrics+trace+留痕)。
### 2.3 运行设计
单进程组合(教学)/多副本(生产);请求路径:WAF→API(风控四步)→BC 调用→基础设施;事件路径:BC→Outbox→Pulsar→幂等消费。

## 3 系统结构(概要)
### 3.1 逻辑结构(限界上下文)
七 BC + shared/security/observability + api;依赖方向:api→BC→shared;BC 间经领域事件,禁止横向 import(防腐)。
### 3.2 部署结构
compose:pg-primary/replica、redis、pulsar、milvus、api×N;边缘 WAF(nginx 模板)。
### 3.3 接口设计(内部)
LLMProvider 协议(complete/stream_events);AuditBus 协议;KVStore 协议;Worker 协议;Judge 协议 —— 全部可替换实现。

## 4 模块详细设计(详细)
| 模块 | 关键类/函数 | 算法/要点 | 测试 |
|---|---|---|---|
| gateway.domain | Usage(派生 total)/ChatRequest | 不变量入校验器 | 12+ |
| gateway.router | ModelRouter.complete | 链式 fallback+attempts | 3 |
| gateway.openai/anthropic | complete/stream_events | SSE 解析/错误归一 | 12+3(实网) |
| tools.runtime | ToolExecutor.execute | 权限→校验→wait_for→审计;mask_args | 10 |
| tools.pulsar_audit | PulsarAuditBus | 懒加载/降级计数/异步安全投递 | 3+1 |
| orchestration.loop | AgentLoop.run | 4 出口+签名熔断+深拷贝存档 | 12 |
| orchestration.sandbox | check_* | realpath 归一+白名单+危险模式 | 5 |
| context_memory.* | compress/fit/memory/rag | 头尾保留/装箱/RRF K=60 | 16 |
| multi_agent.supervisor | run | gather+wait_for+aspect 仲裁 | 6 |
| eval.evaluator | EvalRunner.regression | improved/regressed 双清单 | 6 |
| governance.* | Trace/Replay/Flags/Cost | Span 树/sha256 桶/千 token 计价 | 8 |
| security.* | SecurityStack/JwtCodec/ChainedAuditBus | 注入→重放→限流;HS256;哈希链 | 20 |
| shared.* | TwoLevelCache/SemanticCache/Router/Outbox/DAO | LRU+TTL/τ=0.92/锚定/DLQ | 20 |

## 5 接口与数据设计
持久化九类对象(见 SRS §3.4);事件主题 tool-audit;缓存键规范:llm:sha256(normalize)/tool:{name}:{sorted args}。

## 6 需求追踪矩阵(样例)
FR-1→spec1 AC2-4→tests/unit/gateway→src/gateway/*;FR-3→spec3 AC1-7→tests/unit/orchestration→orchestration/*;FR-7 风控→v1.3→tests/unit/test_v13_modules→security/*。全量矩阵由 CI 覆盖率报告佐证(93%)。

## 7 出错处理设计
分层错误:ProviderError/ValidationFailedError/PermissionDeniedError/RateLimitExceeded/ReplayDetected/InjectionDetected/AuthError/SandboxViolation —— 全部结构化、可审计、不裸抛。

## 8 维护设计
ADR 治理变更;版本六对象;metrics+Trace 定位;Runbook 处置;评测回归防退化。
