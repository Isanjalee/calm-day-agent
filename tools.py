import json
from pathlib import Path
from datetime import datetime

MEM_FILE = Path("memory.json")

def _load_all():
    if not MEM_FILE.exists():
        return {"tasks": [], "plan": {}, "prefs": {}}
    try:
        return json.loads(MEM_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": [], "plan": {}, "prefs": {}}

def _save_all(data):
    MEM_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def add_task(text: str) -> str:
    data = _load_all()
    txt = (text or "").strip()
    if not txt:
        return "Task text was empty."
    data["tasks"].append({
        "text": txt,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "done": False
    })
    _save_all(data)
    return "Task saved."

def list_tasks() -> str:
    data = _load_all()
    tasks = data.get("tasks", [])
    if not tasks:
        return "No tasks yet."
    lines = []
    for i, t in enumerate(tasks, 1):
        mark = "✅" if t.get("done") else "⬜"
        lines.append(f"{i}. {mark} {t.get('text')}")
    return "\n".join(lines)

def mark_done(index: int) -> str:
    data = _load_all()
    tasks = data.get("tasks", [])
    if index < 1 or index > len(tasks):
        return "Invalid task number."
    tasks[index-1]["done"] = True
    _save_all(data)
    return "Marked as done."

def save_plan(plan_json: dict) -> str:
    data = _load_all()
    data["plan"] = plan_json if isinstance(plan_json, dict) else {}
    _save_all(data)
    return "Daily plan saved."

def get_plan() -> dict:
    data = _load_all()
    plan = data.get("plan", {})
    return plan if isinstance(plan, dict) else {}

def set_prefs(prefs: dict) -> str:
    data = _load_all()
    existing = data.get("prefs", {})
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(prefs, dict):
        prefs = {}
    data["prefs"] = {**existing, **prefs}
    _save_all(data)
    return "Preferences saved."

def get_prefs() -> dict:
    data = _load_all()
    prefs = data.get("prefs", {})
    return prefs if isinstance(prefs, dict) else {}
