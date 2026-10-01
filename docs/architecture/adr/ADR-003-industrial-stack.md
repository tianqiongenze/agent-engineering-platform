# ADR-003:工业级组件全真实落地

- 状态:**Proposed(默认值推进,待负责人确认 D3)**
- 日期:2026-10-01

## 决策
Compose 基础设施按生产形态部署:
- **PostgreSQL 16 主从流复制**(读写分离,从库真 `pg_is_in_recovery`);
- **Pulsar 4 standalone**(领域事件/审计/Outbox/DLQ 真实收发);
- **Milvus 2.5 standalone**(向量检索真实建集合);
- **Redis 7 AOF**(L2 缓存/限流)。

## 理由
- 课程差异化核心:学员在单机即可触摸生产拓扑,而非"接口抽象+内存假实现";
- 开发机 32GB 实测可承载(峰值约 6-8GB);
- 与负责人"按工业级标准构建"的长期要求一致。

## 后果
- 环境启动变重(~1-2 分钟);集成测试依赖 docker;
- 教学轻量路径保留:`LLM_PROVIDER=mock` + `pytest -m unit` 无需任何容器。

## 风险与缓解
- Pulsar 镜像架构差异(arm64):apachepulsar 官方多架构镜像已覆盖 arm64;
- Milvus 组件多(etcd/minio):已按官方 standalone 最小拓扑编排。
