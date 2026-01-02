import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(subject: str, body: str) -> str:
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_APP_PASSWORD")
    recipients = os.getenv("TO_EMAILS")

    if not sender or not password or not recipients:
        return "Email settings missing. Check .env: EMAIL_ADDRESS, EMAIL_APP_PASSWORD, TO_EMAILS"

    to_emails = [e.strip() for e in recipients.split(",") if e.strip()]
    if not to_emails:
        return "TO_EMAILS is empty."

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, to_emails, msg.as_string())
        return "Email sent successfully 💌"
    except Exception as e:
        return f"Failed to send email: {e}"
