#!/usr/bin/env python3
"""Manage JSRPC server and Flask proxy lifecycle.

Supports the legacy flag interface and the state-file subcommand interface.
Includes PID identity verification to avoid killing wrong processes.

Usage (legacy flag interface):
  python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action start --force
  python3 scripts/manage_services.py --service flask --analysis analysis_result.json --flask-file generated/flask_proxy.py --output artifacts/flask_status.json --action start --force
  python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action stop

Usage (state-file subcommand):
  python3 scripts/manage_services.py start --kind jsrpc --state artifacts/jsrpc_state.json
  python3 scripts/manage_services.py stop --state artifacts/jsrpc_state.json
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
from shutil import which

from common import dump_json, load_json

# Common JSRPC binary names and paths to search
JSRPC_SEARCH_NAMES = ["jsrpc", "jsrpc-mac", "jsrpc-linux", "mac_m_arm64", "mac_x64", "linux_amd64"]
JSRPC_SEARCH_DIRS = [
    Path.home() / "jsrpc",
    Path.home() / "jstest",
    Path.home() / "hacker" / "jstest",
    Path.home() / "tools" / "jsrpc",
    Path.home() / ".local" / "bin",
    Path("/usr/local/bin"),
    Path("/opt/jsrpc"),
]


def find_jsrpc_binary() -> str | None:
    """Auto-discover JSRPC binary from common locations and PATH."""
    # 1. Check PATH
    for name in JSRPC_SEARCH_NAMES:
        found = which(name)
        if found:
            return found
    # 2. Check common directories
    for search_dir in JSRPC_SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for name in JSRPC_SEARCH_NAMES:
            candidate = search_dir / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        for subdir in search_dir.iterdir():
            if subdir.is_dir():
                for name in JSRPC_SEARCH_NAMES:
                    candidate = subdir / name
                    if candidate.is_file() and os.access(candidate, os.X_OK):
                        return str(candidate)
    # 3. Check current directory and parent
    cwd = Path.cwd()
    for name in JSRPC_SEARCH_NAMES:
        candidate = cwd / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        candidate = cwd.parent / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def process_identity(pid: int) -> dict:
    """Get process identity info for PID verification."""
    result = {"pid": pid, "alive": False, "exe": None, "started": None, "command": None}
    try:
        os.kill(pid, 0)
        result["alive"] = True
    except OSError:
        return result
    proc = Path(f"/proc/{pid}")
    if proc.exists():
        try:
            result["exe"] = str((proc / "exe").resolve())
        except OSError:
            pass
        try:
            result["started"] = (proc / "stat").read_text().split()[21]
        except Exception:
            pass
        try:
            result["command"] = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="replace").strip()
        except Exception:
            pass
    else:
        try:
            result["command"] = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                text=True, capture_output=True, timeout=2
            ).stdout.strip() or None
            result["started"] = subprocess.run(
                ["ps", "-p", str(pid), "-o", "lstart="],
                text=True, capture_output=True, timeout=2
            ).stdout.strip() or None
        except Exception:
            pass
    return result


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
        result = subprocess.run(["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True, timeout=5)
        for pid in result.stdout.strip().split("\n"):
            pid = pid.strip()
            if pid.isdigit():
                return int(pid)
    except Exception:
        pass
    return None


def find_available_port(start: int, host: str = "127.0.0.1", attempts: int = 30) -> int | None:
    """Find an available local port without touching an unrelated process."""
    for candidate in range(int(start), int(start) + attempts):
        if not is_port_in_use(candidate, host):
            return candidate
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


# === Legacy flag interface ===

def legacy_jsrpc_start(binary_path: str, port: int) -> dict:
    proc = subprocess.Popen([binary_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(10):
        time.sleep(0.5)
        if is_port_in_use(port):
            identity = process_identity(proc.pid)
            return {"status": "started", "pid": proc.pid, "binary_path": str(Path(binary_path).resolve()), "port": port,
                    "started": identity.get("started"), "observed_command": identity.get("command"),
                    "stop_hint": "使用同一状态文件执行 manage_services.py --action stop"}
    return {"status": "start_failed", "pid": proc.pid, "binary_path": binary_path, "port": port}


def legacy_flask_start(flask_file: str, host: str, port: int, route: str = "/autodecoder") -> dict:
    requested_port = int(port)
    actual_port = requested_port
    if is_port_in_use(actual_port, host):
        actual_port = find_available_port(actual_port + 1, host)
        if actual_port is None:
            existing_pid = get_pid_on_port(requested_port)
            return {"status": "port_occupied", "port": requested_port, "existing_pid": existing_pid, "hint": f"端口 {requested_port} 已被占用，且没有找到可用备用端口"}
    if not os.path.isfile(flask_file):
        return {"status": "file_not_found", "flask_file": flask_file, "hint": "Flask 代理文件不存在，先运行代码生成"}
    log_file = Path(flask_file).parent / "flask_proxy.log"
    environment = os.environ.copy()
    environment["JSRA_FLASK_PORT"] = str(actual_port)
    with open(log_file, "w") as lf:
        proc = subprocess.Popen([sys.executable, flask_file], stdout=lf, stderr=subprocess.STDOUT, start_new_session=True, env=environment)
    for _ in range(10):
        time.sleep(0.5)
        if is_port_in_use(actual_port, host):
            healthy = check_health(host, actual_port)
            identity = process_identity(proc.pid)
            return {
                "status": "started", "pid": proc.pid, "host": host, "port": actual_port,
                "requested_port": requested_port, "port_fallback": actual_port != requested_port,
                "flask_file": str(Path(flask_file).resolve()),
                "started": identity.get("started"), "observed_command": identity.get("command"),
                "url": f"http://{host}:{actual_port}{route}", "healthz": f"http://{host}:{actual_port}/healthz",
                "encode_url": f"http://{host}:{actual_port}/encode", "decode_url": f"http://{host}:{actual_port}/decode",
                "healthy": healthy, "log_file": str(log_file),
                "stop_hint": "使用同一状态文件执行 manage_services.py --action stop"
            }
    return {"status": "start_failed", "pid": proc.pid, "port": actual_port, "requested_port": requested_port,
            "flask_file": str(Path(flask_file).resolve()), "log_file": str(log_file)}


def legacy_status(path: str) -> dict:
    """Load a previously written legacy status file without guessing a PID."""
    try:
        return load_json(Path(path), {})
    except (OSError, ValueError, TypeError):
        return {}


def managed_pid_matches(status: dict, kind: str) -> bool:
    """Verify that a legacy status PID still belongs to this service.

    The legacy interface predates state files, so only a recorded PID and a
    recorded executable/script identity are accepted.  A port occupant alone
    is never sufficient evidence for a kill operation.
    """
    pid = status.get("pid")
    if not pid:
        return False
    try:
        identity = process_identity(int(pid))
    except (TypeError, ValueError):
        return False
    if not identity.get("alive"):
        return False
    expected = str(status.get("flask_file" if kind == "flask" else "binary_path", ""))
    command = str(identity.get("command") or "")
    if not expected or not command:
        return False
    if status.get("started") and identity.get("started") and status["started"] != identity["started"]:
        return False
    return Path(expected).name in command or expected in command


def stop_legacy_service(kind: str, status_path: str, configured_port: int) -> dict:
    """Stop only a process recorded by this skill's own status artifact."""
    status = legacy_status(status_path)
    if not status:
        return {"status": "not_running", "port": configured_port, "hint": "没有可验证的服务状态文件，未尝试按端口杀进程"}
    if not managed_pid_matches(status, kind):
        return {"status": "identity_mismatch", "pid": status.get("pid"), "port": status.get("port", configured_port),
                "hint": "状态文件中的进程身份无法验证，未执行停止操作"}
    pid = int(status["pid"])
    if kill_process(pid):
        return {"status": "stopped", "pid": pid, "port": status.get("port", configured_port)}
    return {"status": "stop_failed", "pid": pid, "port": status.get("port", configured_port)}


def legacy_mode(args: argparse.Namespace) -> dict:
    """Legacy flag-based interface."""
    analysis = load_json(Path(args.analysis))
    if args.service == "jsrpc":
        config = analysis.get("jsrpc_server", {})
        port = config.get("port", 12080)
        if args.action == "stop":
            return stop_legacy_service("jsrpc", args.output, port)
        elif args.action == "status":
            if not is_port_in_use(port):
                return {"status": "not_running", "port": port}
            pid = get_pid_on_port(port)
            return {"status": "already_running", "pid": pid, "port": port,
                    "stop_command": f"python3 scripts/manage_services.py --service jsrpc --analysis {args.analysis} --output {args.output} --action stop" if pid else None}
        else:  # start
            if is_port_in_use(port):
                pid = get_pid_on_port(port)
                status = legacy_status(args.output)
                if status.get("status") in {"started", "already_running"} and managed_pid_matches(status, "jsrpc"):
                    return {"status": "already_running", "pid": status.get("pid", pid), "port": port,
                            "stop_command": f"python3 scripts/manage_services.py --service jsrpc --analysis {args.analysis} --output {args.output} --action stop"}
                return {"status": "port_occupied", "pid": pid, "port": port,
                        "hint": f"端口 {port} 已被其他进程占用，未执行强制终止；请释放端口或更换 JSRPC 端口"}
            binary_path = config.get("binary_path", "")
            if binary_path == "auto" or not binary_path:
                binary_path = find_jsrpc_binary()
            if binary_path and os.path.isfile(binary_path):
                return legacy_jsrpc_start(binary_path, port)
            return {"status": "not_found", "port": port, "hint": "请在 analysis_result.json 的 jsrpc_server.binary_path 中提供 JSRPC 服务器二进制路径，或手动启动后重试"}
    else:  # flask
        config = analysis.get("flask_server", analysis.get("flask", {}))
        host = config.get("listen_host", config.get("host", "127.0.0.1"))
        port = config.get("listen_port", config.get("port", 5000))
        if args.action == "stop":
            return stop_legacy_service("flask", args.output, port)
        elif args.action == "status":
            if not is_port_in_use(port, host):
                return {"status": "not_running", "port": port}
            pid = get_pid_on_port(port)
            healthy = check_health(host, port)
            flask_config = analysis.get("flask", {})
            route = flask_config.get("route", "/autodecoder")
            return {"status": "running", "pid": pid, "port": port, "healthy": healthy, "url": f"http://{host}:{port}{route}",
                    "stop_command": f"python3 scripts/manage_services.py --service flask --analysis {args.analysis} --output {args.output} --action stop" if pid else None}
        else:  # start
            flask_config = analysis.get("flask", {})
            route = flask_config.get("route", "/autodecoder")
            # The legacy Flask start deliberately selects a free fallback port.  Do
            # not pre-emptively kill an arbitrary occupant here; --force is
            # retained for CLI compatibility but never authorizes that kill.
            return legacy_flask_start(args.flask_file, host, port, route)
    return {"status": "error", "hint": "unknown action"}


# === State-file subcommand interface ===

def start_process(command: list[str], state_path: Path, kind: str) -> int:
    environment = None
    requested_port = None
    actual_port = None
    if kind == "flask":
        requested_port = int(os.environ.get("JSRA_FLASK_PORT", "5000"))
        actual_port = find_available_port(requested_port)
        if actual_port is None:
            print(json.dumps({"status": "port_occupied", "requested_port": requested_port}, ensure_ascii=False))
            return 2
        environment = os.environ.copy()
        environment["JSRA_FLASK_PORT"] = str(actual_port)
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env=environment)
    time.sleep(.3)
    identity = process_identity(process.pid)
    dump_json(state_path, {
        "kind": kind, "command": command, "pid": process.pid,
        "exe": identity.get("exe"), "started": identity.get("started"),
        "observed_command": identity.get("command"), "created_at": time.time(),
        "requested_port": requested_port, "port": actual_port,
        "port_fallback": actual_port is not None and actual_port != requested_port
    })
    print(json.dumps({"status": "started", "kind": kind, "pid": process.pid, "state": str(state_path), "port": actual_port}, ensure_ascii=False))
    return 0


def stop_process(state_path: Path, kill_unknown: bool) -> int:
    state = load_json(state_path)
    identity = process_identity(int(state["pid"]))
    if not identity["alive"]:
        state_path.unlink(missing_ok=True)
        print("[OK] process already stopped")
        return 0
    expected = (state.get("exe"), state.get("started"), state.get("observed_command"))
    actual = (identity.get("exe"), identity.get("started"), identity.get("command"))
    verifiable = any(value is not None for value in expected)
    if (not verifiable or expected != actual) and not kill_unknown:
        print(f"[ERROR] process identity cannot be verified; expected={expected}, actual={actual}")
        return 3
    os.kill(int(state["pid"]), signal.SIGTERM)
    state_path.unlink(missing_ok=True)
    print(f"[OK] stopped pid {state['pid']}")
    return 0


def main() -> int:
    # Detect the legacy flag interface or the state-file subcommand interface.
    if len(sys.argv) > 1 and sys.argv[1] in ("start", "stop", "status"):
        # State-file subcommand mode
        parser = argparse.ArgumentParser(description="Safe service manager for JSRA.")
        sub = parser.add_subparsers(dest="command", required=True)
        start = sub.add_parser("start")
        start.add_argument("--kind", choices=["jsrpc", "flask"], required=True)
        start.add_argument("--state", required=True)
        start.add_argument("--jsrpc-binary")
        start.add_argument("--flask-script")
        stop = sub.add_parser("stop")
        stop.add_argument("--state", required=True)
        stop.add_argument("--kill-unknown", action="store_true")
        status = sub.add_parser("status")
        status.add_argument("--state", required=True)
        args = parser.parse_args()
        state = Path(args.state)

        if args.command == "start":
            if args.kind == "jsrpc":
                binary_path = args.jsrpc_binary
                if not binary_path:
                    binary_path = find_jsrpc_binary()
                    if not binary_path:
                        parser.error("--jsrpc-binary is required; auto-discovery failed.")
                    print(f"[INFO] Auto-discovered JSRPC binary: {binary_path}")
                binary = Path(binary_path).expanduser().resolve()
                if not binary.is_file() or not os.access(binary, os.X_OK):
                    parser.error("invalid executable: " + str(binary))
                return start_process([str(binary)], state, "jsrpc")
            if not args.flask_script:
                parser.error("--flask-script is required")
            return start_process([sys.executable, str(Path(args.flask_script).resolve())], state, "flask")
        if args.command == "stop":
            return stop_process(state, args.kill_unknown)
        info = load_json(state, {})
        print(json.dumps({
            "state": info,
            "process": process_identity(int(info["pid"])) if info.get("pid") else None
        }, ensure_ascii=False, indent=2))
        return 0
    else:
        # Legacy flag-based mode
        parser = argparse.ArgumentParser()
        parser.add_argument("--service", required=True, choices=["jsrpc", "flask"])
        parser.add_argument("--analysis", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--flask-file", default="")
        parser.add_argument("--action", choices=["start", "stop", "status"], default="start")
        parser.add_argument("--force", action="store_true")
        args = parser.parse_args()
        result = legacy_mode(args)
        dump_json(Path(args.output), result)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") in ("already_running", "started", "running", "stopped", "not_running") else 1


if __name__ == "__main__":
    raise SystemExit(main())
