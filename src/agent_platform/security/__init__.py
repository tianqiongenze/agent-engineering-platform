"""风控层:JWT/租户、防刷/防重放/防注入、审计哈希链。"""

from agent_platform.security.audit_chain import ChainedAuditBus
from agent_platform.security.auth import (
    AuthError,
    JwtCodec,
    Principal,
    authenticate,
    current_tenant,
    run_as_tenant,
)
from agent_platform.security.guard import (
    InjectionDetected,
    InjectionGuard,
    RateLimitExceeded,
    ReplayDetected,
    ReplayGuard,
    SecurityStack,
    TokenBucketRateLimiter,
)

__all__ = [
    "AuthError",
    "ChainedAuditBus",
    "InjectionDetected",
    "InjectionGuard",
    "JwtCodec",
    "Principal",
    "RateLimitExceeded",
    "ReplayDetected",
    "ReplayGuard",
    "SecurityStack",
    "TokenBucketRateLimiter",
    "authenticate",
    "current_tenant",
    "run_as_tenant",
]
