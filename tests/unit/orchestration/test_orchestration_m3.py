"""阶段三(M3)Agent Loop / State Machine / Checkpoint / Sandbox 单元测试。"""

from __future__ import annotations

import os

import pytest

from agent_platform.orchestration.loop import (
    Action,
    AgentLoop,
    AgentState,
    CheckpointStore,
    Decider,
    LoopFailedError,
)
from agent_platform.orchestration.sandbox import LocalSandbox, SandboxViolation

pytestmark = pytest.mark.unit

_TMP = os.environ.get("TMPDIR", "/private/tmp")


def make_loop(decider: Decider, max_iterations: int = 8) -> tuple[AgentLoop, CheckpointStore]:
    store = CheckpointStore()
    return AgentLoop(decider=decider, checkpoint=store, max_iterations=max_iterations), store


class ScriptedDecider:
    """按脚本依次返回动作;obs 记录每轮观察(测试可断言)。"""

    def __init__(self, script: list[Action]) -> None:
        self.script = list(script)
        self.observed: list[str] = []

    async def __call__(self, obs: list[str]) -> Action:
        self.observed = list(obs)
        return self.script.pop(0) if self.script else Action.finish("no more script")


class TestStateMachine:
    def test_nine_states_defined(self) -> None:
        expected = {
            "created",
            "planning",
            "running",
            "tool_failed",
            "waiting_tool",
            "waiting_approval",
            "completed",
            "failed",
            "cancelled",
        }
        assert {s.value for s in AgentState} == expected


class TestAgentLoop:
    async def test_finish_immediately_completes(self) -> None:
        decider = ScriptedDecider([Action.finish("done!")])
        loop, store = make_loop(decider)
        run = await loop.run("说点什么")
        assert run.state is AgentState.COMPLETED
        assert run.final_output == "done!"
        assert store.load(run.run_id).state is AgentState.COMPLETED

    async def test_tool_call_then_finish(self) -> None:
        decider = ScriptedDecider(
            [
                Action.call_tool("get_weather", {"city": "BJ"}),
                Action.finish("weather ready"),
            ]
        )
        loop, _ = make_loop(decider)
        run = await loop.run("查天气")
        assert run.state is AgentState.COMPLETED
        assert run.steps[0].tool == "get_weather"
        assert "sunny" in str(run.steps[0].output)

    async def test_max_iterations_aborts(self) -> None:
        # 参数逐次变化,避开死循环检测,专测迭代上限
        script = [Action.call_tool("get_weather", {"city": f"c{i}"}) for i in range(99)]
        decider = ScriptedDecider(script)
        loop, _ = make_loop(decider, max_iterations=3)
        run = await loop.run("无限循环")
        assert run.state is AgentState.FAILED
        assert "max iterations" in run.error

    async def test_repeated_identical_action_detected_as_deadloop(self) -> None:
        same = Action.call_tool("get_weather", {"city": "BJ"})
        decider = ScriptedDecider([same, same, same, same])
        loop, _ = make_loop(decider, max_iterations=10)
        with pytest.raises(LoopFailedError, match="dead loop"):
            await loop.run("重复任务")

    async def test_checkpoint_resumes_from_step(self) -> None:
        """中断恢复:重建 loop 从 checkpoint 续跑。"""
        first = ScriptedDecider(
            [
                Action.call_tool("get_weather", {"city": "BJ"}),
                Action.call_tool("get_weather", {"city": "SH"}),
            ]
        )
        loop1, store = make_loop(first, max_iterations=1)  # 第一步后超限失败
        run1 = await loop1.run("两步任务")
        assert run1.state is AgentState.FAILED  # 未完成即中断

        resumed_decider = ScriptedDecider([Action.finish("resumed done")])
        loop2 = AgentLoop(
            decider=resumed_decider,
            checkpoint=store,
            max_iterations=4,
            resume_from=run1.run_id,
        )
        run2 = await loop2.run("两步任务")
        assert run2.state is AgentState.COMPLETED
        assert run2.obs_history[:1] == run1.obs_history  # 历史被带入


class TestLocalSandbox:
    def test_allows_read_within_roots(self, tmp_path) -> None:
        sb = LocalSandbox(allowed_roots=[str(tmp_path)])
        assert sb.check_read(str(tmp_path / "a.txt")) is True

    def test_denies_read_outside_roots(self, tmp_path) -> None:
        sb = LocalSandbox(allowed_roots=[str(tmp_path)])
        with pytest.raises(SandboxViolation):
            sb.check_read("/etc/passwd")

    def test_write_requires_explicit_write_root(self, tmp_path) -> None:
        sb = LocalSandbox(allowed_roots=[str(tmp_path)], writable_roots=[str(tmp_path)])
        assert sb.check_write(str(tmp_path / "out.md")) is True

    def test_command_whitelist(self) -> None:
        sb = LocalSandbox(allowed_roots=[_TMP], command_whitelist={"ls", "pytest"})
        assert sb.check_command("ls -la") is True
        with pytest.raises(SandboxViolation):
            sb.check_command("rm -rf /")

    def test_dangerous_command_always_blocked(self) -> None:
        sb = LocalSandbox(allowed_roots=[_TMP], command_whitelist={"rm"})
        with pytest.raises(SandboxViolation):
            sb.check_command("rm -rf --no-preserve-root /")
