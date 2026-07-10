from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.providers.base import (
    OutboundMailbox,
    OutboundMessage,
    ProviderCredentials,
    ProviderError,
    ProviderResult,
)


class CloudflareEmailProvider:
    """Cloudflare Email Service REST adapter.

    The public-beta endpoint accepts a message and returns Cloudflare's immediate send
    result. A successful response means accepted by the service; it is not evidence of
    downstream inbox delivery.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.cloudflare_timeout_seconds)
        )

    async def send(
        self, message: OutboundMessage, credentials: ProviderCredentials
    ) -> ProviderResult:
        endpoint = (
            f"{self._settings.cloudflare_api_base_url.rstrip('/')}"
            f"/accounts/{quote(credentials.account_id, safe='')}/email/sending/send"
        )
        headers = {
            "Authorization": f"Bearer {credentials.api_token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "from": _mailbox_payload(message.sender),
            "to": [_mailbox_payload(mailbox) for mailbox in message.to],
            "subject": message.subject,
        }
        if message.cc:
            payload["cc"] = [_mailbox_payload(mailbox) for mailbox in message.cc]
        if message.bcc:
            payload["bcc"] = [_mailbox_payload(mailbox) for mailbox in message.bcc]
        if message.reply_to:
            payload["reply_to"] = _mailbox_payload(message.reply_to)
        if message.html is not None:
            payload["html"] = message.html
        if message.text is not None:
            payload["text"] = message.text

        try:
            response = await self._client.post(endpoint, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError(
                "Cloudflare Email Service is temporarily unreachable",
                code="provider_network_error",
                retriable=True,
            ) from exc

        raw = _response_payload(response)
        if response.status_code >= 400:
            retriable = response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
            raise ProviderError(
                _cloudflare_error_message(raw, response.status_code),
                code=f"provider_http_{response.status_code}",
                retriable=retriable,
                raw_response=raw,
            )

        if raw.get("success") is False:
            raise ProviderError(
                _cloudflare_error_message(raw, response.status_code),
                code="provider_rejected",
                retriable=False,
                raw_response=raw,
            )
        result = raw.get("result")
        if not isinstance(result, dict):
            raise ProviderError(
                "Cloudflare returned an invalid response",
                code="provider_invalid_response",
                retriable=True,
                raw_response=raw,
            )
        permanent_bounces = result.get("permanent_bounces")
        delivered = result.get("delivered")
        queued = result.get("queued")
        if (
            isinstance(permanent_bounces, list)
            and permanent_bounces
            and not (isinstance(delivered, list) and delivered)
            and not (isinstance(queued, list) and queued)
        ):
            raise ProviderError(
                "Cloudflare permanently rejected every recipient",
                code="provider_permanent_bounce",
                retriable=False,
                raw_response=raw,
            )
        message_id = result.get("message_id")
        return ProviderResult(
            message_id=message_id if isinstance(message_id, str) else None,
            raw_response=raw,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _mailbox_payload(mailbox: OutboundMailbox) -> dict[str, str]:
    payload = {"address": mailbox.email}
    if mailbox.name:
        payload["name"] = mailbox.name
    return payload


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"status_code": response.status_code, "body": response.text[:2000]}
    if isinstance(payload, dict):
        return payload
    return {"status_code": response.status_code, "body": payload}


def _cloudflare_error_message(payload: dict[str, Any], status_code: int) -> str:
    errors = payload.get("errors")
    if isinstance(errors, list):
        messages = [item.get("message") for item in errors if isinstance(item, dict)]
        rendered = "; ".join(message for message in messages if isinstance(message, str))
        if rendered:
            return rendered[:2000]
    return f"Cloudflare Email Service returned HTTP {status_code}"
