#!/usr/bin/env python3
"""Manage JSRPC server and Flask proxy lifecycle.

Usage:
  python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action start
  python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action stop
  python3 scripts/manage_services.py --service flask --analysis analysis_result.json --flask-file generated/flask_proxy.py --output artifacts/flask_status.json --action start
  python3 scripts/manage_services.py --service flask --analysis analysis_result.json --output artifacts/flask_status.json --action stop
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True, choices=["jsrpc", "flask"])
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--output", required=True, help="Path to status output JSON.")
    parser.add_argument("--flask-file", default="", help="Path to generated flask_proxy.py (flask only).")
    parser.add_argument("--action", choices=["start", "stop", "status"], default="start")
    parser.add_argument("--force", action="store_true", help="Auto-kill process on occupied port before start")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    for family in [socket.AF_INET, socket.AF_INET6]:
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                h = "127.0.0.1" if family == socket.AF_INET else "::1"
                if s.connect_ex((h, port)) == 0:
                    return True
        except Exception:
            pass
    return False


def get_pid_on_port(port: int) -> int | None:
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True, text=True, timeout=5
        )
        for pid in result.stdout.strip().split("\n"):
            pid = pid.strip()
            if pid.isdigit():
                return int(pid)
    except Exception:
        pass
    return None


def kill_process(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return True
    except ProcessLookupError:
        return True
    except Exception:
        return False


def check_health(host: str, port: int) -> bool:
    try:
        import urllib.request
        req = urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=3)
        return req.status == 200
    except Exception:
        return False


def find_jsrpc_binary() -> str | None:
    """Search common locations for JSRPC binary."""
    home = Path.home()
    search_dirs = [
        Path.cwd(),
        home / "jsrpc",
        home / "tools",
        home / "Desktop",
        home / "Downloads",
        home / "bin",
    ]
    for d in search_dirs:
        if not d.is_dir():
            continue
        try:
            for item in d.iterdir():
                if item.is_file() and os.access(str(item), os.X_OK):
                    try:
                        result = subprocess.run(
                            ["file", str(item)], capture_output=True, text=True, timeout=5
                        )
                        out = result.stdout.lower()
                        if any(kw in out for kw in ["executable", "mach-o", "elf"]):
                            return str(item)
                    except Exception:
                        pass
        except PermissionError:
            pass
    return None


# === JSRPC specific ===

def jsrpc_start(binary_path: str, port: int) -> dict:
    proc = subprocess.Popen(
        [binary_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
    )
    for _ in range(10):
        time.sleep(0.5)
        if is_port_in_use(port):
            return {"status": "started", "pid": proc.pid, "binary_path": binary_path, "port": port, "stop_command": f"kill {proc.pid}"}
    return {"status": "start_failed", "pid": proc.pid, "binary_path": binary_path, "port": port}


def jsrpc_status(port: int) -> dict:
    if not is_port_in_use(port):
        return {"status": "not_running", "port": port}
    pid = get_pid_on_port(port)
    return {"status": "already_running", "pid": pid, "port": port, "stop_command": f"kill {pid}" if pid else None}


def jsrpc_stop(port: int) -> dict:
    pid = get_pid_on_port(port)
    if not pid:
        return {"status": "not_running", "port": port}
    if kill_process(pid):
        return {"status": "stopped", "pid": pid, "port": port}
    return {"status": "stop_failed", "pid": pid, "port": port}


# === Flask specific ===

def flask_start(flask_file: str, host: str, port: int) -> dict:
    if is_port_in_use(port, host):
        existing_pid = get_pid_on_port(port)
        return {"status": "port_occupied", "port": port, "existing_pid": existing_pid, "hint": f"端口 {port} 已被占用，kill {existing_pid} 后重试"}
    if not os.path.isfile(flask_file):
        return {"status": "file_not_found", "flask_file": flask_file, "hint": "Flask 代理文件不存在，先运行代码生成"}
    log_file = Path(flask_file).parent / "flask_proxy.log"
    with open(log_file, "w") as lf:
        proc = subprocess.Popen([sys.executable, flask_file], stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(10):
        time.sleep(0.5)
        if is_port_in_use(port, host):
            healthy = check_health(host, port)
            return {
                "status": "started", "pid": proc.pid, "host": host, "port": port,
                "url": f"http://{host}:{port}/encode", "healthz": f"http://{host}:{port}/healthz",
                "healthy": healthy, "log_file": str(log_file), "stop_command": f"kill {proc.pid}"
            }
    return {"status": "start_failed", "pid": proc.pid, "port": port, "log_file": str(log_file)}


def flask_status(host: str, port: int) -> dict:
    if not is_port_in_use(port, host):
        return {"status": "not_running", "port": port}
    pid = get_pid_on_port(port)
    healthy = check_health(host, port)
    return {"status": "running", "pid": pid, "port": port, "healthy": healthy, "url": f"http://{host}:{port}/encode", "stop_command": f"kill {pid}" if pid else None}


def flask_stop(host: str, port: int) -> dict:
    pid = get_pid_on_port(port)
    if not pid:
        return {"status": "not_running", "port": port}
    if kill_process(pid):
        return {"status": "stopped", "pid": pid, "port": port}
    return {"status": "stop_failed", "pid": pid, "port": port}


def main() -> int:
    args = parse_args()
    analysis_path = Path(args.analysis)
    output_path = Path(args.output)
    analysis = load_json(analysis_path)

    if args.service == "jsrpc":
        config = analysis.get("jsrpc_server", {})
        port = config.get("port", 12080)
        if args.action == "stop":
            result = jsrpc_stop(port)
        elif args.action == "status":
            result = jsrpc_status(port)
        else:
            if is_port_in_use(port):
                if args.force:
                    pid = get_pid_on_port(port)
                    if pid:
                        kill_process(pid)
                        time.sleep(1)
                    # fall through to start
                else:
                    result = jsrpc_status(port)
            if not is_port_in_use(port) and args.action == "start":
                binary_path = config.get("binary_path", "")
                if binary_path == "auto" or not binary_path:
                    binary_path = find_jsrpc_binary()
                if binary_path and os.path.isfile(binary_path):
                    result = jsrpc_start(binary_path, port)
                else:
                    result = {"status": "not_found", "port": port, "hint": "请在 analysis_result.json 的 jsrpc_server.binary_path 中提供 JSRPC 服务器二进制路径，或手动启动后重试"}
    else:
        config = analysis.get("flask_server", analysis.get("flask", {}))
        host = config.get("listen_host", config.get("host", "127.0.0.1"))
        port = config.get("listen_port", config.get("port", 5000))
        if args.action == "stop":
            result = flask_stop(host, port)
        elif args.action == "status":
            result = flask_status(host, port)
        else:
            if is_port_in_use(port, host) and args.force:
                pid = get_pid_on_port(port)
                if pid:
                    kill_process(pid)
                    time.sleep(1)
            result = flask_start(args.flask_file, host, port)

    save_json(output_path, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") in ("already_running", "started", "running", "stopped", "not_running") else 1


if __name__ == "__main__":
    raise SystemExit(main())
