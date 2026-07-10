from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinja2 import StrictUndefined, TemplateError, nodes
from jinja2.sandbox import SandboxedEnvironment

from app.errors import abort

_forbidden_nodes = (
    nodes.Include,
    nodes.Extends,
    nodes.Import,
    nodes.FromImport,
    nodes.Call,
    nodes.Macro,
)


@dataclass(frozen=True, slots=True)
class RenderedTemplate:
    subject: str
    html: str | None
    text: str | None


def validate_template(subject: str, html: str | None, text: str | None) -> None:
    for source, autoescape in ((subject, False), (html, True), (text, False)):
        if source is None:
            continue
        environment = _environment(autoescape=autoescape)
        try:
            parsed = environment.parse(source)
        except TemplateError as exc:
            abort(422, "invalid_template", f"Template syntax error: {exc}")
        if any(parsed.find_all(_forbidden_nodes)):
            abort(
                422, "unsafe_template", "Template imports, includes, and inheritance are disabled"
            )


def render_template(
    subject: str,
    html: str | None,
    text: str | None,
    variables: dict[str, Any],
) -> RenderedTemplate:
    validate_template(subject, html, text)
    try:
        rendered_subject = _environment(autoescape=False).from_string(subject).render(variables)
        rendered_html = (
            _environment(autoescape=True).from_string(html).render(variables)
            if html is not None
            else None
        )
        rendered_text = (
            _environment(autoescape=False).from_string(text).render(variables)
            if text is not None
            else None
        )
    except TemplateError as exc:
        abort(422, "template_render_failed", f"Could not render template: {exc}")
    if "\r" in rendered_subject or "\n" in rendered_subject:
        abort(422, "unsafe_subject", "Rendered subject cannot contain line breaks")
    total_size = sum(
        len(value.encode("utf-8")) for value in (rendered_html, rendered_text) if value
    )
    if total_size > 5 * 1024 * 1024:
        abort(413, "rendered_email_too_large", "Rendered email exceeds Cloudflare's 5 MiB limit")
    return RenderedTemplate(rendered_subject, rendered_html, rendered_text)


def _environment(*, autoescape: bool) -> SandboxedEnvironment:
    environment = SandboxedEnvironment(
        undefined=StrictUndefined,
        autoescape=autoescape,
        enable_async=False,
    )
    environment.globals.clear()
    environment.filters.pop("safe", None)
    environment.filters.pop("attr", None)
    return environment
