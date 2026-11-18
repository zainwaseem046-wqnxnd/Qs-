"""Outbound email: a small backend abstraction with console, in-memory (tests) and SMTP implementations.

Messages are sent after the database transaction commits. A delivery failure is logged and reported to the
caller (e.g. ``email_sent: false``) but never rolls back the business action that triggered it.
"""

from __future__ import annotations

import html
import logging
import smtplib
import ssl
import threading
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import get_settings

logger = logging.getLogger("qs.email")


@dataclass
class OutboundEmail:
    to: str
    subject: str
    text: str
    html: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


_outbox: list[OutboundEmail] = []
_outbox_lock = threading.Lock()


def outbox() -> list[OutboundEmail]:
    """Messages captured by the memory backend (tests only)."""
    with _outbox_lock:
        return list(_outbox)


def clear_outbox() -> None:
    with _outbox_lock:
        _outbox.clear()


def _build(message: OutboundEmail) -> EmailMessage:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = formataddr((s.email_from_name, s.email_from_address))
    msg["To"] = message.to
    msg["Subject"] = message.subject
    msg["Message-ID"] = make_msgid(domain=s.email_from_address.split("@")[-1])
    for k, v in message.headers.items():
        msg[k] = v
    msg.set_content(message.text)
    if message.html:
        msg.add_alternative(message.html, subtype="html")
    return msg


def send(message: OutboundEmail) -> bool:
    """Send one message. Returns True on success, False on failure (already logged)."""
    s = get_settings()
    if s.email_backend == "memory":
        with _outbox_lock:
            _outbox.append(message)
        return True
    if s.email_backend == "console":
        logger.info("EMAIL (console backend) to=%s subject=%r\n%s", message.to, message.subject, message.text)
        return True
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds) as smtp:
            smtp.starttls(context=context)
            if s.smtp_username and s.smtp_password:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(_build(message))
        return True
    except (smtplib.SMTPException, OSError):
        logger.exception("Email delivery failed (to=%s, subject=%r)", message.to, message.subject)
        return False


def render(title: str, paragraphs: list[str], action_label: str, action_url: str, footer: str) -> tuple[str, str]:
    """Plain-text and minimal HTML bodies. All interpolated values are escaped for HTML."""
    text = "\n\n".join([*paragraphs, f"{action_label}: {action_url}", footer])
    e = html.escape
    body = "".join(f'<p style="margin:0 0 16px">{e(p)}</p>' for p in paragraphs)
    html_body = (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#0d1b2e">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{e(title)}</h1>{body}'
        f'<p style="margin:24px 0"><a href="{e(action_url, quote=True)}" style="background:#1f5fd1;color:#fff;'
        f'padding:10px 18px;border-radius:6px;text-decoration:none;display:inline-block">{e(action_label)}</a></p>'
        f'<p style="font-size:12px;color:#4f5f75">{e(footer)}</p></div>'
    )
    return text, html_body
