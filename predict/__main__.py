"""
PREDICT - Vehicle Intelligence Platform

Entry point: python -m predict [--headless|--desktop]

Modes:
  --desktop   Launch PySide6 GUI with embedded FastAPI server (default)
  --headless  Launch FastAPI server only (for Windows service / 24/7 operation)
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="predict",
        description="PREDICT - Vehicle Intelligence Platform",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run server only, no GUI (for Windows service / 24/7 operation)",
    )
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Run PySide6 Desktop GUI with embedded server (default)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Server bind host (default: from .env or 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server bind port (default: from .env or 8000)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    if args.version:
        from predict.core.version import APP_VERSION, APP_NAME
        print(f"{APP_NAME} v{APP_VERSION}")
        sys.exit(0)

    if args.headless:
        _run_headless(args)
    else:
        _run_desktop(args)


def _run_headless(args):
    """Start server-only mode (no GUI)."""
    print("PREDICT - Starting in headless mode...")
    # Phase 10 will implement predict.headless
    try:
        from predict.headless import start_headless
        start_headless(host=args.host, port=args.port)
    except ImportError:
        print("Headless mode not yet implemented (Phase 10).")
        print("Server scaffolding is ready. Run with --desktop for GUI mode.")
        sys.exit(1)


def _run_desktop(args):
    """Start Desktop GUI with embedded server."""
    print("PREDICT - Starting in desktop mode...")
    # Phase 8 will implement predict.desktop.app
    try:
        from predict.desktop.app import start_desktop
        start_desktop(host=args.host, port=args.port)
    except ImportError:
        print("Desktop mode not yet implemented (Phase 8).")
        print("GUI scaffolding is ready. Phases 1-7 build the server core first.")
        sys.exit(1)


if __name__ == "__main__":
    main()
