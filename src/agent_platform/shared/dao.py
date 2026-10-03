"""数据访问层:读写分离路由的 SQLAlchemy Async 实现(审计 R5 收口)。

- write():主库
- read():从库;读己之写会话内钉主库(TTL 后回从)
- 教学版同步语义;生产在此之上叠 Repository/聚合映射(DDD 分层不变)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from agent_platform.shared.db_routing import ReadWriteRouter


class DatabaseRouter:
    def __init__(
        self,
        primary_dsn: str,
        replica_dsn: str | None = None,
        *,
        rw: ReadWriteRouter | None = None,
        pool_size: int = 2,
    ) -> None:
        self.primary_dsn = primary_dsn
        self.replica_dsn = replica_dsn or primary_dsn
        self.rw = rw or ReadWriteRouter(primary_dsn, self.replica_dsn)
        self._primary: AsyncEngine = create_async_engine(primary_dsn, pool_size=pool_size)
        self._replica: AsyncEngine = (
            create_async_engine(self.replica_dsn, pool_size=pool_size)
            if self.replica_dsn != primary_dsn else self._primary
        )

    @asynccontextmanager
    async def write_session(self) -> AsyncIterator[Any]:
        """写会话:主库连接,结束后保留读己之写锚定(锚定策略为同步 CM)。"""
        from contextlib import AsyncExitStack

        async with AsyncExitStack() as stack:
            sid = stack.enter_context(self.rw.write_session())
            conn = await stack.enter_async_context(self._primary.begin())
            yield conn, sid

    async def write(self, sql: str, params: dict[str, Any] | None = None) -> None:
        sql_text = text(sql)
        async with self.write_session() as (conn, _sid):
            await conn.execute(sql_text, params or {})

    async def read(self, sql: str, params: dict[str, Any] | None = None,
                   session_id: str | None = None) -> list[dict[str, Any]]:
        """读:路由决定主/从;返回行字典列表。"""
        target = self.rw.read_dsn(session_id)
        engine = self._primary if target == self.primary_dsn else self._replica
        async with engine.connect() as conn:
            rows = (await conn.execute(text(sql), params or {})).mappings().all()
            return [dict(r) for r in rows]

    async def aclose(self) -> None:
        await self._primary.dispose()
        if self._replica is not self._primary:
            await self._replica.dispose()
