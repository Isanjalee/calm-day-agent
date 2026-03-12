import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

import tools
from config import load_config
from document_service import send_learning_note_email
from planner_service import generate_plan, normalize_plan, send_plan_email

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
ASSETS_DIR = (WEB_DIR / "assets").resolve()

load_dotenv()


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    try:
        content_length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        content_length = 0

    raw = handler.rfile.read(content_length) if content_length > 0 else b"{}"
    if not raw:
        return {}

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _public_state() -> dict:
    config = load_config()
    state = tools.get_state()
    return {
        "config": {
            "user_name": config.user_name,
            "partner_name": config.partner_name,
            "timezone": config.timezone,
            "can_send_plan": config.validate_email_settings() is None,
        },
        "plan": state.get("plan", {}),
        "documents": state.get("documents", []),
    }


def _resolve_asset_path(relative_path: str) -> Path | None:
    candidate = (ASSETS_DIR / Path(unquote(relative_path))).resolve()
    try:
        candidate.relative_to(ASSETS_DIR)
    except ValueError:
        return None
    return candidate


class CalmDayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            _json_response(self, _public_state())
            return

        if parsed.path == "/":
            self._serve_file(WEB_DIR / "index.html")
            return

        if parsed.path.startswith("/assets/"):
            relative = parsed.path.removeprefix("/assets/")
            asset_path = _resolve_asset_path(relative)
            if asset_path is None:
                _json_response(
                    self,
                    {"ok": False, "error": "Invalid asset path."},
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            self._serve_file(asset_path)
            return

        _json_response(
            self,
            {"ok": False, "error": f"Route not found: {parsed.path}"},
            status=HTTPStatus.NOT_FOUND,
        )

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = _read_json(self)
        config = load_config()

        if parsed.path == "/api/plan/generate":
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                _json_response(
                    self,
                    {"ok": False, "error": "Please describe the day you want planned."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            plan = generate_plan(prompt, config, prefs=tools.get_prefs())
            _json_response(self, {"ok": True, "plan": plan})
            return

        if parsed.path == "/api/plan/save":
            plan = normalize_plan(payload.get("plan", {}), config)
            tools.save_plan(plan)
            _json_response(self, {"ok": True, "plan": plan, "message": "Day plan saved."})
            return

        if parsed.path == "/api/plan/send":
            plan = normalize_plan(payload.get("plan", {}) or tools.get_plan(), config)
            tools.save_plan(plan)
            result = send_plan_email(plan, config)
            _json_response(
                self,
                {"ok": result.lower().startswith("email sent"), "message": result, "plan": plan},
            )
            return

        if parsed.path == "/api/document/save":
            kind = str(payload.get("kind", "")).strip().lower()
            title = str(payload.get("title", "")).strip()
            content = str(payload.get("content", "")).strip()
            doc_id = str(payload.get("id", "")).strip() or None
            try:
                document = tools.save_document(kind, title, content, doc_id=doc_id)
            except ValueError as exc:
                _json_response(
                    self,
                    {"ok": False, "error": str(exc)},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            _json_response(
                self,
                {
                    "ok": True,
                    "document": document,
                    "documents": tools.list_documents(kind),
                    "message": "Learning note saved." if kind == "book" else f"{kind.title()} saved.",
                },
            )
            return

        if parsed.path == "/api/document/delete":
            kind = str(payload.get("kind", "")).strip().lower()
            doc_id = str(payload.get("id", "")).strip()
            if not doc_id:
                _json_response(
                    self,
                    {"ok": False, "error": "Document id was required."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            deleted = tools.delete_document(doc_id, kind or None)
            if deleted is None:
                _json_response(
                    self,
                    {"ok": False, "error": "Document not found."},
                    status=HTTPStatus.NOT_FOUND,
                )
                return

            _json_response(
                self,
                {
                    "ok": True,
                    "document": deleted,
                    "documents": tools.list_documents(kind or None),
                    "message": "Learning note deleted." if kind == "book" else f"{kind.title() if kind else 'Document'} deleted.",
                },
            )
            return

        if parsed.path == "/api/document/send-pdf":
            doc_id = str(payload.get("id", "")).strip()
            if not doc_id:
                _json_response(
                    self,
                    {"ok": False, "error": "Document id was required."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            document = tools.get_document(doc_id, "book")
            if document is None:
                _json_response(
                    self,
                    {"ok": False, "error": "Learning note not found."},
                    status=HTTPStatus.NOT_FOUND,
                )
                return

            result = send_learning_note_email(document, config)
            _json_response(
                self,
                {
                    "ok": result.lower().startswith("email sent"),
                    "message": result,
                    "document": document,
                },
            )
            return

        _json_response(
            self,
            {"ok": False, "error": f"Route not found: {parsed.path}"},
            status=HTTPStatus.NOT_FOUND,
        )

    def _serve_file(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            _json_response(
                self,
                {"ok": False, "error": "File not found."},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run(host: str = "127.0.0.1", port: int = 8088):
    server = ThreadingHTTPServer((host, port), CalmDayHandler)
    print(f"Calm Day UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
