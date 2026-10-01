"""阶段四(M4)Context Engineering / Memory / Hybrid RAG 单元测试。"""

from __future__ import annotations

import pytest

from agent_platform.context_memory.context import ContextWindow, compress_history
from agent_platform.context_memory.memory import MemoryStore
from agent_platform.context_memory.rag import Chunk, HybridRetriever

pytestmark = pytest.mark.unit


class TestContextCompression:
    def test_compress_keeps_system_and_recent_within_budget(self) -> None:
        msgs = [f"msg-{i}" for i in range(20)]
        out = compress_history(msgs, keep_head=1, keep_tail=5)
        assert out[0] == "msg-0"
        assert out[-5:] == msgs[-5:]
        assert len(out) < len(msgs)
        assert any("[summarized" in m for m in out)

    def test_context_window_budget_in_tokens(self) -> None:
        win = ContextWindow(budget_tokens=10)
        msgs = [f"x{i}" for i in range(20)]  # 每条约 1 token 近似
        trimmed, report = win.fit(msgs)
        assert len(trimmed) <= 10
        assert report.original_count == 20
        assert report.final_count == len(trimmed)
        assert report.compression_ratio < 1.0


class TestMemoryStore:
    async def test_short_term_roundtrip(self) -> None:
        mem = MemoryStore()
        mem.set_short("goal", "修复登录 bug")
        assert mem.get_short("goal") == "修复登录 bug"

    async def test_long_term_search_by_keyword(self) -> None:
        mem = MemoryStore()
        mem.add_long("用户偏好:输出要简洁", source="chat", confidence=0.9)
        mem.add_long("项目约定:测试用 pytest", source="wiki", confidence=0.8)
        hits = mem.search_long("pytest")
        assert len(hits) == 1 and "pytest" in hits[0].content

    async def test_project_memory_persist(self) -> None:
        mem = MemoryStore()
        mem.set_project("build_cmd", "make test")
        assert mem.project["build_cmd"] == "make test"

    async def test_memory_summary_for_context_recovery(self) -> None:
        mem = MemoryStore()
        mem.set_short("done", "已定位根因")
        summary = mem.task_summary()
        assert "已定位根因" in summary


class TestHybridRetriever:
    def make_corpus(self) -> list[Chunk]:
        return [
            Chunk(id="auth-1", text="login 鉴权逻辑 auth.py token 校验", source="auth.py"),
            Chunk(id="auth-2", text="auth middleware 拦截未授权请求", source="middleware.py"),
            Chunk(id="pay-1", text="payment 支付渠道下单流程", source="payment.py"),
            Chunk(id="docs-1", text="部署文档 deploy 使用 docker compose", source="docs/deploy.md"),
        ]

    def test_keyword_and_semantic_merged(self) -> None:
        retriever = HybridRetriever(corpus=self.make_corpus())
        hits = retriever.search("鉴权 登录 auth", k=2)
        assert len(hits) >= 1
        assert hits[0].chunk.source in {"auth.py", "middleware.py"}
        assert hits[0].score > 0

    def test_rrf_fusion_prefers_hit_by_both_channels(self) -> None:
        retriever = HybridRetriever(corpus=self.make_corpus())
        hits = retriever.search("auth", k=4)
        top = hits[0]
        double_hit = sum(1 for h in hits if "auth" in h.chunk.text.lower())
        assert double_hit >= 2  # 两个 auth chunk 都被召回
        assert top.chunk.id.startswith("auth")

    def test_no_hit_returns_empty(self) -> None:
        retriever = HybridRetriever(corpus=self.make_corpus())
        assert retriever.search("量子物理", k=3) == []
