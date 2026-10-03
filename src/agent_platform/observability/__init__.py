"""可观测性:Prometheus 指标。"""

from agent_platform.observability.metrics import REGISTRY, render_metrics

__all__ = ["REGISTRY", "render_metrics"]
