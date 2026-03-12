import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parent
MEM_FILE = ROOT_DIR / "memory.json"
DEFAULT_MEMORY = {"tasks": [], "plan": {}, "prefs": {}, "documents": []}


def _load_all():
    if not MEM_FILE.exists():
        return DEFAULT_MEMORY.copy()

    try:
        data = json.loads(MEM_FILE.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_MEMORY.copy()

    if not isinstance(data, dict):
        return DEFAULT_MEMORY.copy()

    return {
        "tasks": data.get("tasks", []),
        "plan": data.get("plan", {}),
        "prefs": data.get("prefs", {}),
        "documents": data.get("documents", []),
    }


def _save_all(data):
    MEM_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_task(text: str) -> str:
    data = _load_all()
    task_text = (text or "").strip()
    if not task_text:
        return "Task text was empty."

    data["tasks"].append(
        {
            "text": task_text,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "done": False,
        }
    )
    _save_all(data)
    return "Task saved."


def list_tasks() -> str:
    data = _load_all()
    tasks = data.get("tasks", [])
    if not tasks:
        return "No tasks yet."

    lines = []
    for index, task in enumerate(tasks, 1):
        mark = "[x]" if task.get("done") else "[ ]"
        lines.append(f"{index}. {mark} {task.get('text')}")
    return "\n".join(lines)


def mark_done(index: int) -> str:
    data = _load_all()
    tasks = data.get("tasks", [])
    if index < 1 or index > len(tasks):
        return "Invalid task number."

    tasks[index - 1]["done"] = True
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


def save_document(kind: str, title: str, content: str, doc_id: str | None = None) -> dict:
    data = _load_all()
    documents = data.get("documents", [])
    if not isinstance(documents, list):
        documents = []

    normalized_kind = (kind or "").strip().lower()
    if normalized_kind not in {"diary", "book"}:
        raise ValueError("Document kind must be 'diary' or 'book'.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item = {
        "id": doc_id or str(uuid4()),
        "kind": normalized_kind,
        "title": (title or "").strip() or normalized_kind.title(),
        "content": (content or "").strip(),
        "updated_at": now,
    }
    if not item["content"]:
        raise ValueError("Document content was empty.")

    for index, existing in enumerate(documents):
        if isinstance(existing, dict) and existing.get("id") == item["id"]:
            item["created_at"] = existing.get("created_at", now)
            documents[index] = item
            break
    else:
        item["created_at"] = now
        documents.append(item)

    data["documents"] = documents
    _save_all(data)
    return item


def list_documents(kind: str | None = None) -> list[dict]:
    data = _load_all()
    documents = data.get("documents", [])
    if not isinstance(documents, list):
        return []

    filtered = []
    for item in documents:
        if not isinstance(item, dict):
            continue
        item_kind = str(item.get("kind", "")).strip().lower()
        if kind and item_kind != kind.strip().lower():
            continue
        filtered.append(item)

    return sorted(
        filtered,
        key=lambda item: (item.get("updated_at", ""), item.get("created_at", "")),
        reverse=True,
    )


def get_document(doc_id: str, kind: str | None = None) -> dict | None:
    if not doc_id:
        return None

    for item in list_documents(kind):
        if str(item.get("id", "")).strip() == str(doc_id).strip():
            return item
    return None


def delete_document(doc_id: str, kind: str | None = None) -> dict | None:
    data = _load_all()
    documents = data.get("documents", [])
    if not isinstance(documents, list):
        return None

    deleted = None
    remaining = []
    expected_kind = (kind or "").strip().lower()

    for item in documents:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "")).strip()
        item_kind = str(item.get("kind", "")).strip().lower()
        if item_id == str(doc_id).strip() and (not expected_kind or item_kind == expected_kind) and deleted is None:
            deleted = item
            continue
        remaining.append(item)

    if deleted is None:
        return None

    data["documents"] = remaining
    _save_all(data)
    return deleted


def get_state() -> dict:
    data = _load_all()
    return {
        "tasks": data.get("tasks", []),
        "plan": data.get("plan", {}),
        "prefs": data.get("prefs", {}),
        "documents": list_documents(),
    }
