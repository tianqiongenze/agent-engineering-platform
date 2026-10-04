# 软件需求规格说明书(SRS)· GB/T 9385 结构

> 项目:Agent Engineering Platform v1.3 · 2026-10-04 · 与 specs/spec-phase1~6 构成"总-分"关系
> 完整性:本 SRS 为教学裁剪版,章节结构严格对齐 GB/T 9385;详单引 specs 不重复

## 1 引言
### 1.1 目的
定义 Agent Engineering Platform 的功能/非功能需求,作为设计、实现、验收的基准(GB/T 9385)。
### 1.2 范围
面向 AI Agent 开发教学与生产原型的统一平台:LLM 网关、工具运行时、Agent 编排、上下文/RAG、多智能体、评测、治理可观测七大能力域(20 项能力,见 README §6)。
### 1.3 术语与缩略语
Agent/Tool Runtime/MCP/Outbox/RBAC/HITL/RRF/RRF-K/JWT/SLA(定义见课程讲义 ch0)。
### 1.4 参考资料
GB/T 9385-2008、GB/T 8567-2006、GB/T 25000.10-2016、TOGAF 10、大纲 course_outline.txt、ADR-001~004/007。

## 2 总体描述
### 2.1 产品前景
教学平台(单机 Compose)与生产原型(可水平扩展)双形态;是训练营七大里程碑 M1~M7 的承载物。
### 2.2 产品功能(汇总,详单→ specs)
F1 LLM 网关(双协议/路由/流式/留痕) F2 工具运行时(注册/校验/RBAC/审计/MCP) F3 编排(Loop/9 态/Checkpoint/Sandbox) F4 上下文(压缩/预算/三层记忆/Hybrid RAG) F5 多智能体(Supervisor/委托八要素/Skill) F6 评测(Golden/指标/回归) F7 治理(Trace/Replay/Flag/成本/metrics/风控)。
### 2.3 用户特征
学员(后端转型)/讲师(演示)/平台运维(演练);面试者(作品集)。
### 2.4 约束
Python 3.12;密钥永不入库;教学 Mock 与生产真实 Provider 显式开关(ADR-002);单机拓扑但多节点可移植(ADR-003)。
### 2.5 假设与依赖
外部 LLM 端点可用性;Docker 环境镜像可达(含镜像源)。

## 3 具体需求(外部接口→功能→非功能)
### 3.1 外部接口
- API:POST /v1/chat/completions(SSE)、GET /v1/tools、/graphql、/healthz、/metrics(可保护)
- 硬件:≥16GB RAM 开发机;通信:HTTP/1.1 SSE、Pulsar 二进制、PG 流复制
### 3.2 功能需求(带验收→ specs AC)
FR-1 模型调用:统一 ChatRequest/Response;路由 fallback(attempts 留痕);SSE 末帧 usage。[spec1 AC2~4]
FR-2 工具:注册/发现/启停;执行六步管线;RBAC 三角色;DANGEROUS 需确认;审计脱敏+哈希链。[spec2 AC1~7]
FR-3 编排:五段循环;九态;四出口终止(含 3 连相同动作熔断);Checkpoint 恢复;Sandbox 三边界。[spec3 AC1~7]
FR-4 认知:压缩(FitReport);三层记忆;Hybrid RAG(RRF K=60)+L3 语义缓存(τ=0.92)。[spec4 + bench]
FR-5 协作:委托八要素;同 aspect 冲突仲裁(证据多数);Skill 版本递增。[spec5]
FR-6 评测:GoldenCase;成功率/工具准确率;回归双清单。[spec5]
FR-7 治理:Span 树;Replay 重执行;一致性哈希灰度;成本账本;JWT/租户;防刷防重放防注入。[spec6 + v1.3]
### 3.3 非功能需求(可度量)
NFR-性能:网关代理开销 <50ms(不含推理);TTFT 记录。NFR-可靠:核心事件 at-least-once+幂等;复制追平 ≤30s。NFR-安全:注入/重放/越权拦截 100%(实测);密钥零入库。NFR-可维护:覆盖率 ≥80%(实测 93%);mypy 零错。NFR-可移植:compose 单机→多节点同构。
### 3.4 数据需求
九类持久对象(工具/任务/审计/评测/版本/知识库…)与 Outbox 表;敏感字段脱敏规则(mask_args)。
### 3.5 验收准则
里程碑 M1~M7 验收清单(实验手册)+ CI 门禁(测试/覆盖率/lint/类型/评测)。

## 4 附录
A. 追踪矩阵:FR↔spec↔测试↔代码路径(见 SDD §6)。B. 决策记录索引:ADR 目录。
