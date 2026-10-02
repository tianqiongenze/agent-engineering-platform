"""PulsarAuditBus 单元测试:假 factory 注入,验证降级语义。"""

from __future__ import annotations

import pytest

from agent_platform.tools.pulsar_audit import PulsarAuditBus
from agent_platform.tools.runtime import AuditEvent

pytestmark = pytest.mark.unit


def event() -> AuditEvent:
    return AuditEvent(event_id="e1", run_id="r1", tool="t", args={}, ok=True)


class FakeProducer:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send(self, payload: bytes) -> None:
        self.sent.append(payload)


class TestPulsarAuditBus:
    def test_publish_success(self) -> None:
        producer = FakeProducer()
        bus = PulsarAuditBus(factory=lambda url, topic: producer)
        bus.publish(event())
        assert bus.published == 1 and bus.dropped == 0
        assert b'"tool":"t"' in producer.sent[0]

    def test_factory_failure_degrades_silently(self) -> None:
        def broken(url: str, topic: str) -> object:
            raise RuntimeError("no broker")

        bus = PulsarAuditBus(factory=broken)
        bus.publish(event())  # 不得抛异常
        assert bus.dropped == 1 and bus.published == 0

    def test_send_failure_resets_producer_for_rebuild(self) -> None:
        bus = PulsarAuditBus(factory=lambda url, topic: FakeProducer())

        class Broken(FakeProducer):
            def send(self, payload: bytes) -> None:
                raise RuntimeError("broken pipe")

        bus._producer = Broken()  # 测试直注坏生产者(SLF001 豁免)
        bus.publish(event())
        assert bus.dropped == 1
        assert bus._producer is None  # 已复位,下条消息重建
