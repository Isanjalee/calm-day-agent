# calm-day-agent 🌿

Calm Day Agent is a gentle AI assistant that helps you **plan your day**, **manage tasks**, and **stay aligned** with a calm vibe.  
It runs locally on your computer, saves your plan/tasks to a local file, and can **email your daily plan** to you (and someone you care about).

> Note: This version uses **Groq (cloud LLM)** for fast responses. Your data (tasks/plan) is stored locally in `memory.json`.  
> If you want a fully offline version later, you can swap the LLM backend (e.g., local models).

---

## Features ✨

- ✅ **Day planning** (work + exercise + study + breaks)  
- ✅ **Task management** (add / list / mark done)  
- ✅ **Plan memory** (saved locally in `memory.json`)  
- ✅ **Email your plan** (Gmail App Password via SMTP)  
- ✅ **Safe for GitHub** (secrets kept in `.env`, ignored by git)

---

## Commands (What you can type)

### Day planning
- `Plan my day calmly. I work 8am–5pm. I want 1 hour exercise and 2 hours study.`
- `Show my plan`
- `plan` (shortcut)

### Tasks
- `Save this task: reply to emails`
- `Show my tasks`
- `Mark task 1 as done`

### Email
- `Email my plan`
- `Email this message: Hi Dulan, today I built my first AI agent 💚`

---

## Requirements

- Windows 10/11
- Python 3.10+ (recommended)
- A Groq API key
- A Gmail account with **App Password** enabled (for sending email)

---

## Setup (Windows)

### 1) Clone the repo
```bash
git clone https://github.com/Isanjalee/calm-day-agent.git
cd calm-day-agent
2) Create & activate virtual environment
powershell
Copy code
python -m venv .venv
.\.venv\Scripts\Activate.ps1
3) Install dependencies
powershell
Copy code
pip install groq python-dotenv rich
4) Create a .env file (IMPORTANT)
Create a file named .env in the project root:

env
Copy code
GROQ_API_KEY=your_groq_key_here

EMAIL_ADDRESS=yourgmail@gmail.com
EMAIL_APP_PASSWORD=your_gmail_app_password_here

# Comma-separated recipients (you + friend/friend etc.)
TO_EMAILS=you@gmail.com,friend@gmail.com
✅ .env is ignored by git (safe)
