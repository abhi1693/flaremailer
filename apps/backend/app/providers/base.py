from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class OutboundMailbox:
    email: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    message_id: str
    sender: OutboundMailbox
    to: list[OutboundMailbox]
    cc: list[OutboundMailbox] = field(default_factory=list)
    bcc: list[OutboundMailbox] = field(default_factory=list)
    reply_to: OutboundMailbox | None = None
    subject: str = ""
    html: str | None = None
    text: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderResult:
    message_id: str | None
    raw_response: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProviderCredentials:
    account_id: str
    api_token: str = field(repr=False)


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        retriable: bool = False,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retriable = retriable
        self.raw_response = raw_response


class EmailProvider(Protocol):
    async def send(
        self, message: OutboundMessage, credentials: ProviderCredentials
    ) -> ProviderResult: ...

    async def aclose(self) -> None: ...
