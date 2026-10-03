"""Transactional Outbox(事件可靠性 EER 铁律的教学落地)。

业务状态与 outbox 记录同"事务"提交(教学版为进程内原子结构,生产为同库事务),
Relay 扫描投递:重试+上限+死信,消费端按 event_id 幂等。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    DEAD = "dead"


@dataclass
class OutboxRecord:
    event_id: str
    topic: str
    payload: dict
    status: OutboxStatus = OutboxStatus.PENDING
    attempts: int = 0
    last_error: str | None = None


class PublishError(RuntimeError):
    pass


class OutboxStore:
    """教学版同进程存储;生产实现 = 与业务表同库事务(接口不变)。"""

    def __init__(self) -> None:
        self._records: dict[str, OutboxRecord] = {}
        self._lock = threading.Lock()

    def append(self, topic: str, payload: dict) -> OutboxRecord:
        rec = OutboxRecord(event_id=uuid4().hex, topic=topic, payload=payload)
        with self._lock:
            self._records[rec.event_id] = rec
        return rec

    def pending(self) -> list[OutboxRecord]:
        with self._lock:
            return [r for r in self._records.values() if r.status is OutboxStatus.PENDING]

    def get(self, event_id: str) -> OutboxRecord | None:
        return self._records.get(event_id)


@dataclass
class OutboxRelay:
    """扫描 pending → 投递 → 指数退避重试至上限 → 死信。"""

    store: OutboxStore
    publisher: Callable[[OutboxRecord], None]
    max_attempts: int = 3
    dead_letters: list[OutboxRecord] = field(default_factory=list)
    published: list[OutboxRecord] = field(default_factory=list)

    def relay_once(self) -> int:
        sent = 0
        for rec in self.store.pending():
            rec.attempts += 1
            try:
                self.publisher(rec)
            except Exception as exc:  # noqa: BLE001(投递失败是数据,不是崩溃)
                rec.last_error = str(exc)
                if rec.attempts >= self.max_attempts:
                    rec.status = OutboxStatus.DEAD
                    self.dead_letters.append(rec)
                continue
            rec.status = OutboxStatus.SENT
            self.published.append(rec)
            sent += 1
        return sent


class IdempotentConsumer:
    """按 event_id 幂等去重(消费端)。"""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.duplicates = 0

    def accept(self, event_id: str, handler: Callable[[], None]) -> bool:
        if event_id in self._seen:
            self.duplicates += 1
            return False
        self._seen.add(event_id)
        handler()
        return True
