# Spec · 阶段二(M2):Agent 工具调用基础设施

> 对应课程第 2 章;实现:`src/agent_platform/tools/`

## 1. 目标(In Scope)
工具注册/发现/版本/启停、JSON Schema+Pydantic 参数校验、RBAC 与风险分级、人工确认、
调用审计(含脱敏)、超时/重试/降级、审计事件总线(内存 + Pulsar 适配)、CLI 调试入口、MCP 接入。

## 2. 接口契约
- `RiskLevel(str,Enum)`: read / write / dangerous
- `@tool(*,name,description,risk,timeout_s,mask_args)`: 从函数签名派生 Pydantic 输入模型并挂 `spec/fn`
- `ToolSpec(name,description,input_model,risk,timeout_s,version,enabled,mask_args)`
- `ToolContext(role: agent|readonly|admin, run_id, confirmed)`
- `ToolRegistry`: register / get / discover(keyword) / disable / is_enabled / get_fn
  —— 启停状态收归 Registry 内部,不污染共享 spec(测试隔离教训)
- `ToolExecutor.execute(name,args,ctx) -> ToolResult`: 权限 → 校验 → wait_for 超时 → 审计
  - 权限规则:readonly 仅 READ;agent 可 READ/WRITE;DANGEROUS 拒绝 readonly 且需 `confirmed=True`
  - 失败语义:参数非法 → `ValidationFailedError`;越权 → `PermissionDeniedError`;超时 → `ok=False, error=timeout...`
- `AuditEvent(event_id,run_id,tool,args(脱敏后),ok,error,latency_ms)`
- `AuditBus` 协议;`InMemoryAuditBus`(测试)/ `PulsarAuditBus`(懒加载,失败降级计数 dropped,不抛异常)

## 3. 验收标准
- [x] AC1 注册与关键词发现:`test_register_and_get/test_discover_by_keyword`
- [x] AC2 Schema 拦截非法参数:`test_invalid_args_blocked_by_schema`
- [x] AC3 RBAC + 高危确认制:`TestPermission` 3 例
- [x] AC4 审计含脱敏:`test_audit_event_masks_sensitive_args`(sk- 值 → ***MASKED***)
- [x] AC5 超时失败恢复:`test_timeout_recovers_as_failure`
- [x] AC6 Pulsar 适配器降级:`test_pulsar_audit.py`(3 例,工厂注入)
- [x] AC7 启停隔离:`test_disable_hides_tool`
- [ ] AC8 MCP Client 接入(文件系统 MCP;integration profile,依赖真实 MCP Server)
- [ ] AC9 CLI 调试入口(`python -m agent_platform.tools.cli list|call`;依赖 CLI 参数解析器,第 2 章实验课产出)

## 4. Out of Scope
工具版本灰度切换 UI(第 6 章版本对象)、调用队列编排(第 3 章 Loop 承担)、SQL/Shell 网关(第 3 章 Sandbox)。
