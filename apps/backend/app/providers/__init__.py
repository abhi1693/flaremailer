"""Outbound email provider adapters."""

from app.providers.cloudflare import CloudflareEmailProvider

__all__ = ["CloudflareEmailProvider"]
