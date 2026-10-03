"""真实基础设施集成测试:Pulsar 收发 + PG 主从读写分离。

前置:docker compose -f docker-compose.infra.yml up -d(至少 pulsar 与 pg-*)
运行:uv run pytest -m integration -v
"""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration

_PULSAR_HTTP = os.getenv("PULSAR_HTTP_URL", "http://localhost:8080")
_PRIMARY = os.getenv(
    "PG_PRIMARY_DSN", "postgresql+asyncpg://agent:agent_pass@localhost:5432/agent_platform"
)
_REPLICA = os.getenv(
    "PG_REPLICA_DSN", "postgresql+asyncpg://agent:agent_pass@localhost:5433/agent_platform"
)


def _broker_alive() -> bool:
    try:
        return httpx.get(f"{_PULSAR_HTTP}/admin/v2/brokers/health", timeout=3).status_code == 200
    except Exception:
        return False


def _pg_alive() -> bool:
    try:
        import asyncio

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        async def probe() -> bool:
            engine = create_async_engine(_PRIMARY, pool_size=1)
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return True
            finally:
                await engine.dispose()

        return asyncio.run(probe())
    except Exception:
        return False


requires_pulsar = pytest.mark.skipif(not _broker_alive(), reason="Pulsar broker 未运行")
requires_pg = pytest.mark.skipif(not _pg_alive(), reason="PostgreSQL 未运行")


class TestPulsarReal:
    @requires_pulsar
    async def test_real_produce_consume_roundtrip(self) -> None:
        import pulsar as pulsar_sdk

        from agent_platform.security import run_as_tenant
        from agent_platform.tools.pulsar_audit import PulsarAuditBus
        from agent_platform.tools.runtime import AuditEvent

        tenant_token = run_as_tenant("acme-live")
        try:
            topic = (f"persistent://public/default/it-{uuid.uuid4().hex[:8]}")
            url = os.getenv("PULSAR_URL", "pulsar://localhost:6650")
            client = pulsar_sdk.Client(url)
            consumer = client.subscribe(topic, "it-sub",
                                        initial_position=pulsar_sdk.InitialPosition.Earliest)
            try:
                bus = PulsarAuditBus(url=url, topic=topic)
                event = AuditEvent(event_id=uuid.uuid4().hex, run_id="live-run",
                                   tool="get_weather", args={"city": "BJ"}, ok=True,
                                   meta={"tenant_id": "acme-live"})
                bus.publish(event)
                assert bus.published == 1
                msg = consumer.receive(timeout_millis=30000)
                payload = msg.data().decode()
                consumer.acknowledge(msg)
                assert '"tool":"get_weather"' in payload.replace(" ", "").replace(": ", ":")
                assert "acme-live" in payload
            finally:
                bus.close()
                client.close()
        finally:
            from agent_platform.security.auth import reset_tenant
            reset_tenant(tenant_token)


class TestPgReadWriteSplit:
    @requires_pg
    async def test_write_primary_read_your_writes_replica_lag(self) -> None:
        from agent_platform.shared.dao import DatabaseRouter

        router = DatabaseRouter(_PRIMARY, _REPLICA)
        token = uuid.uuid4().hex[:8]

        # 建表(主库)
        await router.write(
            "CREATE TABLE IF NOT EXISTS rw_demo (k text primary key, v text)"
        )
        # 写入(走主库)
        await router.write(
            "INSERT INTO rw_demo (k, v) VALUES (:k, :v) "
            "ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v",
            {"k": f"key-{token}", "v": token},
        )

        # 读己之写:写会话锚定期内,即使路由到主库也能读到
        async with router.write_session() as (_conn, sid):
            rows = await router.read(
                "SELECT v FROM rw_demo WHERE k = :k", {"k": f"key-{token}"}, session_id=sid
            )
            assert rows and rows[0]["v"] == token, "读己之写失败:锚定期内主库未读到"

        # 从库最终一致:轮询直至复制追平(≤30s)
        seen = False
        for _ in range(30):
            replica_rows = await router.read(
                "SELECT v FROM rw_demo WHERE k = :k", {"k": f"key-{token}"}
            )
            if replica_rows and replica_rows[0]["v"] == token:
                seen = True
                break
            await asyncio.sleep(1)
        assert seen, "30s 内从库未追平:流复制异常"

        # 路由计数证据:读己之写走了主库
        assert router.rw.reads_primary >= 1
        await router.write("DELETE FROM rw_demo WHERE k = :k", {"k": f"key-{token}"})
        await router.aclose()
