"""Notification abstraction — email MVP with log provider for development."""
from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from ai_cio.db.models import NotificationDelivery, User, UserAlert
from ai_cio.settings import (
    EMAIL_FROM,
    EMAIL_PROVIDER,
    NOTIFICATION_EMAIL,
    PRODUCT_ATTRIBUTION,
    PRODUCT_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
)

logger = logging.getLogger(__name__)

FORBIDDEN_PHRASES = (
    "buy now",
    "sell now",
    "guaranteed",
    "risk-free",
    "certain return",
    "this stock will rise",
    "this stock will fall",
    "definitely buy",
    "definitely sell",
)


class EmailProvider(ABC):
    @abstractmethod
    def send(self, *, to: str, subject: str, body: str) -> str:
        ...


class LogEmailProvider(EmailProvider):
    def send(self, *, to: str, subject: str, body: str) -> str:
        logger.info(
            "[EMAIL] To: %s | Subject: %s | Status: generated | body_len=%s",
            to or "(not configured)",
            subject,
            len(body),
        )
        return f"log-{datetime.now(timezone.utc).timestamp()}"


class SMTPEmailProvider(EmailProvider):
    def send(self, *, to: str, subject: str, body: str) -> str:
        msg = EmailMessage()
        msg["From"] = EMAIL_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return f"smtp-{datetime.now(timezone.utc).timestamp()}"


def get_email_provider() -> EmailProvider:
    if EMAIL_PROVIDER == "smtp" and SMTP_HOST:
        return SMTPEmailProvider()
    return LogEmailProvider()


def resolve_notification_recipient(user: User) -> str:
    """Development/test override via NOTIFICATION_EMAIL; otherwise user account email."""
    return NOTIFICATION_EMAIL or (user.email or "")


def validate_email_content(subject: str, body: str) -> list[str]:
    issues = []
    combined = f"{subject} {body}".lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in combined:
            issues.append(f"forbidden_phrase:{phrase}")
    return issues


def build_market_observation_email(
    *,
    user_name: str,
    sector_name: str,
    sector_change: str,
    benchmark_change: str,
    relative_change: str | None,
    exposure_value: str | None,
    exposure_pct: str | None,
    why_surface: list[str],
    considerations: list[str] | None = None,
    analysis_summary: str | None = None,
    missing: list[str],
) -> tuple[str, str]:
    subject = f"{PRODUCT_NAME} Market Observation: {sector_name} sector moved materially"
    rel_line = f"Relative movement: {relative_change} percentage points\n" if relative_change else ""
    exposure_block = ""
    if exposure_value:
        exposure_block = f"Identified {sector_name} exposure:\n₹{exposure_value}"
        if exposure_pct:
            exposure_block += f"\n{exposure_pct}% of identified equity exposure"
        exposure_block += "\n\n"
    why = "\n".join(f"- {line}" for line in why_surface) if why_surface else "- Material sector move with identified exposure."
    review = considerations or [
        "portfolio concentration",
        "investment objective",
        "time horizon",
        "risk willingness and capacity",
        "liquidity needs",
    ]
    review_block = "\n".join(f"- {line}" for line in review)
    missing_block = ""
    if missing:
        missing_block = f"\n{PRODUCT_NAME} currently does not have complete information about:\n" + "\n".join(f"- {m}" for m in missing)
    analysis_block = ""
    if analysis_summary:
        analysis_block = f"\n{PRODUCT_NAME} ANALYSIS\n\n{analysis_summary}\n"
    body = f"""Hi {user_name},

{PRODUCT_NAME} noticed a meaningful movement in the {sector_name} sector.

MARKET

{sector_name}: {sector_change}%
Nifty 50: {benchmark_change}%
{rel_line}
YOUR FINANCIAL PROFILE

{exposure_block}WHY THIS WAS SURFACED

{why}
{analysis_block}
WHAT TO REVIEW

{review_block}

IMPORTANT

This is a market observation, not a buy/sell instruction.

SOURCES

NSE market data
{PRODUCT_NAME} Digital Financial Twin
Relevant authoritative financial education{missing_block}

{PRODUCT_ATTRIBUTION}
"""
    return subject, body


def deliver_alert_email(
    db: Session,
    alert: UserAlert,
    user: User,
    subject: str,
    body: str,
    *,
    recipient: str | None = None,
) -> NotificationDelivery:
    to = recipient or resolve_notification_recipient(user)
    issues = validate_email_content(subject, body)
    if not to:
        delivery = NotificationDelivery(
            alert_id=alert.id,
            channel="email",
            recipient="",
            status="failed",
            subject=subject,
            body_preview=body[:500],
            error="no_recipient",
        )
        db.add(delivery)
        alert.status = "failed"
        return delivery
    if issues:
        delivery = NotificationDelivery(
            alert_id=alert.id,
            channel="email",
            recipient=to,
            status="failed",
            subject=subject,
            body_preview=body[:500],
            error=";".join(issues),
        )
        db.add(delivery)
        alert.status = "failed"
        return delivery
    provider = get_email_provider()
    try:
        msg_id = provider.send(to=to, subject=subject, body=body)
        delivery = NotificationDelivery(
            alert_id=alert.id,
            channel="email",
            recipient=to,
            status="sent",
            provider_message_id=msg_id,
            subject=subject,
            body_preview=body[:500],
            sent_at=datetime.now(timezone.utc),
        )
        alert.status = "sent"
    except Exception as exc:
        delivery = NotificationDelivery(
            alert_id=alert.id,
            channel="email",
            recipient=to,
            status="failed",
            subject=subject,
            body_preview=body[:500],
            error=str(exc),
        )
        alert.status = "failed"
    db.add(delivery)
    return delivery
