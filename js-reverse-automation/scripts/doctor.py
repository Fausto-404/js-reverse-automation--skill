#!/usr/bin/env python3
"""Check JSRA runtime dependencies.

Usage:
  python3 scripts/doctor.py
  python3 scripts/doctor.py --ci
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Check JSRA runtime dependencies.")
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args()

    checks = {
        "python": {"ok": sys.version_info >= (3, 10), "value": platform.python_version(), "required": True},
        "flask": {"ok": importlib.util.find_spec("flask") is not None, "required": True},
        "requests": {"ok": importlib.util.find_spec("requests") is not None, "required": True},
        "jsonschema": {"ok": importlib.util.find_spec("jsonschema") is not None, "required": True},
        "websocket_client": {"ok": importlib.util.find_spec("websocket") is not None, "required": False},
        "node": {"ok": shutil.which("node") is not None, "value": shutil.which("node"), "required": False},
        "chrome": {"ok": any(shutil.which(x) for x in ("google-chrome", "chromium", "chromium-browser")), "required": False},
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    failed = [name for name, item in checks.items() if item.get("required") and not item.get("ok")]
    if failed:
        print("Missing required dependencies:", ", ".join(failed))
        return 2
    if not args.ci and not checks["node"]["ok"]:
        print("[WARN] Node.js not found; JavaScript syntax validation will be skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
