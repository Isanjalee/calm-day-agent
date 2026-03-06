import re

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

import tools
from config import load_config
from planner_service import format_plan_for_email, generate_plan, normalize_plan, send_plan_email

load_dotenv()
console = Console()

HELP_TEXT = """Try:
- Plan my day around work from 9 to 5, a gym session, and dinner with my boyfriend
- Show my plan
- Save this task: reply to emails
- Show my tasks
- Mark task 1 as done
- Email my plan
"""


def render_plan(plan: dict):
    if not plan:
        console.print(Panel("No plan saved yet. Say: 'Plan my day...'", title="Daily Plan"))
        return

    text = Text()
    if plan.get("summary"):
        text.append(plan["summary"] + "\n\n")

    if plan.get("top_3"):
        text.append("Top 3:\n")
        for index, item in enumerate(plan["top_3"], 1):
            text.append(f"  {index}. {item}\n")
        text.append("\n")

    if plan.get("schedule"):
        text.append("Schedule:\n")
        for item in plan["schedule"]:
            participants = item.get("participants", [])
            label = f" [{', '.join(participants)}]" if participants else ""
            if item.get("calendar_invite"):
                label += " [invite]"
            text.append(
                f"  {item.get('time', '')}  {item.get('title', '')} "
                f"({item.get('duration_min', '')} min){label}\n"
            )
        text.append("\n")

    if plan.get("notes"):
        text.append("Notes:\n")
        for note in plan["notes"]:
            text.append(f"  - {note}\n")

    console.print(Panel(text, title=f"Daily Plan - {plan.get('date', '')}"))


def should_auto_send(user_input: str) -> bool:
    lowered = user_input.lower()
    return any(
        phrase in lowered
        for phrase in (
            "send it",
            "email it",
            "send to my boyfriend",
            "send to my partner",
            "email my boyfriend",
            "email my partner",
        )
    )


def main():
    console.print(Panel("Calm Day Agent\nType 'exit' to quit.", title="Welcome"))

    while True:
        user = Prompt.ask("YOU").strip()
        if user.lower() in ("exit", "quit"):
            break

        lowered = user.lower()
        config = load_config()

        save_task_match = re.match(r"^\s*save this task\s*:\s*(.+)$", user, flags=re.IGNORECASE)
        if save_task_match:
            console.print(Panel(tools.add_task(save_task_match.group(1)), title="Done"))
            continue

        if lowered in ("show my tasks", "show tasks", "tasks", "list tasks"):
            console.print(Panel(tools.list_tasks(), title="Tasks"))
            continue

        mark_done_match = re.search(r"\bmark\s+task\s+(\d+)\s+as\s+done\b", lowered)
        if mark_done_match:
            console.print(Panel(tools.mark_done(int(mark_done_match.group(1))), title="Done"))
            continue

        if lowered in ("show my plan", "show plan", "plan"):
            render_plan(tools.get_plan())
            continue

        if "plan my day" in lowered:
            plan = generate_plan(user, config, prefs=tools.get_prefs())
            tools.save_plan(plan)
            render_plan(plan)
            if should_auto_send(user):
                console.print(Panel(send_plan_email(plan, config), title="Email"))
            else:
                console.print(Panel("Daily plan saved.", title="Done"))
            continue

        if lowered in ("email my plan", "send my plan"):
            plan = normalize_plan(tools.get_plan(), config)
            console.print(Panel(send_plan_email(plan, config), title="Email"))
            continue

        if lowered in ("preview plan email", "show plan email"):
            plan = normalize_plan(tools.get_plan(), config)
            console.print(Panel(format_plan_for_email(plan, config), title="Email Preview"))
            continue

        console.print(Panel(HELP_TEXT, title="Help"))


if __name__ == "__main__":
    main()
