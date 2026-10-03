"""Capstone B · GitHub Channel:真实 GitHub 集成(分支/提交/PR/CI 状态)。

REST API via httpx;单测用 MockTransport,联调用 GITHUB_TOKEN + GITHUB_REPO 环境变量。
Token 永不落盘、不进日志(只进请求头)。
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx


class GitHubChannelError(RuntimeError):
    pass


@dataclass
class PullRequest:
    number: int
    url: str
    branch: str
    state: str = "open"


class GitHubChannel:
    """软件工厂的 DevOps 集成通道(第 7 章讲 7-2)。"""

    def __init__(
        self,
        *,
        token: str,
        repo: str,
        base_branch: str = "main",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.repo = repo
        self.base_branch = base_branch
        self._client = client or httpx.AsyncClient(
            base_url="https://api.github.com",
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    @classmethod
    def from_env(cls, base_branch: str = "main") -> GitHubChannel:
        import os

        token = os.getenv("GITHUB_TOKEN", "")
        repo = os.getenv("GITHUB_REPO", "")
        if not token or not repo:
            raise GitHubChannelError("GITHUB_TOKEN / GITHUB_REPO not configured")
        return cls(token=token, repo=repo, base_branch=base_branch)

    async def _raise(self, resp: httpx.Response, action: str) -> None:
        if resp.status_code >= 400:
            raise GitHubChannelError(f"{action} failed: HTTP {resp.status_code}: {resp.text[:160]}")

    async def _get_ref_sha(self, branch: str) -> str:
        resp = await self._client.get(f"/repos/{self.repo}/git/ref/heads/{branch}")
        await self._raise(resp, f"get ref {branch}")
        return resp.json()["object"]["sha"]

    async def create_branch(self, new_branch: str, from_branch: str | None = None) -> str:
        base = from_branch or self.base_branch
        sha = await self._get_ref_sha(base)
        resp = await self._client.post(
            f"/repos/{self.repo}/git/refs",
            json={"ref": f"refs/heads/{new_branch}", "sha": sha},
        )
        await self._raise(resp, f"create branch {new_branch}")
        return sha

    async def commit_file(self, branch: str, path: str, content: str, message: str) -> str:
        """单文件提交(Contents API);返回新 commit sha。"""
        resp = await self._client.put(
            f"/repos/{self.repo}/contents/{path}",
            json={
                "message": message,
                "branch": branch,
                "content": base64.b64encode(content.encode()).decode(),
                "sha": await self._maybe_file_sha(branch, path),
            },
        )
        await self._raise(resp, f"commit {path}")
        return resp.json()["commit"]["sha"]

    async def _maybe_file_sha(self, branch: str, path: str) -> str | None:
        resp = await self._client.get(f"/repos/{self.repo}/contents/{path}", params={"ref": branch})
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None

    async def create_pull_request(self, head: str, title: str, body: str = "") -> PullRequest:
        resp = await self._client.post(
            f"/repos/{self.repo}/pulls",
            json={"title": title, "head": head, "base": self.base_branch, "body": body},
        )
        await self._raise(resp, "create pull request")
        data = resp.json()
        return PullRequest(number=data["number"], url=data["html_url"], branch=head)

    async def latest_check_status(self, branch: str) -> dict[str, Any]:
        sha = await self._get_ref_sha(branch)
        resp = await self._client.get(f"/repos/{self.repo}/commits/{sha}/check-runs")
        await self._raise(resp, "list check runs")
        runs = resp.json().get("check_runs", [])
        return {"total": len(runs), "conclusions": [r.get("conclusion") for r in runs]}

    async def aclose(self) -> None:
        await self._client.aclose()


async def ship_change(spec: str, change_note: str, new_branch: str, file_path: str) -> PullRequest:
    """端到端:开分支 → 提交变更说明 → 发 PR(软件工厂交付动作)。"""
    channel = GitHubChannel.from_env()
    await channel.create_branch(new_branch)
    await channel.commit_file(
        new_branch,
        file_path,
        f"# 变更说明\n\n- spec: {spec}\n\n{change_note}\n",
        message=f"feat({spec}): agent-generated change",
    )
    return await channel.create_pull_request(
        new_branch, title=f"[software-factory] {spec}", body=change_note
    )
