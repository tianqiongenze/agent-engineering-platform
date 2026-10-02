# Spec · 阶段六(M6):可观测性与治理(Production Ready)

> 对应课程第 6 章;实现:`src/agent_platform/governance/` + 基础设施 Compose

## 1. 目标(In Scope)
Trace Span 树、失败任务 Replay、一致性哈希灰度 Feature Flag、成本账本;
生产化接线:Pulsar 审计总线、PG 持久化(读写分离)、版本对象与回滚 Runbook。

## 2. 接口契约
- `TraceCollector.span(name,parent)`(context manager,异常自动 set_ok(False));
  `build() -> TraceRecord(trace_id,spans)`;`TraceRecord.healthy = all(span.ok)`
  `Span(duration_ms 派生, meta, ok/error)`
- `ReplayStore.record(prompt,output)` / `recordings()` / `replay(prompt,fn)`:
  回放=同一输入真实重执行(修复验证),非缓存回放
- `FeatureFlags.set(key,enabled,rollout_percent)` / `is_enabled(key,user_id)`:
  sha256(key:user) 前 8 位 % 1000 < percent×10 —— 同用户判定恒定(一致性哈希)
- `CostLedger(pricing:{model:元/千token})`:record(model,prompt_tokens,completion_tokens);
  `report()` 按 model 计价,含 `_total` 与 `_unpriced_models`(未定价模型显式暴露)
- 基础设施:docker-compose.infra.yml —— PG16 主从流复制(读走 replica,读己之写回 primary)、
  Redis7 AOF、Pulsar4 standalone、Milvus2.5(etcd+minio);`scripts/wait-for-infra.sh` 就绪聚合

## 3. 验收标准
- [x] AC1 Span 树与失败标记:`test_span_tree_and_total_latency` / `test_failed_span_marks_trace_unhealthy`
- [x] AC2 Replay 重执行一致性:`test_replay_reproduces_identical_result`
- [x] AC3 灰度一致性与比例区间:`TestFeatureFlags` 3 例(同用户恒定;1000 用户 40%~60%)
- [x] AC4 成本账本与未定价暴露:`TestCostLedger` 2 例
- [x] AC5 Pulsar 审计适配器降级:`test_pulsar_audit.py`(published/dropped 计数)
- [x] AC6 OpenAICompatibleProvider 真实接入:`test_openai_provider.py`(MockTransport 7 例;`build_provider` 工厂 env 切换)
- [ ] AC7 六类版本对象持久化(模型/Prompt/工具/Skill/RAG 策略/知识库;PG 表 + Alembic 迁移)
- [ ] AC8 Prometheus /metrics 与四族指标(业务/模型/Agent/安全;integration profile)
- [ ] AC9 真实 Pulsar 收发与 DLQ(integration profile;`docker compose -f docker-compose.infra.yml up`)

## 4. Out of Scope
多区域/异地多活(架构文档愿景);成本报表 UI;Runbook 告警系统对接(Prometheus Alertmanager 演示)。
