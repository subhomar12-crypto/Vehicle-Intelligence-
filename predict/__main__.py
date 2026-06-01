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


def _build_kwargs(args):
    """Build host/port kwargs, skipping None values so defaults apply."""
    kw = {}
    if args.host is not None:
        kw['host'] = args.host
    if args.port is not None:
        kw['port'] = args.port
    return kw


def _run_headless(args):
    """Start server-only mode (no GUI)."""
    print("PREDICT - Starting in headless mode...")
    try:
        from predict.headless import start_headless
    except ImportError as e:
        print(f"Failed to start headless mode: {e}")
        print("Check that all dependencies are installed (pip install -e .)")
        sys.exit(1)
    start_headless(**_build_kwargs(args))


def _run_desktop(args):
    """Start Desktop GUI with embedded server."""
    print("PREDICT - Starting in desktop mode...")
    try:
        from predict.desktop.app import start_desktop
    except ImportError as e:
        print(f"Failed to start desktop mode: {e}")
        print("Check that all dependencies are installed (pip install -e .)")
        print("PySide6 required: pip install PySide6")
        sys.exit(1)
    start_desktop(**_build_kwargs(args))


if __name__ == "__main__":
    main()
