"""Email content for identity and organization events."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.email import OutboundEmail, render


def _url(path: str) -> str:
    return f"{get_settings().public_app_url.rstrip('/')}{path}"


def invitation(to: str, inviter: str, organization: str, role: str, token: str) -> OutboundEmail:
    url = _url(f"/invite/{token}")
    text, html = render(
        f"Join {organization} on QS Intelligence",
        [f"{inviter} has invited you to join {organization} on QS Intelligence as {role}.",
         "The link works once and expires in 7 days."],
        "Accept invitation", url,
        "If you were not expecting this invitation, you can ignore this email.",
    )
    return OutboundEmail(to=to, subject=f"{inviter} invited you to {organization} on QS Intelligence",
                         text=text, html=html)


def password_reset(to: str, name: str, token: str) -> OutboundEmail:
    url = _url(f"/reset-password/{token}")
    text, html = render(
        "Reset your password",
        [f"Hi {name},", "We received a request to reset your QS Intelligence password. "
         "The link works once and expires in 60 minutes."],
        "Choose a new password", url,
        "If you did not request this, you can ignore this email — your password will not change.",
    )
    return OutboundEmail(to=to, subject="Reset your QS Intelligence password", text=text, html=html)


def password_changed(to: str, name: str) -> OutboundEmail:
    text, html = render(
        "Your password was changed",
        [f"Hi {name},", "Your QS Intelligence password was just changed and all sessions were signed out."],
        "Sign in", _url("/login"),
        "If this wasn't you, reset your password immediately and contact your administrator.",
    )
    return OutboundEmail(to=to, subject="Your QS Intelligence password was changed", text=text, html=html)
