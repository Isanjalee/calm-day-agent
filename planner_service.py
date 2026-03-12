import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from calendar_utils import build_calendar_attachments, extract_shared_events
from config import AppConfig
from emailer import send_email
from llm_groq import ask_groq


LOVE_IMAGE_PATH = Path(__file__).resolve().parent / "web" / "assets" / "images" / "love1.jpg"


def build_planner_system(config: AppConfig) -> str:
    return f"""
You are "Calm Day", a planning assistant that turns a real user request into a real daily plan.
Tone: calm, modern, practical.
Timezone: {config.timezone}.

Task:
Generate exactly one JSON object and nothing else.

The schedule must come from the user's actual request, not from a canned template.
If the user mentions work hours, study, errands, rest, gym, travel, or shared activities, reflect them directly.
If the user wants a diary or book note, do not generate that here. This planner is only for the day plan.

JSON format:
{{
  "date": "YYYY-MM-DD",
  "summary": "1-2 lines",
  "top_3": ["...", "...", "..."],
  "schedule": [
    {{
      "time": "08:00",
      "title": "Focused work block",
      "duration_min": 120,
      "participants": ["{config.user_name}"],
      "calendar_invite": false
    }},
    {{
      "time": "19:00",
      "title": "Dinner together",
      "duration_min": 90,
      "participants": ["{config.user_name}", "{config.partner_name}"],
      "calendar_invite": true
    }}
  ],
  "notes": ["..."]
}}

Rules:
- Output only valid JSON.
- Include a participants list for every schedule item.
- Use only "{config.user_name}" for solo activities.
- If an activity includes both {config.user_name} and {config.partner_name}, include both names.
- Set calendar_invite to true only for shared activities worth sending as a calendar event.
- Prefer a plan that feels personal to the user input over generic defaults.
- If a key detail is missing, make a light, reasonable assumption instead of asking questions.
""".strip()


def extract_json_object(text: str):
    if not text:
        return None

    candidate = text.strip()
    if candidate.startswith("{") and candidate.endswith("}"):
        try:
            return json.loads(candidate)
        except Exception:
            pass

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except Exception:
            return None

    return None


def _clean_text_list(value, *, limit: int | None = None) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split("\n")]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value]
    else:
        items = []

    cleaned = [item for item in items if item]
    if limit is not None:
        cleaned = cleaned[:limit]
    return cleaned


def _is_valid_time(value: str) -> bool:
    try:
        datetime.strptime(value or "", "%H:%M")
    except ValueError:
        return False
    return True


def _normalize_schedule(schedule, config: AppConfig) -> list[dict]:
    if not isinstance(schedule, list):
        return []

    normalized = []
    for item in schedule:
        if not isinstance(item, dict):
            continue

        time_value = str(item.get("time", "")).strip()
        if not _is_valid_time(time_value):
            continue

        title = str(item.get("title", "")).strip() or "Focus block"
        try:
            duration_min = int(item.get("duration_min", 30))
        except (TypeError, ValueError):
            duration_min = 30
        duration_min = max(duration_min, 0)

        participants = item.get("participants", [config.user_name])
        if isinstance(participants, str):
            participants = [participants]
        if not isinstance(participants, list):
            participants = [config.user_name]

        cleaned_participants = []
        seen = set()
        for name in participants:
            text = str(name).strip()
            if not text:
                continue

            lowered = text.lower()
            if lowered in {"me", "myself", config.user_name.lower()}:
                text = config.user_name
            elif lowered in {"partner", "boyfriend", config.partner_name.lower()}:
                text = config.partner_name

            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned_participants.append(text)

        if not cleaned_participants:
            cleaned_participants = [config.user_name]

        normalized.append(
            {
                "time": time_value,
                "title": title,
                "duration_min": duration_min,
                "participants": cleaned_participants,
                "calendar_invite": bool(item.get("calendar_invite")),
            }
        )

    return normalized


def _display_participants(participants: list[str], config: AppConfig) -> str:
    rendered = []
    for name in participants or []:
        text = str(name).strip()
        lowered = text.lower()
        if lowered == config.user_name.lower():
            rendered.append("Me")
        else:
            rendered.append(text)
    return " & ".join(rendered)


def _partner_display_name(config: AppConfig) -> str:
    return (config.partner_name or "").strip() or "your partner"


def _participant_suffix(participants: list[str], config: AppConfig) -> str:
    names = [str(name).strip().lower() for name in participants or [] if str(name).strip()]
    my_name = config.user_name.lower()
    partner_name = _partner_display_name(config).lower()
    partner_label = _partner_display_name(config)

    has_me = any(name in {"me", "myself", my_name} for name in names)
    has_partner = partner_name in names or "partner" in names or "boyfriend" in names

    if has_me and has_partner:
        return f" | with Me and {partner_label}"
    if has_me or not names:
        return " | solo"
    return f" | with {_display_participants(participants, config)}"


def _schedule_marker(title: str, participants: list[str], config: AppConfig) -> str:
    text = str(title or "").lower()
    participant_names = {str(name).strip().lower() for name in participants or []}
    shared = config.partner_name.lower() in participant_names and config.user_name.lower() in participant_names

    if "work" in text:
        return "[Work]" if not shared else "[Shared]"
    if "study" in text or "learning" in text or "english" in text or "german" in text:
        return "[Study]"
    if "lunch" in text or "dinner" in text or "breakfast" in text:
        return "[Meal]"
    if "worship" in text or "pray" in text:
        return "[Prayer]"
    if "help" in text or "family" in text or "mom" in text:
        return "[Family]"
    if "rest" in text or "quiet" in text or "wait" in text or "wind" in text:
        return "[Rest]"
    if "exercise" in text or "walk" in text or "gym" in text:
        return "[Exercise]"
    if "reset" in text:
        return "[Reset]"
    if shared:
        return "[Shared]"
    return ""


def _format_email_time(value: str) -> str:
    raw = str(value or "").strip()
    match = re.match(r"^(\d{2}):(\d{2})$", raw)
    if not match:
        return raw

    hour = int(match.group(1))
    minute = match.group(2)
    meridiem = "AM"
    if hour >= 12:
        meridiem = "PM"
    hour = hour % 12 or 12
    return f"{hour}:{minute} {meridiem}"


def is_valid_plan(plan: dict) -> bool:
    return (
        isinstance(plan, dict)
        and bool(plan.get("date"))
        and isinstance(plan.get("schedule"), list)
        and len(plan["schedule"]) > 0
    )


def _today_for_timezone(timezone_name: str) -> str:
    try:
        return datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def fallback_plan(today: str, config: AppConfig) -> dict:
    return {
        "date": today,
        "summary": "A first draft for the day. Edit it before saving if needed.",
        "top_3": ["One important task", "One caring habit", "One clear finish line"],
        "schedule": [
            {
                "time": "08:00",
                "title": "Main work block",
                "duration_min": 180,
                "participants": [config.user_name],
                "calendar_invite": False,
            },
            {
                "time": "13:00",
                "title": "Reset and lunch",
                "duration_min": 60,
                "participants": [config.user_name],
                "calendar_invite": False,
            },
            {
                "time": "19:00",
                "title": "Evening together",
                "duration_min": 90,
                "participants": [config.user_name, config.partner_name],
                "calendar_invite": True,
            },
        ],
        "notes": [
            "Adjust the times to match the real shape of your day.",
            "Only shared items will be sent as invites.",
        ],
    }


def normalize_plan(plan: dict, config: AppConfig, *, fallback_date: str | None = None) -> dict:
    today = fallback_date or _today_for_timezone(config.timezone)
    if not isinstance(plan, dict):
        return fallback_plan(today, config)

    normalized = {
        "date": str(plan.get("date", "")).strip() or today,
        "summary": str(plan.get("summary", "")).strip(),
        "top_3": _clean_text_list(plan.get("top_3"), limit=3),
        "schedule": _normalize_schedule(plan.get("schedule"), config),
        "notes": _clean_text_list(plan.get("notes")),
    }

    if not normalized["schedule"]:
        return fallback_plan(normalized["date"], config)

    if not normalized["top_3"]:
        normalized["top_3"] = [normalized["schedule"][0]["title"]]

    return normalized


def generate_plan(user_message: str, config: AppConfig, prefs: dict | None = None) -> dict:
    today = _today_for_timezone(config.timezone)
    prompt = f"""{build_planner_system(config)}

TODAY: {today}

USER_MESSAGE:
{(user_message or "").strip()}

PREFERENCES_JSON:
{json.dumps(prefs or {}, ensure_ascii=False)}

Output only the JSON plan.
"""

    raw = ask_groq(prompt)
    plan = extract_json_object(raw)
    if not is_valid_plan(plan):
        return fallback_plan(today, config)
    return normalize_plan(plan, config, fallback_date=today)


def format_plan_for_email(plan: dict, config: AppConfig) -> str:
    normalized_plan = normalize_plan(plan, config)
    shared_events = extract_shared_events(normalized_plan, config)
    partner_name = _partner_display_name(config)
    lines = [
        f"Hi {partner_name},",
        "",
        "I made a small calm plan for today and wanted to share it with you.",
        "Think of it as a simple roadmap for the day with a bit of focus and a bit of care.",
        "",
        f"Calm Day plan for today ({normalized_plan.get('date', '')})",
        "",
    ]

    if normalized_plan.get("top_3"):
        lines.append("Top 3 for the day")
        lines.append("")
        for index, item in enumerate(normalized_plan["top_3"], 1):
            lines.append(f"{index}. {item}")
        lines.append("")

    lines.append("Schedule")
    lines.append("")
    for item in normalized_plan.get("schedule", []):
        participant_text = _participant_suffix(item.get("participants", []), config)
        marker = _schedule_marker(item.get("title", ""), item.get("participants", []), config)
        marker_suffix = f" {marker}" if marker else ""
        lines.append(
            f"{_format_email_time(item.get('time', ''))} - {item.get('title', '')} "
            f"({item.get('duration_min', '')} min){participant_text}{marker_suffix}"
        )
    lines.append("")

    if normalized_plan.get("notes"):
        lines.append("Notes")
        for note in normalized_plan["notes"]:
            lines.append(f"- {note}")
        if shared_events:
            lines.append("- Only shared items will be sent as calendar invites.")
        lines.append("")
    elif shared_events:
        lines.append("Notes")
        lines.append("- Only shared items will be sent as calendar invites.")
        lines.append("")

    lines.extend(
        [
            "Hope your day goes smoothly too.",
            "",
            "Have a beautiful day.",
            "",
            "Calm Day",
        ]
    )
    return "\n".join(lines)


def send_plan_email(plan: dict, config: AppConfig) -> str:
    validation_error = config.validate_email_settings()
    if validation_error:
        return validation_error

    normalized_plan = normalize_plan(plan, config)
    attachments = build_calendar_attachments(normalized_plan, config)
    file_attachments = []
    if LOVE_IMAGE_PATH.exists():
        file_attachments.append({"path": str(LOVE_IMAGE_PATH), "filename": "love1.jpg"})
    return send_email(
        subject=f"A beautiful little day plan from {config.user_name}",
        body=format_plan_for_email(normalized_plan, config),
        sender=config.sender_email,
        password=config.email_password,
        recipients=config.plan_recipients,
        calendar_attachments=attachments,
        file_attachments=file_attachments,
    )
