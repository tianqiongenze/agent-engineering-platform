"""Pulsar 审计总线适配器:懒加载 + 尽力而为降级(失败不阻塞主链路)。

韧性原则:审计是旁路,Producer 不可用时丢弃计数并复位,下条消息重建连接;
绝不向工具执行主流程抛异常。真实 Pulsar 连接属 integration profile。
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agent_platform.tools.runtime import AuditBus, AuditEvent

ClientFactory = Callable[[str, str], Any]


def _default_factory(url: str, topic: str) -> Any:
    import pulsar  # 懒加载:无 Pulsar 环境时不 import(PLC0415 豁免行内说明)

    client = pulsar.Client(url)
    return client.create_producer(topic)


class PulsarAuditBus(AuditBus):
    def __init__(
        self,
        url: str = "pulsar://localhost:6650",
        topic: str = "persistent://public/default/tool-audit",
        factory: ClientFactory | None = None,
    ) -> None:
        self.url = url
        self.topic = topic
        self._factory = factory or _default_factory
        self._producer: Any | None = None
        self._lock = threading.RLock()  # 可重入:publish 同步路径嵌套 _send_blocking 需重入
        self._io_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pulsar-audit")
        self._closed = False
        self.published = 0
        self.dropped = 0

    def _ensure_producer(self) -> Any:
        if self._producer is None:
            self._producer = self._factory(self.url, self.topic)
        return self._producer

    def _send_blocking(self, event: AuditEvent) -> None:
        """真实网络发送(仅供线程池调用;失败复位 producer 待重建)。

        P2-14:producer 的取用与复位统一经锁(锁内仅对象交换,无网络 IO)。
        """
        with self._lock:
            if self._closed:
                return
            producer_ref = self._producer
        try:
            if producer_ref is None:
                producer_ref = self._factory(self.url, self.topic)
                with self._lock:
                    if self._closed:
                        return
                    self._producer = producer_ref
            producer_ref.send(event.model_dump_json().encode())
            self.published += 1
        except Exception:  # 旁路降级:吞异常、计数、复位待重建
            self.dropped += 1
            with self._lock:
                self._producer = None

    def publish(self, event: AuditEvent) -> None:
        """同步 API;在事件循环内自动移交 I/O 线程池,不阻塞主循环(审查重构项)。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.run_in_executor(self._io_pool, self._send_blocking, event)
        else:
            with self._lock:
                self._send_blocking(event)

    def close(self) -> None:
        with self._lock:
            if self._producer is not None:
                try:
                    self._producer.close()
                except Exception as exc:  # noqa: BLE001(关停旁路,丢弃即达成幂等)
                    _ = str(exc)
                self._producer = None
