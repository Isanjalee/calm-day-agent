from datetime import datetime
from textwrap import dedent

from config import AppConfig
from emailer import send_email
from pdf_utils import build_learning_note_pdf


def _partner_display_name(config: AppConfig) -> str:
    name = (config.partner_name or "").strip()
    return name if name and name.lower() != "boyfriend" else "Dulan"


def _author_display_name(config: AppConfig) -> str:
    return "Chooty"


def _learning_note_recipients(config: AppConfig) -> list[str]:
    recipients: list[str] = []
    if config.partner_email:
        recipients.append(config.partner_email)
    elif config.plan_recipients:
        recipients.extend(config.plan_recipients)
    if config.sender_email:
        recipients.append(config.sender_email)

    deduped: list[str] = []
    seen = set()
    for item in recipients:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def format_learning_note_email(title: str, config: AppConfig) -> tuple[str, str]:
    partner_name = _partner_display_name(config)
    author_name = _author_display_name(config)
    subject = f"Learning note for {partner_name}"
    body = dedent(
        f"""\
        Hi {partner_name} \U0001F427,

        Today I learned new things and wanted to share them with you.
        I attached my learning note as a PDF so you can read it when you have time.

        Title: {title}

        With love \u2764\ufe0f,
        Your {author_name} \U0001F43C
        """
    ).strip()
    return subject, body


def send_learning_note_email(document: dict, config: AppConfig) -> str:
    if not isinstance(document, dict):
        return "Learning note was missing."

    title = str(document.get("title", "")).strip() or "Learning Note"
    content = str(document.get("content", "")).strip()
    if not content:
        return "Learning note content was empty."

    generated_at = None
    updated_at = str(document.get("updated_at", "")).strip()
    if updated_at:
        try:
            generated_at = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            generated_at = None

    partner_name = _partner_display_name(config)
    author_name = _author_display_name(config)
    subject, body = format_learning_note_email(title, config)
    file_attachments: list[dict[str, bytes | str]] = []
    fallback_reason = ""
    try:
        pdf_bytes = build_learning_note_pdf(
            title=title,
            content=content,
            author_name=author_name,
            partner_name=partner_name,
            generated_at=generated_at,
        )
        safe_name = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-") or "learning-note"
        filename = f"{safe_name}.pdf"
        file_attachments.append({"filename": filename, "content": pdf_bytes})
    except Exception as exc:
        fallback_reason = str(exc).strip()
        body = (
            f"{body}\n\n"
            "PDF attachment could not be generated this time, so I included the learning note below.\n\n"
            f"{content}"
        )

    result = send_email(
        subject,
        body,
        sender=config.sender_email,
        password=config.email_password,
        recipients=_learning_note_recipients(config),
        file_attachments=file_attachments,
    )
    if fallback_reason and result.lower().startswith("email sent"):
        return f"{result} PDF generation failed, so the note was sent in the email body instead."
    return result
