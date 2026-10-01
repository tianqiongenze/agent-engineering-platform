# Agent Engineering Platform

> 《AI Agent 全栈工程师训练营》配套工程 —— 单仓库、六大演进阶段、全链路可测。
> 方法论:SDD(spec → plan → tasks → implement)· TDD · DDD · TOGAF 视图
> 工业件:GraphQL BFF · Pulsar 事件骨干 · PostgreSQL 读写分离 · 四级缓存

## 快速开始

```bash
# 0) 安装工具链(如无)
brew install uv

# 1) 一键环境(Python 3.12 由 uv 自动管理)
make setup

# 2) 启动基础设施(PG 主从 / Redis / Pulsar / Milvus)
make infra

# 3) 跑测试(单元,CI 同款)
make test

# 4) 起应用(开发模式)
make dev
```

## 目录结构

```
src/agent_platform/
  shared/         共享内核:领域事件、Outbox、结果类型、缓存抽象
  gateway/        BC1 LLM 网关:多模型路由/Streaming/结构化输出/成本留痕
  tools/          BC2 工具运行时:注册/校验/RBAC/审计/MCP
  orchestration/  BC3 Agent Loop/状态机/Checkpoint/Sandbox
  context_memory/ BC4 上下文工程/记忆/RAG
  multi_agent/    BC5 多智能体/Skill
  eval/           BC6 评测:Golden Set/Judge/回归
  governance/     BC7 Trace/Replay/版本/灰度/成本
  api/            GraphQL BFF + REST(SSE/Webhook)
docs/
  architecture/   TOGAF 四视图 + ADR 决策记录
  specs/          SDD 规范(每阶段一份)
  runbooks/       上线 Runbook
infra/            PG 主从初始化、Pulsar 配置
tests/            unit / integration 分层
```

## 六大演进阶段(与课程章节一一对应)

| 阶段 | 课程章 | 能力 | 标签 |
|---|---|---|---|
| M1 | 第1章 | LLM 统一模型调用服务(Gateway) | `phase/m1` |
| M2 | 第2章 | 工具调用基础设施(Tool Runtime+MCP) | `phase/m2` |
| M3 | 第3章 | Codebase Agent(Loop/State/Sandbox) | `phase/m3` |
| M4 | 第4章 | Codebase RAG & Memory | `phase/m4` |
| M5 | 第5章 | Multi-Agent & Eval Platform | `phase/m5` |
| M6 | 第6章 | Production Ready(可观测/灰度/Runbook) | `phase/m6` |

## 环境变量

复制 `.env.example` 为 `.env`。真实 LLM 接入:设置 `LLM_PROVIDER=openai_compatible` +
`OPENAI_BASE_URL` / `OPENAI_API_KEY`;默认 `LLM_PROVIDER=mock`(CI 与单测零外部依赖)。
