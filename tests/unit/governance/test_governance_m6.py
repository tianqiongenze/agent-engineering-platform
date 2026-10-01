"""阶段六(M6)可观测与治理:Trace / Replay / Feature Flag / Cost Ledger。"""

from __future__ import annotations

import pytest

from agent_platform.governance.cost import CostLedger
from agent_platform.governance.flags import FeatureFlags
from agent_platform.governance.trace import ReplayStore, TraceCollector

pytestmark = pytest.mark.unit


class TestTrace:
    def test_span_tree_and_total_latency(self) -> None:
        collector = TraceCollector()
        with collector.span("run") as run_span:
            with collector.span("llm_call", parent=run_span.span_id) as llm_span:
                llm_span.set_meta(model="primary", tokens=120)
            with collector.span("tool_call", parent=run_span.span_id) as tool_span:
                tool_span.set_ok(False, error="timeout")
        trace = collector.build()
        assert len(trace.spans) == 3
        assert {s.name for s in trace.spans} == {"run", "llm_call", "tool_call"}
        failed = next(s for s in trace.spans if s.name == "tool_call")
        assert failed.ok is False and "timeout" in (failed.error or "")

    def test_failed_span_marks_trace_unhealthy(self) -> None:
        collector = TraceCollector()
        with collector.span("run") as root:
            with collector.span("tool", parent=root.span_id) as s:
                s.set_ok(False, error="boom")
        assert collector.build().healthy is False


class TestReplay:
    async def test_replay_reproduces_identical_result(self) -> None:
        store = ReplayStore()
        captured_inputs: list[str] = []
        original_outputs: list[str] = []

        async def llm(prompt: str) -> str:
            captured_inputs.append(prompt)
            return f"echo::{prompt}"

        # 原始执行 + 录制
        for p in ["a", "b"]:
            out = await llm(p)
            original_outputs.append(out)
            store.record(prompt=p, output=out)

        # 回放:相同输入得到相同输出(确定性验证)
        replayed = [await store.replay(r.prompt, llm) for r in store.recordings()]
        assert replayed == original_outputs
        assert captured_inputs == ["a", "b", "a", "b"]  # 回放真实重执行


class TestFeatureFlags:
    def test_boolean_flag(self) -> None:
        flags = FeatureFlags()
        flags.set("new_planner", enabled=True)
        assert flags.is_enabled("new_planner", user_id="u1") is True

    def test_percentage_rollout_is_deterministic(self) -> None:
        flags = FeatureFlags()
        flags.set("gray_prompt_v2", enabled=True, rollout_percent=50)
        # 同一用户反复判定结果一致(一致性哈希灰度的关键性质)
        first = flags.is_enabled("gray_prompt_v2", user_id="user-42")
        assert all(
            flags.is_enabled("gray_prompt_v2", user_id="user-42") == first for _ in range(10)
        )
        # 大样本下灰度比例接近 50%(桶分布)
        hits = sum(1 for i in range(1000) if flags.is_enabled("gray_prompt_v2", user_id=f"u{i}"))
        assert 400 < hits < 600

    def test_disabled_flag_defaults_off(self) -> None:
        assert FeatureFlags().is_enabled("unknown", user_id="u") is False


class TestCostLedger:
    def test_record_and_report_by_model(self) -> None:
        ledger = CostLedger(pricing={"primary": 0.5, "fast": 0.1})  # 元/千token
        ledger.record(model="primary", prompt_tokens=1000, completion_tokens=1000)
        ledger.record(model="fast", prompt_tokens=2000, completion_tokens=0)
        report = ledger.report()
        assert report["primary"] == pytest.approx(1.0)  # 2k tokens x 0.5 元/k
        assert report["fast"] == pytest.approx(0.2)  # 2k tokens x 0.1 元/k
        assert report["_total"] == pytest.approx(1.2)

    def test_unknown_model_is_free_and_flagged(self) -> None:
        ledger = CostLedger(pricing={})
        ledger.record(model="mystery", prompt_tokens=10, completion_tokens=10)
        assert ledger.report()["_unpriced_models"] == ["mystery"]
