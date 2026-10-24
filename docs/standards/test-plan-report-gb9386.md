# 测试计划与测试报告 · GB/T 9386 结构

> Agent Engineering Platform v1.3 · 2026-10-04

## 1 测试计划
### 1.1 测试范围与策略
- **单元测试**(pytest -m unit):7 BC+shared/security/observability 全模块;Mock 隔离外部;门禁 125 通过、覆盖率 ≥80%(实测 93%)。
- **集成测试**(-m integration):真实基础设施 —— GLM 双协议实网(AC6)、Pulsar 收发、PG 主从读写分离;5 用例。
- **端到端安全测试**:curl 实测注入 400/重放 429/限流 429/JWT 401。
- **性能基准**:bench_cache(命中率)、联调延迟(TTFT/总延迟)、成本账本。
- **回归门禁**:CI 双 job(quality+integration);regressed 非空阻断合并。
### 1.2 环境
macOS(docker 29)/Python 3.12/uv;基础设施:PG16 主从、Redis7、Pulsar 3.3、Milvus2.5(镜像源 docker.1ms.run)。
### 1.3 通过准则
单元:0 失败且覆盖达标;集成:全部通过(健康等待内);安全:拦截率 100%;基准:语义层命中率 > 仅精确。
### 1.4 暂缓项
WAF 实机部署演练、Grafana 对接、多区域(见审计 P2/P3)。

## 2 测试报告(2026-10-04 执行)
### 2.1 单元测试
**结果:126 passed / 0 failed;覆盖率 91%(v1.5 实测基线)**;ruff All checks passed;mypy 40 文件零错误。
### 2.2 集成测试
**结果:5 passed / 0 failed / 0 skipped**(26s):
| 用例 | 结论 | 关键断言 |
|---|---|---|
| APIS-glm-5.3 complete | ✓ | 非空响应,usage>0,17.0s/626tok |
| APIS-glm-5.3 stream | ✓ | ≥2 帧,末帧 usage(246tok) |
| nvidia openai complete | ✓ | 返回 "OK" |
| Pulsar 收发 | ✓ | 消费侧 JSON 含 tool/tenant |
| PG 读写分离 | ✓ | 写主库→锚定读→从库 ≤30s 追平 |
### 2.3 安全端到端
注入→**400**;重放→**429**;14 连发→8×200+6×**429**;JWT 强制→**401**/带证→**200**;审计脱敏 sk-***;哈希链篡改定位。
### 2.4 基准
缓存混合 59.5%;语义层 9.9%→**42.2%**(+32.3%);L1=64 即 100% L1 命中(30 键池)。
### 2.5 缺陷与遗留
无未决缺陷;遗留性能项=审计 P2/P3(多区域/Grafana/移动端)。
### 2.6 结论
满足 GB/T 9386 通过准则,达到 M1~M7 里程碑验收条件;可进入教学使用与二次开发。
