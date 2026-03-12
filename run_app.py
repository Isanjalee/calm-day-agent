import argparse
import importlib
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Calm Day web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the local server to.")
    parser.add_argument("--port", default=8088, type=int, help="Port to bind the local server to.")
    return parser


def _print_missing_dependency_help(module_name: str):
    project_root = Path(__file__).resolve().parent
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        install_command = f'"{venv_python}" -m pip install groq python-dotenv rich'
    else:
        install_command = "python -m pip install groq python-dotenv rich"

    print(f"Missing dependency: {module_name}")
    print("Install the required packages, then run the app again.")
    print(f"Suggested command: {install_command}")


def main() -> int:
    args = _build_parser().parse_args()

    try:
        webapp = importlib.import_module("webapp")
    except ModuleNotFoundError as exc:
        _print_missing_dependency_help(exc.name or "unknown")
        return 1

    url = f"http://{args.host}:{args.port}"
    print(f"Starting Calm Day at {url}")

    try:
        webapp.run(host=args.host, port=args.port)
    except OSError as exc:
        print(f"Failed to start server: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nCalm Day stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
