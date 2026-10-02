# Spec · 阶段三(M3):Agent Loop、State Machine 与 Sandbox

> 对应课程第 3 章;实现:`src/agent_platform/orchestration/`

## 1. 目标(In Scope)
可连续思考/执行/观察/纠错的长程任务执行骨架:五段循环、9 态任务状态机、Checkpoint 断点续跑、
死循环熔断、文件/Shell/网络三类执行边界。

## 2. 接口契约
- `Action.call_tool(name,args)` / `Action.finish(content)`;`signature()` 供死循环比对
- `Decider = Callable[[list[str]], Awaitable[Action]]` —— LLM 决策的防腐层
  (生产由 Gateway 驱动;测试注入 ScriptedDecider)
- `AgentState(StrEnum)` 9 态:created/planning/running/tool_failed/waiting_tool/waiting_approval/completed/failed/cancelled
- `AgentLoop.run(goal) -> AgentRun`:
  - 每轮:decide → finish 则 COMPLETED;tool 则经 ToolExecutor 执行,观察回灌 obs_history
  - 终止:finish / `max_iterations`(→ FAILED) / 连续 3 个相同动作签名(→ `LoopFailedError` 死循环熔断)
  - 每轮后 `checkpoint.save`(深拷贝)
- `CheckpointStore.save/load`;构造参数 `resume_from` 续跑:steps 与 obs_history 完整带入
- `LocalSandbox(allowed_roots, writable_roots, command_whitelist)`:
  - check_read/check_write:realpath 归一后必须在对应根内,否则 `SandboxViolation`
  - check_command:白名单 + 危险模式硬拦截(--no-preserve-root/mkfs/管道 sh 等 + sudo/dd 等禁用头部)

## 3. 验收标准
- [x] AC1 九态完备:`test_nine_states_defined`
- [x] AC2 finish 即完成且落盘:`test_finish_immediately_completes`
- [x] AC3 工具→观察→完成链路:`test_tool_call_then_finish`
- [x] AC4 迭代上限:`test_max_iterations_aborts`(参数逐次变化避开死循环路径——两条失败路径须分开测)
- [x] AC5 死循环熔断:`test_repeated_identical_action_detected_as_deadloop`
- [x] AC6 断点续跑:`test_checkpoint_resumes_from_step`(历史观察带回)
- [x] AC7 Sandbox 三类拦截:`TestLocalSandbox` 5 例(越界读/写/白名单外/危险模式)
- [ ] AC8 Docker Sandbox 执行器(同接口,容器内执行;第 3 章实验课)
- [ ] AC9 Codebase 十类工具集与 LangGraph 映射(第 3 章实验课产出)

## 4. Out of Scope
Planning 多策略(一次性/动态)由 Decider 实现层承担;Human-in-the-loop 状态迁移(waiting_approval)
在 Harness 化时接入;风险回放 UI 属第 6 章 Replay。
