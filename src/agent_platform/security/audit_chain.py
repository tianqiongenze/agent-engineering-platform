"""审计日志防篡改:哈希链(审计 R11 缺口落地)。

每条审计事件附加 chain_hash = SHA256(prev_hash ‖ canonical(event)),
任何中间篡改都会使后续校验断裂 —— append-only 语义的进程内等价物。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from agent_platform.tools.runtime import AuditBus, AuditEvent

_GENESIS = "0" * 64


def _canonical(event: AuditEvent, prev_hash: str) -> str:
    body: dict[str, Any] = event.model_dump()
    body["chain_prev"] = prev_hash
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class ChainedAuditBus(AuditBus):
    """包装任意 AuditBus:落链后再转发底层总线。"""

    def __init__(self, inner: AuditBus) -> None:
        self.inner = inner
        self._prev = _GENESIS
        self.chain: list[tuple[str, str]] = []  # (event_id, chain_hash)

    def publish(self, event: AuditEvent) -> None:
        digest = hashlib.sha256(_canonical(event, self._prev).encode()).hexdigest()
        event.meta = {**(event.meta or {}), "chain_hash": digest, "chain_prev": self._prev}
        self.inner.publish(event)
        self.chain.append((event.event_id, digest))
        self._prev = digest

    def verify_records(self, records: list[AuditEvent]) -> tuple[bool, str | None]:
        prev = _GENESIS
        for ev in records:
            expected = ev.meta.get("chain_prev")
            if expected != prev:
                return False, ev.event_id
            if (
                ev.meta.get("chain_hash")
                != hashlib.sha256(_canonical(_strip_chain(ev), prev).encode()).hexdigest()
            ):
                return False, ev.event_id
            prev = ev.meta["chain_hash"]
        return True, None


def _strip_chain(event: AuditEvent) -> AuditEvent:
    clone = event.model_copy(deep=True)
    clone.meta = {
        k: v for k, v in (clone.meta or {}).items() if k not in ("chain_hash", "chain_prev")
    }
    return clone
