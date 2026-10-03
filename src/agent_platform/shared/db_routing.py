"""读写分离路由 + 读己之写会话锚定。

审计报告 R5 缺口落地:此前 PG 主从只是基础设施;本模块让"写走主库、
读走从库、读己之写强制主库"成为业务层可编程的路由策略。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4


class ReadWriteRouter:
    """DSN 路由器:write()/read() 返回目标 DSN。

    读己之写:进入 write_session 后,同会话内 read() 钉在主库,
    直至 TTL 过期(主从复制追平后自动回从库)。
    """

    def __init__(self, primary_dsn: str, replica_dsn: str, rtt_pin_ttl_s: float = 5.0) -> None:
        self.primary = primary_dsn
        self.replica = replica_dsn
        self.pin_ttl = rtt_pin_ttl_s
        self._pinned_until: dict[str, float] = {}
        self._lock = threading.Lock()
        self.reads_primary = 0
        self.reads_replica = 0

    @contextmanager
    def write_session(self, session_id: str | None = None) -> Iterator[str]:
        sid = session_id or uuid4().hex
        with self._lock:
            self._pinned_until[sid] = time.monotonic() + self.pin_ttl
        try:
            yield sid
        finally:
            pass  # 锚定按 TTL 自然过期,不主动清除(简化语义)

    def write_dsn(self, session_id: str | None = None) -> str:
        return self.primary

    def read_dsn(self, session_id: str | None = None) -> str:
        if session_id:
            with self._lock:
                until = self._pinned_until.get(session_id)
                if until is not None and time.monotonic() < until:
                    self.reads_primary += 1
                    return self.primary
                self._pinned_until.pop(session_id, None)
        self.reads_replica += 1
        return self.replica
