"""BC3 · 本地 Sandbox:文件读/写/命令三类边界(阶段三)。

教学为本地边界;Docker Sandbox 在第 3 章实验课以容器执行器接入(同一接口)。
"""

from __future__ import annotations

import os

_DANGEROUS_PATTERNS = (
    "--no-preserve-root",
    "mkfs",
    "| sh",
    "|sh",
    "| bash",
    "|bash",
    "> /dev/",
    "chmod 777 /",
)

_FORBIDDEN_HEADS = {"sudo", "su", "dd", "shred", "shutdown", "reboot", "kill"}


class SandboxViolation(PermissionError):
    pass


def _under(path: str, roots: list[str]) -> bool:
    real = os.path.realpath(path)
    return any(
        os.path.realpath(r) == os.path.commonpath([real, os.path.realpath(r)]) for r in roots
    )


class LocalSandbox:
    def __init__(
        self,
        allowed_roots: list[str],
        writable_roots: list[str] | None = None,
        command_whitelist: set[str] | None = None,
    ) -> None:
        self.allowed_roots = allowed_roots
        self.writable_roots = writable_roots or []
        self.command_whitelist = command_whitelist or set()

    def check_read(self, path: str) -> bool:
        if not _under(path, self.allowed_roots):
            raise SandboxViolation(f"read denied outside roots: {path}")
        return True

    def check_write(self, path: str) -> bool:
        if not _under(path, self.writable_roots):
            raise SandboxViolation(f"write denied outside writable roots: {path}")
        return True

    def check_command(self, command: str) -> bool:
        stripped = command.strip()
        head = stripped.split(maxsplit=1)[0] if stripped else ""
        if head in _FORBIDDEN_HEADS or head not in self.command_whitelist:
            raise SandboxViolation(f"command not in whitelist: {head!r}")
        lowered = stripped.lower()
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in lowered:
                raise SandboxViolation(f"dangerous pattern blocked: {pattern!r}")
        return True
