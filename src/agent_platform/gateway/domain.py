"""BC1 · LLM Gateway 域模型(阶段一)。

设计要点:
- Usage.total_tokens 为派生值(不变量由校验器保证,不可外部注入);
- role 受 Literal 约束,脏数据在入口即被拦截(防御式编程);
- response_schema 预留结构化输出能力(M1 后段接入)。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: Role
    content: str

    @model_validator(mode="after")
    def _content_not_blank(self) -> ChatMessage:
        if not self.content.strip():
            raise ValueError("message content must not be blank")
        return self


class Usage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(default=0, ge=0, init=False)

    @model_validator(mode="after")
    def _derive_total(self) -> Usage:
        # total 由两分量派生,外部传入值一律被覆盖(不变量)
        object.__setattr__(self, "total_tokens", self.prompt_tokens + self.completion_tokens)
        return self


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 1024
    response_schema: dict | None = None


class ChatResponse(BaseModel):
    model: str
    content: str
    usage: Usage
    latency_ms: float = 0.0
    finish_reason: str = "stop"
