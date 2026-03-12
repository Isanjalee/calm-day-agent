import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def send_email(
    subject: str,
    body: str,
    *,
    sender: str,
    password: str,
    recipients: list[str],
    calendar_attachments: list[dict[str, str]] | None = None,
    file_attachments: list[dict[str, str]] | None = None,
) -> str:
    if not sender or not password:
        return "Email settings missing. Check .env: EMAIL_ADDRESS and EMAIL_APP_PASSWORD"
    if not recipients:
        return "No email recipients configured."

    msg = MIMEMultipart("mixed")
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for attachment in calendar_attachments or []:
        part = MIMEText(attachment["content"], "calendar", "utf-8")
        part.replace_header(
            "Content-Type",
            (
                'text/calendar; method=REQUEST; charset="utf-8"; '
                f'name="{attachment["filename"]}"'
            ),
        )
        part["Content-Class"] = "urn:content-classes:calendarmessage"
        part["Content-Disposition"] = f'attachment; filename="{attachment["filename"]}"'
        msg.attach(part)

    sent_files = 0
    for attachment in file_attachments or []:
        part = MIMEBase("application", "octet-stream")
        if "content" in attachment:
            payload = attachment.get("content") or b""
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            filename = attachment.get("filename") or "attachment.bin"
        else:
            file_path = Path(str(attachment.get("path", "")))
            if not file_path.exists() or not file_path.is_file():
                continue
            payload = file_path.read_bytes()
            filename = attachment.get("filename") or file_path.name

        part.set_payload(payload)
        encoders.encode_base64(part)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)
        sent_files += 1

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
    except Exception as exc:
        return f"Failed to send email: {exc}"

    invite_count = len(calendar_attachments or [])
    return (
        f"Email sent to {len(recipients)} recipient(s)"
        f" with {invite_count} calendar invite(s)"
        f" and {sent_files} file attachment(s)."
    )
