# calm-day-agent

Calm Day Agent now includes a local browser UI for three separate workflows:

- `Day Plan`: generate, edit, save, and send only the schedule for the day
- `Diary`: save private journal entries
- `Book`: save longer-form writing or notes

Diary and book content are stored locally but are never included when you send the day plan to your boyfriend.

## Features

- Modern local web UI with tabs for day planning, diary writing, and book drafting
- AI-assisted day-plan generation from your actual prompt
- Editable timeline blocks before saving or sending
- Email delivery for the saved day plan only
- Calendar invite attachments for shared activities in the day plan
- Local storage in `memory.json`

## Requirements

- Windows 10/11
- Python 3.10+
- A Groq API key
- A Gmail account with an App Password

## Setup

1. Create and activate the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install groq python-dotenv rich
```

3. Create `.env` in the project root:

```env
GROQ_API_KEY=your_groq_key_here

EMAIL_ADDRESS=yourgmail@gmail.com
EMAIL_APP_PASSWORD=your_gmail_app_password_here

USER_NAME=Isanjalee
PARTNER_NAME=Dulan
PARTNER_EMAIL=dulan@example.com

PLAN_RECIPIENTS=you@gmail.com,dulan@example.com
APP_TIMEZONE=Asia/Colombo
CALENDAR_ALERT_MINUTES=30
SHARED_ACTIVITY_KEYWORDS=together,shared,date night,team activity,with both of us,with dulan
```

## Run the UI

```powershell
.\.venv\Scripts\python.exe webapp.py
```

Then open:

```text
http://127.0.0.1:8088
```

## How it works

1. Open the `Day Plan` tab.
2. Describe the day you actually want.
3. Click `Generate plan`.
4. Edit the summary, top priorities, timeline blocks, participants, and invite toggles.
5. Click `Save day plan`.
6. Click `Send to <partner>` when you want to email only the day plan.

Use the `Diary` and `Book` tabs for personal writing. Those entries save locally but are not part of the email payload.

## Shared activities and invites

If a schedule block includes both you and your partner and `Invite` is turned on, the app sends an `.ics` calendar attachment with the day-plan email. Gmail and Google Calendar usually recognize these as event invites.

## Files

- `webapp.py`: local HTTP server and API endpoints
- `web/index.html`: browser UI
- `web/assets/app.css`: styling and layout
- `web/assets/app.js`: UI behavior
- `planner_service.py`: plan generation, normalization, and send logic
- `calendar_utils.py`: shared event detection and `.ics` invite generation
- `emailer.py`: Gmail delivery
- `tools.py`: local storage for plan, diary, and book content
- `agent.py`: optional CLI interface

## Security

- Keep secrets only in `.env`
- Do not commit `.env`, `.venv`, or `memory.json`
