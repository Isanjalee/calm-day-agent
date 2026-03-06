import os
from dataclasses import dataclass, field


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _read_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class AppConfig:
    sender_email: str
    email_password: str
    user_name: str = "You"
    partner_name: str = "Boyfriend"
    partner_email: str = ""
    timezone: str = "Asia/Colombo"
    calendar_alert_minutes: int = 30
    plan_recipients: list[str] = field(default_factory=list)
    shared_activity_keywords: list[str] = field(default_factory=list)

    @property
    def shared_event_recipients(self) -> list[str]:
        if self.partner_email:
            return [self.partner_email]

        return [
            email
            for email in self.plan_recipients
            if email.lower() != self.sender_email.lower()
        ]

    def validate_email_settings(self) -> str | None:
        if not self.sender_email or not self.email_password:
            return (
                "Email settings missing. Check .env: EMAIL_ADDRESS and "
                "EMAIL_APP_PASSWORD"
            )
        if not self.plan_recipients:
            return (
                "No plan recipients configured. Add PLAN_RECIPIENTS or TO_EMAILS "
                "to .env."
            )
        return None


def load_config() -> AppConfig:
    sender_email = (os.getenv("EMAIL_ADDRESS") or "").strip()
    email_password = (os.getenv("EMAIL_APP_PASSWORD") or "").strip()
    user_name = (os.getenv("USER_NAME") or "You").strip() or "You"
    partner_name = (os.getenv("PARTNER_NAME") or "Boyfriend").strip() or "Boyfriend"
    partner_email = (os.getenv("PARTNER_EMAIL") or "").strip()
    timezone = (os.getenv("APP_TIMEZONE") or "Asia/Colombo").strip() or "Asia/Colombo"

    recipients = _split_csv(os.getenv("PLAN_RECIPIENTS") or os.getenv("TO_EMAILS"))
    if not recipients and sender_email:
        recipients = [sender_email]
    if partner_email:
        recipients.append(partner_email)
    recipients = _dedupe(recipients)

    keywords = _split_csv(os.getenv("SHARED_ACTIVITY_KEYWORDS"))
    if not keywords:
        keywords = [
            "together",
            "shared",
            "date night",
            "team activity",
            "with both of us",
            f"with {partner_name.lower()}",
        ]

    return AppConfig(
        sender_email=sender_email,
        email_password=email_password,
        user_name=user_name,
        partner_name=partner_name,
        partner_email=partner_email,
        timezone=timezone,
        calendar_alert_minutes=_read_int("CALENDAR_ALERT_MINUTES", 30),
        plan_recipients=recipients,
        shared_activity_keywords=keywords,
    )
