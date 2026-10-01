# ADR-002:LLM Provider 策略 —— Mock 优先 + 可插拔

- 状态:**Proposed(默认值推进,待负责人确认 D2)**
- 日期:2026-10-01

## 决策
`LLMProvider` 抽象两种实现:
1. `MockProvider`:确定性回放(prompt→分块响应/工具调用意图),CI 与单测零外部依赖、断言可重复;
2. `OpenAICompatibleProvider`:任何 OpenAI 兼容端点(云 API/网关/本地 vLLM),运行时经 `.env` 切换。

生产域 Mock 零残留铁律的适用方式:Mock 属测试/本地域,由 `LLM_PROVIDER` 显式开关;生产部署配置必为真实 Provider,CI 扫描生产 compose/env 文件中出现 `LLM_PROVIDER=mock` 即红。

## 理由
- 测试确定性:LLM 输出不可复现会毁掉 TDD 节奏与 CI 稳定性;
- 成本可控:授课演示时才配置真实 Key;
- 大纲要求"封装 OpenAI Compatible 协议"本身即多厂商可插拔。

## 后果
- MockProvider 需维护脚本化行为(按 prompt 关键词路由预设响应),本身有测试成本;
- 真实 Provider 行为差异(限流/字段)需在集成 profile 验证。
