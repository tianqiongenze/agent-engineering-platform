"""JWT 鉴权与租户隔离(审计 R7 缺口落地)。

- HS256 JWT:stdlib 实现(教学展示令牌解剖;生产可换 PyJWT,接口不变)
- tenant_id 进声明,依赖注入层强制(业界共识:中间件层收口而非逐端点)
- X-Tenant-ID 头仅用于开发态;生产必须持证(SEC_JWT_REQUIRED=1)
- /metrics 保护:同栈校验(业界:指标端点泄露运维细节须防护)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from contextvars import ContextVar

from pydantic import BaseModel

_tenant_ctx: ContextVar[str] = ContextVar("tenant_id", default="default")


class AuthError(PermissionError):
    pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class JwtCodec:
    """HS256 签发的最小 JWT:header.payload.signature。"""

    def __init__(self, secret: str, issuer: str = "agent-platform", ttl_s: int = 3600) -> None:
        self.secret = secret.encode()
        self.issuer = issuer
        self.ttl = ttl_s

    def issue(self, *, subject: str, tenant_id: str, role: str = "agent") -> str:
        now = int(time.time())
        payload = {
            "sub": subject,
            "tenant_id": tenant_id,
            "role": role,
            "iss": self.issuer,
            "iat": now,
            "exp": now + self.ttl,
        }
        head = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64url(json.dumps(payload).encode())
        sig = _b64url(hmac.new(self.secret, f"{head}.{body}".encode(), hashlib.sha256).digest())
        return f"{head}.{body}.{sig}"

    def verify(self, token: str) -> dict:
        try:
            head_b64, body_b64, sig_b64 = token.split(".")
            expect = hmac.new(
                self.secret, f"{head_b64}.{body_b64}".encode(), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(expect, _b64url_decode(sig_b64)):
                raise AuthError("signature mismatch")
            payload = json.loads(_b64url_decode(body_b64))
        except AuthError:
            raise
        except Exception as exc:  # 结构损坏一律 401 语义
            raise AuthError("malformed token") from exc
        if payload.get("iss") != self.issuer:
            raise AuthError("bad issuer")
        if int(payload.get("exp", 0)) < time.time():
            raise AuthError("token expired")
        if not payload.get("tenant_id"):
            raise AuthError("missing tenant claim")
        return payload


class Principal(BaseModel):
    subject: str
    tenant_id: str
    role: str = "agent"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def current_tenant() -> str:
    return _tenant_ctx.get()


def run_as_tenant(tenant_id: str):
    """上下文传播:进入租户作用域(工具执行/审计自动携带)。"""
    return _tenant_ctx.set(tenant_id)


def reset_tenant(token) -> None:
    _tenant_ctx.reset(token)


def authenticate(
    authorization_header: str | None,
    codec: JwtCodec,
    *,
    required: bool = True,
    dev_tenant: str = "default",
) -> Principal:
    """从 Authorization: Bearer 解析主体;开发态可降级(dev_tenant)。"""
    if not authorization_header:
        if required:
            raise AuthError("missing Authorization header")
        return Principal(subject="anonymous", tenant_id=dev_tenant)
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("expected Bearer token")
    claims = codec.verify(token)
    principal = Principal(
        subject=claims["sub"], tenant_id=claims["tenant_id"], role=claims.get("role", "agent")
    )
    _tenant_ctx.set(principal.tenant_id)
    return principal
