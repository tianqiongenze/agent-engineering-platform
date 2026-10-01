# Spec · 阶段一(M1):LLM 统一模型调用服务

> 对应课程第 1 章《LLM API、Prompt 与结构化输出》
> SDD 流程:本文件为 specify 产物;实现须先有失败测试(TDD),验收标准全部可自动化执行。

## 1. 目标(In Scope)
为 Agent Engineering Platform 提供统一模型调用入口(LLM Gateway):多模型路由、流式输出、
结构化输出、成本留痕、重试降级。所有上层 BC 只依赖本模块的 Provider 抽象。

## 2. 接口契约

### 2.1 域模型(`agent_platform.gateway.domain`)
- `ChatMessage(role: "system"|"user"|"assistant"|"tool", content: str)`
- `Usage(prompt_tokens, completion_tokens, total_tokens)` —— total 派生,不外部传入
- `ChatRequest(model, messages, temperature=0.7, top_p=1.0, max_tokens=1024, response_schema: dict|None)`
- `ChatResponse(model, content, usage, latency_ms, finish_reason)`

### 2.2 Provider 抽象(`gateway.provider`)
```python
class LLMProvider(Protocol):
    async def complete(self, req: ChatRequest) -> ChatResponse: ...
    async def stream(self, req: ChatRequest) -> AsyncIterator[str]: ...
```
- `MockProvider`:确定性;按 prompt 关键词匹配预设脚本;支持分块产出流;
  记录调用次数供测试断言;非法 model 抛 `ProviderError`。
- `OpenAICompatibleProvider`:Phase 后段接入(真实 HTTP,集成测试覆盖)。

### 2.3 模型路由(`gateway.router`)
- `ModelRouter(chain: list[str])`:按优先级尝试,ProviderError 时 fallback 到下一个;
  全部失败抛 `AllProvidersFailedError`;记录每次尝试(供 Trace 留痕)。

## 3. 验收标准(Acceptance)
- [x] AC1:域模型不变量(Usage.total 派生;ChatRequest 默认参数)有单测覆盖
- [x] AC2:MockProvider.complete 返回预设内容,Usage 统计正确
- [x] AC3:MockProvider.stream 按 chunk 产出,拼接等于 complete 内容
- [x] AC4:ModelRouter 主模型失败自动 fallback,次模型成功;全部失败抛聚合异常
- [x] AC5:`pytest -m unit` 全绿,覆盖率 ≥80%(CI 门禁)
- [ ] AC6:OpenAICompatibleProvider 集成测试(需 `LLM_PROVIDER=openai_compatible`,手动验证)

## 4. Out of Scope(后续阶段)
Prompt 模板版本管理(M1 第 4 讲)、JsonSchema 重试纠错(M1 第 5 讲)、
成本事件发 Pulsar(M6 治理联动)、语义缓存(M4)。
