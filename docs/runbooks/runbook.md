# 上线 Runbook(v1.0 · M6 演练用)

> 纪律:**每条告警必须有唯一处置动作**;任何变更先想回滚路径。

## 1. 部署

```bash
make setup && make infra && make test && make dev   # 标准4步
docker compose -f docker-compose.infra.yml ps        # 全部 healthy 才继续
```

## 2. 健康检查

| 检查 | 命令 | 期望 |
|---|---|---|
| API | `curl :8000/healthz` | status=ok |
| PG 主 | `docker exec ap-pg-primary pg_isready -U agent` | accepting |
| PG 从(复制) | `docker exec ap-pg-replica psql -U agent -tAc "SELECT pg_is_in_recovery()"` | t |
| Redis | `docker exec ap-redis redis-cli ping` | PONG |
| Pulsar | `curl -sf :8080/admin/v2/brokers/health` | ok |

## 3. 告警 → 处置

| 告警 | 处置 |
|---|---|
| 模型失败率升高 | 查 router.attempts;主模型故障→确认 fallback 生效;全挂→FeatureFlag 切备用 Provider |
| 工具失败率升高 | 审计总线按 tool 聚合;高危异常工具 `registry.disable()` 热下线 |
| 成本异常 | CostLedger.report() 按 model 定位;开小模型优先路由;检查语义缓存命中率 |
| 延迟 P95 异常 | Trace 找最慢 span;区分模型延迟/工具超时/检索 |
| 越权拦截率异常 | 安全事件:核对 ToolContext.role 配置;必要时只读模式(role=readonly 全局) |
| 人工接管率异常 | 用户体验问题:检查 waiting_approval 是否过频,收紧高危判定 |

## 4. 回滚

- Prompt/模型/RAG 策略:FeatureFlag 关闭即回(秒级)
- 服务镜像:`git checkout <tag> && 重启`(tag 见下)
- 数据:PG 从库为准做应急快照;禁止跨大版本混部

## 5. 里程碑标签

`m0` 环境 / `m1` Gateway / `m2` Tool Runtime / `m3` Loop+Sandbox /
`m4` Context+RAG / `m5` MultiAgent+Eval / `m6` Governance+生产化

## 6. 值班交接三问

① 当前灰度开关状态?② 最近一次回归 improved/regressed?③ 有无未处置告警?
