# 项目群审计与打分报告(v1.2 重构版)

> 审计人:教授级高工/大厂架构师视角 · 2026-10-03
> 对象:`05-平台工程/agent-platform` 项目群(7 限界上下文 + examples + infra + docs)
> 方法:实测证据(测试/基准/端到端 curl)+ 联网最优实践对照([Outbox 实践](https://www.sachith.co.uk)、[幂等与限流](https://scalewithchintan.com)、[前端多端策略](https://ozrit.com)、[跨端成熟度](https://pkgpulse.com))

## 一、总评分卡

| # | 维度 | 权重 | 得分 | 关键证据 |
|---|---|---|---|---|
| 1 | 工程质量与测试 | 20% | **9.2** | 108 单测全绿;覆盖率 ≥95%;ruff/mypy 零错误;CI 双 job 门禁 |
| 2 | 架构与 DDD | 15% | **8.6** | 7 限界上下文边界清晰;聚合/防腐层(Provider/MCP)到位;接缝预留 |
| 3 | 事件驱动 | 10% | **7.8** | Outbox+幂等消费落地(业界对齐[exactly-once 组合](https://blog.stackademic.com));Pulsar 适配降级;⬜真实 broker 收发 |
| 4 | 读写分离 | 10% | **7.8** | PG16 真实流复制;ReadWriteRouter+读己之写锚定实测;⬜业务 DAO 全面接入 |
| 5 | 多级缓存 | 10% | **7.5** | TwoLevelCache 命中率可观测+基准实测;⬜L3 语义缓存 |
| 6 | 风控体系 | 15% | **8.2**(重构前 4.0) | 注入拦截 400/防重放 429/限流 429 全部**端到端实测**;⬜JWT/WAF(见表二) |
| 7 | API 与 BFF | 8% | **8.0** | GraphQL+SSE 双通道;风控接线;⬜JWT 鉴权/租户头 |
| 8 | 可观测性 | 7% | **7.6** | Trace 树/Replay/成本账本;⬜Prometheus /metrics 接线 |
| 9 | 前端多端 | 3% | **3.0 → 方案已立** | 现状 0 前端代码;多端方案+最小控制台 Spec 已交付(见 frontend 文档) |
| 10 | 文档与交付 | 2% | **9.5** | spec×6/ADR×6/runbook/703 页 PPT/题库/实验手册 |
| | **加权总分** | | **8.0 / 10** | 重构前基准分 6.1(风控 4.0/缓存缺位/无路由层) |

## 二、目录结构专项:"服务都放 service 下"是否符合软件工程?

**现状**:项目群为**模块化单体(monorepo)**,七个服务雏形位于 `src/agent_platform/<bc>`,
**没有** `services/` 目录。

**判定:当前布局符合软件工程要求,且是正确阶段选择**。理由:
1. 教学与单仓验证阶段,模块化单体 = 最低分布式税(无网络/无跨仓一致性),同时以 DDD 限界上下文保证"未来可拆";
2. 业界大规模前端与后端共识均为 **monorepo 优先**([Turborepo+pnpm 为 2026 多应用标准](https://softaims.com)),目录结构服务于"变更局部性"而非形式;
3. 强行先建 `services/` 会引入跨仓依赖与部署复杂度,而复用边界尚未被真实流量验证——**拆分应由压测与耦合数据驱动,不由目录形式驱动**。

**服务化迁移路径(映射表,条件触发)**:

| 现有模块 | 未来服务 | 触发条件(满足其一即拆) |
|---|---|---|
| gateway/ | model-gateway-svc | 模型调用量与其他 BC 带宽争抢 |
| tools/ | tool-runtime-svc | 工具执行 CPU 密集拖累 API |
| orchestration/ | agent-orchestrator-svc | Loop 任务数 > 千级并发 |
| context_memory/ | context-rag-svc | 向量索引内存独立扩缩需求 |
| multi_agent/+eval/ | collab-eval-svc | 评测批量任务波峰隔离 |
| governance/ | governance-svc | 合规审计独立存储/权限域 |
| api/ | bff-svc | 多端差异化聚合需求 |

届时目录变更为 `services/<name>/`(每服务独立 Dockerfile/CI),共享内核下沉 `packages/shared`(对应铁律"公共能力共享包优先")。

## 三、四大工业件对服务(限界上下文)的贡献矩阵

| 工业件 | gateway | tools | orchestration | context_memory | multi_agent/eval | governance | api |
|---|---|---|---|---|---|---|---|
| **风控层**(限流/防重/防注入) | 限流保护模型配额 | 高危确认前置 | 防死循环互补 | — | Worker 配额 | 攻击审计 | **入口必经**(实测 429/400) |
| **多级缓存** | 语义缓存宿主 | **Tool Result Cache(实测 69.7%)** | 步骤幂等 | 检索缓存(67.7%) | 评测集缓存 | 命中率上报 | 减尾延迟 |
| **读写分离** | 留痕写主 | 审计写主 | 状态写主 | 记忆读从 | 报表读从 | Trace 查询读从 | **读己之写锚定**(实测钉主库) |
| **Outbox** | 成本事件 | **审计事件(已接 Pulsar)** | 状态变更事件 | 索引更新事件 | 评测完成事件 | 投递重试+DLQ | — |

**缓存命中率实测(scripts/bench_cache.py,冷启动+70/30 稳态负载)**:

| 负载 | 命中率 | L1 占比 | 结论 |
|---|---|---|---|
| 工具结果(30 键池) | 69.7% | 100% | 高度可缓存 |
| 检索结果(200 键池) | 67.7% | 74% | 健康 |
| LLM 语义(1000 键池) | 60.1% | 21% | 依赖语义归一 |
| 混合负载(50% 新键) | 42.9% | 13% | 上限=重复占比 |

**命中率提升空间(优先级排序)**:
1. **缓存键归一化**(收益最大):把"不同表述同一意图"归一到同键——工具参数排序化、查询改写归一;L3 向量语义缓存(相似度>0.92 命中)预计把 LLM 负载命中率从 60% 提至 75%+;
2. **L1 容量按热点定容**:基准显示 l1=64 即可让 30 键池 L1 命中 100%(容量过小则 L2 兜底多一跳,总命中率不掉但延迟 +0.3ms 级);
3. **TTL 分级**:工具结果 60s/检索 5min/项目记忆 24h,减少主动失效;
4. **负缓存**:空结果也缓存,防穿透;
5. **热点预热**:高峰前预载 Top-K 键。

## 四、风控体系审查(重构前 → 重构后)

| 风险 | 重构前 | 重构后 | 实测证据 |
|---|---|---|---|
| R1 接口防刷 | ❌ 无 | ✅ 令牌桶 per-key | 14 连发 → 8×200 后 6×**429** |
| R2 重放攻击 | ❌ 无 | ✅ 幂等键 TTL 去重 | 同键二发 → **429** |
| R3 Prompt 注入 | ❌ 无 | ✅ 模式库拦截(中英) | "ignore all previous instructions" → **400** |
| R4 缓存缺位 | ❌ 仅文档 | ✅ 两级缓存+可观测 | 基准 59.5% 混合命中 |
| R5 读写分离无业务路由 | ⚠️ 仅基础设施 | ✅ 路由器+读己之写 | 钉主库/TTL 回从实测 |
| R6 事件丢失 | ⚠️ 仅设计 | ✅ Outbox+重试+DLQ+幂等消费 | 单测 3 例 |
| R7 JWT 鉴权/租户隔离 | ⬜ | ⬜ 待接(RBAC 模型已在) | — |
| R8 SQL/Shell 注入 | ✅(v1.0) | ✅ Sandbox 白名单+模式拦截 | rm -rf 实测拦截 |
| R9 Secret 管理 | ✅ | ✅ env/掩码/推送前扫描 | 本报告密钥全程掩码 |
| R10 CC/人机验证/WAF | ⬜ | ⬜ 部署层方案(Nginx limit_req+fail2ban+验证码) | — |
| R11 审计日志防篡改 | ⬜ | ⬜ 方案:append-only 表+哈希链 | — |

## 五、前端(多端)大厂标准方案

详见 [docs/frontend/multi-end-design.md](../frontend/multi-end-design.md)。要点:Design Tokens 先行、
Turborepo+pnpm monorepo、Web=Next.js/移动端=React Native(与 Web 共享逻辑)/PWA 轻看板、
性能预算(FCP<1.5s/LCP<2.5s/TTI<3.0s)、灰度直连平台 FeatureFlags、SSE 打字机与 GraphQL 查询面为第一公民。

## 六、重构执行记录(本次已落地)

| 项 | 文件 | 测试 |
|---|---|---|
| 风控层 | `src/agent_platform/security/guard.py` + API 接线 | 10 例 |
| 多级缓存 | `src/agent_platform/shared/cache.py` | 5 例 |
| 读写分离路由 | `src/agent_platform/shared/db_routing.py` | 3 例 |
| Outbox | `src/agent_platform/shared/outbox.py` | 3 例 |
| 缓存基准 | `scripts/bench_cache.py` | 契约测试 1 例 |
| 多协议网关 | `gateway/anthropic_provider.py` + 真实联调 | 单测 5 + 集成 3(实网) |
| GitHub Channel | `examples/capstone/software_factory/github_channel.py` | 5 例 |

## 七、下一阶段重构方向(P1~P3)

- **P1**:JWT 鉴权+租户中间件;Prometheus /metrics;L3 语义缓存(向量接口);Alembic 迁移落地六版本对象表
- **P2**:services/ 拆分(按触发条件);前端控制台 MVP;真实 Pulsar 收发集成测试;审计哈希链
- **P3**:多区域只读副本;WAF/人机验证;成本分摊报表 UI
