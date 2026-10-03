"""Prometheus 指标(可观测性 OSW 缺口落地)。

埋点三原则:
1) 代码注册指标 + 暴露 /metrics(OSW 铁律 ①)
2) 关键链路自动埋点:风控拦截/限流拒绝/缓存命中层级/LLM 调用/工具调用
3) cache_hit 信息透传(禁内部命中外部不可见)
标签基数纪律:仅有限枚举(type/result/layer/provider),禁 user_id 高基数。
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry(auto_describe=True)

SECURITY_BLOCKS = Counter(
    "platform_security_blocks_total", "被拦截的风控事件", ["type"], registry=REGISTRY
)
RATE_LIMIT_REJECTED = Counter(
    "platform_rate_limit_rejected_total", "限流拒绝次数", registry=REGISTRY
)
CACHE_OPERATIONS = Counter(
    "platform_cache_operations_total", "缓存操作", ["layer", "result"], registry=REGISTRY
)
LLM_CALLS = Counter(
    "platform_llm_calls_total", "LLM 调用", ["provider", "result"], registry=REGISTRY
)
LLM_LATENCY = Histogram(
    "platform_llm_latency_seconds",
    "LLM 调用时延",
    ["provider"],
    registry=REGISTRY,
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
)
TOOL_CALLS = Counter("platform_tool_calls_total", "工具调用", ["result"], registry=REGISTRY)
OUTBOX_PUBLISHED = Counter(
    "platform_outbox_published_total", "Outbox 投递", ["result"], registry=REGISTRY
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


# ── 语义化埋点助手(供各模块调用,保持松耦合)────────────────


def track_security_block(block_type: str) -> None:
    SECURITY_BLOCKS.labels(type=block_type).inc()


def track_rate_limit_rejected() -> None:
    RATE_LIMIT_REJECTED.inc()


def track_cache(layer: str, result: str) -> None:
    CACHE_OPERATIONS.labels(layer=layer, result=result).inc()


def track_llm(provider: str, result: str, latency_s: float | None = None) -> None:
    LLM_CALLS.labels(provider=provider, result=result).inc()
    if latency_s is not None:
        LLM_LATENCY.labels(provider=provider).observe(latency_s)


def track_tool(result: str) -> None:
    TOOL_CALLS.labels(result=result).inc()


def track_outbox(result: str) -> None:
    OUTBOX_PUBLISHED.labels(result=result).inc()
