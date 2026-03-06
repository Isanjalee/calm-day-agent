from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from config import AppConfig


def _escape_ics(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\n", r"\n")
    )


def _slugify(value: str) -> str:
    cleaned = []
    for char in (value or "").lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "shared-activity"


def _parse_datetime(plan_date: str, time_value: str, timezone_name: str) -> datetime | None:
    if not plan_date or not time_value:
        return None

    try:
        tzinfo = ZoneInfo(timezone_name)
        naive = datetime.strptime(f"{plan_date} {time_value}", "%Y-%m-%d %H:%M")
        return naive.replace(tzinfo=tzinfo)
    except Exception:
        return None


def _normalize_participants(item: dict) -> list[str]:
    raw = (
        item.get("participants")
        or item.get("shared_with")
        or item.get("attendees")
        or []
    )

    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    participants = []
    seen = set()
    for value in raw:
        person = str(value).strip()
        if not person:
            continue
        key = person.lower()
        if key in seen:
            continue
        seen.add(key)
        participants.append(person)
    return participants


def _includes_me_and_partner(participants: list[str], config: AppConfig) -> bool:
    lowered = {person.lower() for person in participants}
    me_labels = {"me", "myself", config.user_name.lower()}
    partner_labels = {"boyfriend", "partner", config.partner_name.lower()}
    return bool(lowered & me_labels) and bool(lowered & partner_labels)


def _is_shared_event(item: dict, config: AppConfig) -> bool:
    if item.get("calendar_invite") is True or item.get("shared") is True:
        return True

    participants = _normalize_participants(item)
    if _includes_me_and_partner(participants, config):
        return True

    haystack = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("notes", "")),
            " ".join(participants),
        ]
    ).lower()
    return any(keyword.lower() in haystack for keyword in config.shared_activity_keywords)


def extract_shared_events(plan: dict, config: AppConfig) -> list[dict]:
    events = []
    plan_date = str(plan.get("date", "")).strip()
    schedule = plan.get("schedule", [])
    if not isinstance(schedule, list):
        return events

    for item in schedule:
        if not isinstance(item, dict) or not _is_shared_event(item, config):
            continue

        start_at = _parse_datetime(plan_date, str(item.get("time", "")).strip(), config.timezone)
        if start_at is None:
            continue

        try:
            duration_min = int(item.get("duration_min", 0))
        except (TypeError, ValueError):
            duration_min = 0
        if duration_min <= 0:
            duration_min = 30

        end_at = start_at + timedelta(minutes=duration_min)
        participants = _normalize_participants(item)
        if not participants:
            participants = [config.user_name, config.partner_name]

        events.append(
            {
                "title": str(item.get("title", "Shared activity")).strip() or "Shared activity",
                "start_at": start_at,
                "end_at": end_at,
                "participants": participants,
                "description": str(item.get("notes", "")).strip(),
            }
        )

    return events


def build_calendar_attachments(plan: dict, config: AppConfig) -> list[dict[str, str]]:
    attachments = []
    shared_events = extract_shared_events(plan, config)

    for index, event in enumerate(shared_events, 1):
        attendees = []
        if config.sender_email:
            attendees.append((config.user_name, config.sender_email))

        recipient_emails = config.shared_event_recipients or config.plan_recipients
        for email in recipient_emails:
            attendees.append((config.partner_name, email))

        attendees_lines = []
        seen = set()
        for name, email in attendees:
            key = email.lower()
            if key in seen or not email:
                continue
            seen.add(key)
            attendees_lines.append(
                "ATTENDEE;CN={name};ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{email}".format(
                    name=_escape_ics(name),
                    email=email,
                )
            )

        description = event["description"] or "Shared activity from Calm Day."
        description += "\nParticipants: " + ", ".join(event["participants"])

        uid = f"{uuid4()}@calmday"
        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        start_value = event["start_at"].strftime("%Y%m%dT%H%M%S")
        end_value = event["end_at"].strftime("%Y%m%dT%H%M%S")

        lines = [
            "BEGIN:VCALENDAR",
            "PRODID:-//Calm Day Agent//EN",
            "VERSION:2.0",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;TZID={config.timezone}:{start_value}",
            f"DTEND;TZID={config.timezone}:{end_value}",
            f"SUMMARY:{_escape_ics(event['title'])}",
            f"DESCRIPTION:{_escape_ics(description)}",
            "STATUS:CONFIRMED",
            "SEQUENCE:0",
        ]

        if config.sender_email:
            lines.append(
                "ORGANIZER;CN={name}:mailto:{email}".format(
                    name=_escape_ics(config.user_name),
                    email=config.sender_email,
                )
            )

        lines.extend(attendees_lines)
        lines.extend(
            [
                "BEGIN:VALARM",
                f"TRIGGER:-PT{max(config.calendar_alert_minutes, 0)}M",
                "ACTION:DISPLAY",
                "DESCRIPTION:Reminder",
                "END:VALARM",
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        )

        attachments.append(
            {
                "filename": f"{index:02d}-{_slugify(event['title'])}.ics",
                "content": "\r\n".join(lines) + "\r\n",
            }
        )

    return attachments
