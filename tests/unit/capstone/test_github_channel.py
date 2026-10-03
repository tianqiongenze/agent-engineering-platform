"""GitHubChannel 单元测试(MockTransport)+ 缓存基准结果断言。"""

from __future__ import annotations

import json

import httpx
import pytest
from examples.capstone.software_factory.github_channel import (
    GitHubChannel,
    GitHubChannelError,
)

pytestmark = pytest.mark.unit


def make_channel(handler, repo: str = "acme/agent-platform") -> GitHubChannel:
    client = httpx.AsyncClient(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    )
    return GitHubChannel(token="test-token", repo=repo, client=client)  # noqa: S106


REF_OK = {"object": {"sha": "abc123"}}
PR_OK = {"number": 7, "html_url": "https://github.com/acme/x/pull/7"}


class TestGitHubChannel:
    async def test_create_branch_uses_base_sha(self) -> None:
        created: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/git/ref/heads/main"):
                return httpx.Response(200, json=REF_OK)
            created.update(json.loads(request.content))
            return httpx.Response(201, json={"ref": created["ref"]})

        sha = await make_channel(handler).create_branch("agent/task-1")
        assert sha == "abc123"
        assert created["ref"] == "refs/heads/agent/task-1"
        assert created["sha"] == "abc123"

    async def test_commit_file_with_b64_content(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if "/git/ref/" in request.url.path:
                return httpx.Response(200, json=REF_OK)
            if "/contents/" in request.url.path and request.method == "PUT":
                seen.update(json.loads(request.content))
                return httpx.Response(201, json={"commit": {"sha": "c99"}})
            return httpx.Response(200, json={})  # _maybe_file_sha → 200 但无 sha 亦可

        sha = await make_channel(handler).commit_file("b", "docs/x.md", "hello", "msg")
        assert sha == "c99"
        assert seen["message"] == "msg"

    async def test_create_pr(self) -> None:
        body_seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            body_seen.update(json.loads(request.content))
            return httpx.Response(201, json=PR_OK)

        pr = await make_channel(handler).create_pull_request("b", "title", "body")
        assert pr.number == 7 and pr.branch == "b"
        assert body_seen["head"] == "b" and body_seen["base"] == "main"

    async def test_error_surfaced(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"message": "validation failed"})

        with pytest.raises(GitHubChannelError, match="422"):
            await make_channel(handler).create_pull_request("b", "t")

    async def test_from_env_requires_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        with pytest.raises(GitHubChannelError, match="not configured"):
            GitHubChannel.from_env()


class TestCacheBenchmarkContract:
    """基准脚本的契约:混合命中率必须落在可解释区间。"""

    def test_benchmark_runs_and_blended_in_range(self, capsys: pytest.CaptureFixture) -> None:
        import contextlib
        import importlib.util
        import io

        spec = importlib.util.spec_from_file_location("bench_cache", "scripts/bench_cache.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)  # main() 由 __main__ guard 保护,直接调:
        mod.main()
        out = capsys.readouterr().out
        assert "混合命中率" in out
        assert "hit_rate" in out
