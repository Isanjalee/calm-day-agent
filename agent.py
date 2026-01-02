import json
import re
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

import tools
from llm_groq import ask_groq
from emailer import send_email

load_dotenv()
console = Console()

PLANNER_SYSTEM = """
You are "Calm Day", a gentle daily planning assistant.
Tone: calm, supportive, minimal. Avoid too many questions.
Timezone: Asia/Colombo.

TASK:
Generate a COMPLETE DAILY PLAN as a single JSON object (ONLY JSON, no extra text).

JSON format MUST be:
{
  "date": "YYYY-MM-DD",
  "summary": "1-2 lines",
  "top_3": ["...", "...", "..."],
  "schedule": [
    {"time":"06:30","title":"Wake + water","duration_min":10},
    {"time":"08:00","title":"Work block","duration_min":240}
  ],
  "notes": ["..."]
}

Defaults (use if user doesn't specify):
- Wake 06:30
- Work 08:00–17:00 if user says 8–5
- Exercise 18:30–19:30 (1 hour)
- Dinner 19:45–20:15 (single dinner only)
- Study 20:15–21:15 and 21:30–22:30 (2 hours total with a short break)
- Wind-down 22:30–23:00
- Sleep 23:00

Rules:
- Do NOT ask follow-up questions unless a critical detail is missing.
- Keep the schedule realistic and calm (add short breaks).
- Output ONLY JSON.
"""

HELP_TEXT = """Try:
• Plan my day calmly. I work 8am–5pm. I want 1 hour exercise and 2 hours study.
• Show my plan
• Save this task: reply to emails
• Show my tasks
• Mark task 1 as done
• Email my plan
• Email this message: (your message)
"""

def extract_json_object(text: str):
    """Extract first JSON object from model output."""
    if not text:
        return None
    t = text.strip()

    # Fast path: entire output is JSON
    if t.startswith("{") and t.endswith("}"):
        try:
            return json.loads(t)
        except Exception:
            pass

    # Robust: from first '{' to last '}'
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = t[start:end+1]
        try:
            return json.loads(candidate)
        except Exception:
            return None

    return None

def is_valid_plan(plan: dict) -> bool:
    if not isinstance(plan, dict):
        return False
    if not plan.get("date"):
        return False
    if not isinstance(plan.get("schedule"), list) or len(plan["schedule"]) == 0:
        return False
    return True

def fallback_plan(today: str):
    """Safe fallback if model JSON fails."""
    return {
        "date": today,
        "summary": "A calm, balanced day: work, movement, study.",
        "top_3": ["Work 8am–5pm", "1 hour exercise", "2 hours study"],
        "schedule": [
            {"time":"06:30","title":"Wake + water","duration_min":10},
            {"time":"06:40","title":"Slow start (wash/tea)","duration_min":30},
            {"time":"07:10","title":"Breakfast / prep","duration_min":30},
            {"time":"08:00","title":"Work block","duration_min":240},
            {"time":"12:00","title":"Lunch break","duration_min":60},
            {"time":"13:00","title":"Work block","duration_min":240},
            {"time":"17:00","title":"Finish work","duration_min":0},
            {"time":"18:30","title":"Exercise","duration_min":60},
            {"time":"19:45","title":"Dinner","duration_min":30},
            {"time":"20:15","title":"Study block 1","duration_min":60},
            {"time":"21:15","title":"Break","duration_min":15},
            {"time":"21:30","title":"Study block 2","duration_min":60},
            {"time":"22:30","title":"Wind-down","duration_min":30},
            {"time":"23:00","title":"Sleep","duration_min":0},
        ],
        "notes": ["One step at a time.", "Keep it gentle, not perfect."]
    }

def render_plan(plan: dict):
    if not plan:
        console.print(Panel("No plan saved yet. Say: 'Plan my day...'", title="🗓️ Daily Plan", subtitle="calm mode"))
        return

    title = f"🗓️ Daily Plan — {plan.get('date','')}"
    summary = plan.get("summary", "")
    top3 = plan.get("top_3", [])
    schedule = plan.get("schedule", [])
    notes = plan.get("notes", [])

    text = Text()
    if summary:
        text.append(summary + "\n\n")

    if top3:
        text.append("Top 3:\n")
        for i, item in enumerate(top3, 1):
            text.append(f"  {i}. {item}\n")
        text.append("\n")

    if schedule:
        text.append("Schedule:\n")
        for item in schedule:
            tm = item.get("time","")
            ttl = item.get("title","")
            dur = item.get("duration_min","")
            text.append(f"  {tm}  {ttl} ({dur} min)\n")
        text.append("\n")

    if notes:
        text.append("Notes:\n")
        for n in notes:
            text.append(f"  • {n}\n")

    console.print(Panel(text, title=title, subtitle="keep it light • keep it moving"))

def format_plan_for_email(plan: dict) -> str:
    if not plan:
        return "No plan saved yet."

    lines = []
    lines.append(f"🌿 Calm Day — Daily Plan ({plan.get('date','')})")
    lines.append("")
    if plan.get("summary"):
        lines.append(plan["summary"])
        lines.append("")

    if plan.get("top_3"):
        lines.append("Top 3:")
        for i, t in enumerate(plan["top_3"], 1):
            lines.append(f"{i}. {t}")
        lines.append("")

    if plan.get("schedule"):
        lines.append("Schedule:")
        for item in plan["schedule"]:
            lines.append(f"{item.get('time','')} - {item.get('title','')} ({item.get('duration_min','')} min)")
        lines.append("")

    if plan.get("notes"):
        lines.append("Notes:")
        for n in plan["notes"]:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("🤍 One step at a time.")
    return "\n".join(lines)

def main():
    console.print(Panel(
        "Calm Day Agent (Groq • Email + Scheduling)\nType 'exit' to quit.",
        title="🌿 Welcome",
        subtitle="calm planning mode"
    ))

    while True:
        user_raw = Prompt.ask("YOU")
        user = user_raw.strip()

        if user.lower() in ("exit", "quit"):
            break

        ul = user.lower().strip()

        # ---------- TASK COMMANDS (deterministic) ----------
        m = re.match(r"^\s*save this task\s*:\s*(.+)$", user, flags=re.IGNORECASE)
        if m:
            result = tools.add_task(m.group(1))
            console.print(Panel(str(result), title="✅ Done", subtitle="task saved"))
            continue

        if ul in ("show my tasks", "show tasks", "tasks", "list tasks"):
            console.print(Panel(tools.list_tasks(), title="📌 Tasks", subtitle="small steps"))
            continue

        m = re.search(r"\bmark\s+task\s+(\d+)\s+as\s+done\b", ul)
        if m:
            idx = int(m.group(1))
            console.print(Panel(tools.mark_done(idx), title="✅ Done", subtitle="updated"))
            continue

        # ---------- PLAN COMMANDS (deterministic) ----------
        if ul in ("show my plan", "show plan", "plan"):
            render_plan(tools.get_plan())
            continue

        if "plan my day" in ul:
            today = datetime.now().strftime("%Y-%m-%d")
            prefs = tools.get_prefs()
            tasks_text = tools.list_tasks()

            prompt = f"""{PLANNER_SYSTEM}

TODAY: {today}

USER_MESSAGE:
{user}

PREFERENCES_JSON:
{json.dumps(prefs, ensure_ascii=False)}

CURRENT_TASKS:
{tasks_text}

Output ONLY the JSON plan.
"""
            raw = ask_groq(prompt)
            plan = extract_json_object(raw)
            if not is_valid_plan(plan):
                plan = fallback_plan(today)

            tools.save_plan(plan)
            console.print(Panel("Daily plan saved.", title="✅ Done", subtitle="saved"))
            render_plan(tools.get_plan())
            continue

        # ---------- EMAIL COMMANDS ----------
        if ul in ("email my plan", "send my plan"):
            plan = tools.get_plan()
            body = format_plan_for_email(plan)
            result = send_email(subject="🌿 Calm Day — Daily Plan", body=body)
            console.print(Panel(result, title="📧 Email", subtitle="sent"))
            continue

        m = re.match(r"^\s*email this message\s*:\s*(.+)$", user, flags=re.IGNORECASE)
        if m:
            msg = m.group(1).strip()
            subject = "🌿 A note from my AI agent"
            body = msg + "\n\n—\nSent by Calm Day Agent 🤍"
            result = send_email(subject=subject, body=body)
            console.print(Panel(result, title="📧 Email", subtitle="sent"))
            continue

        # ---------- FALLBACK: calm help / chat ----------
        console.print(Panel(HELP_TEXT, title="ℹ️ Help", subtitle="commands"))

if __name__ == "__main__":
    main()
