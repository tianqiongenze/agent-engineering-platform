# 部署手册 · GB/T 8567 结构(含安装/升级/回滚)

> Agent Engineering Platform v1.3 · 2026-10-04

## 1 系统概述与用途
单机 Docker Compose 验证拓扑;多节点同构可移植(替换 host 即可)。用途:教学演示/生产原型/二次开发基座。

## 2 运行环境要求
| 项 | 要求 |
|---|---|
| OS | macOS 14+/Linux(arm64/amd64) |
| Docker | ≥29 + Compose v5(镜像源可达) |
| Python | 3.12(uv 自动管理) |
| 资源 | ≥16GB RAM;磁盘 ≥20GB |
| 网络 | LLM 端点(云 API/内网 vLLM);GitHub(推送,可选) |

## 3 安装与部署(标准四步)
```bash
make setup   # uv sync(Python 3.12)
make infra   # compose 起 PG 主从/Redis/Pulsar/Milvus(健康等待)
make test    # 125 单测门禁
make dev     # uvicorn :8000(控制台 / + /graphql + /metrics)
```
镜像受限环境:compose 已显式使用 `docker.1ms.run/library/postgres:16-alpine` 与本地 `apachepulsar/pulsar:3.3.0`(禁止对官方 tag 做隐式 retag)。

## 4 配置说明(.env)
LLM_PROVIDER=mock|openai_compatible;OPENAI_BASE_URL/KEY;PG_PRIMARY/REPLICA_DSN;REDIS_URL;PULSAR_URL;SEC_JWT_REQUIRED/SECRET;SEC_RATE_CAPACITY/REFILL;METRICS_PROTECTED。生产化:密钥走 KMS/配置中心,禁 .env 明文。

## 5 启动验证(五步健康)
healthz / PG 主从(pg_is_in_recovery=t)/ Redis ping / Pulsar brokers health / Milvus healthz → scripts/wait-for-infra.sh。

## 6 升级
1) `git pull` 2) `uv sync` 3) Alembic(引入后)或 compose 重建 4) 灰度:FeatureFlag 10%→100% 5) 观察指标 24h。

## 7 回滚
Flag 秒级(Prompt/模型/策略);镜像 `git checkout <tag>` 重部署;知识库快照恢复;数据卷变更前必须备份(backup→操作→verify)。

## 8 故障处置(摘要,全文见 runbook.md)
模型失败率高→查 router.attempts;工具失败→registry.disable 热下线;成本异常→CostLedger 定位;越权异常→readonly 模式。

## 9 安全事项
密钥永不入库;审计脱敏+哈希链;WAF 边缘(nginx 模板);租户 JWT 强制(生产 SEC_JWT_REQUIRED=1);/metrics 网络隔离或鉴权。
