#!/usr/bin/env python3
"""Validate one live browser/JSRPC action result before it is reported as success.

The validator deliberately checks evidence fields rather than service liveness. It
accepts either a raw /go response or an envelope with ``result`` and optional
bridge/tab/operation metadata.

Usage:
  python3 scripts/validate_browser_evidence.py \
    --input artifacts/jsrpc_smoke.json \
    --output artifacts/browser_evidence.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ERROR_MARKERS = ("JSRA_ERROR", "EvidenceMissing", "unavailable", "not verified")


def non_empty(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def path_value(root: dict[str, Any], *paths: str) -> tuple[Any, str | None]:
    for path in paths:
        value: Any = root
        ok = True
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                ok = False
                break
            value = value[part]
        if ok:
            return value, path
    return None, None


def marker_in(value: Any) -> str | None:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    lowered = text.lower()
    for marker in ERROR_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def validate(payload: Any, require_session: bool = False) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"passed": False, "reason": "top_level_object_required"}

    result = payload.get("result", payload)
    # Legacy JSRPC /go responses commonly serialize the action result in the
    # outer ``data`` field.  Decode that envelope before checking evidence;
    # an undecoded transport wrapper is not itself a missing business result.
    if isinstance(result, dict) and isinstance(result.get("data"), str):
        try:
            decoded = json.loads(result["data"])
        except (TypeError, ValueError):
            decoded = None
        if isinstance(decoded, dict):
            result = decoded
    if isinstance(result, dict) and isinstance(result.get("data"), dict):
        data = result["data"]
    elif isinstance(result, dict):
        data = result
    else:
        return {"passed": False, "reason": "result_object_required"}

    checks: dict[str, dict[str, Any]] = {}

    plaintext, plaintext_path = path_value(data, "plaintext", "input", "value")
    checks["plaintext"] = {"ok": non_empty(plaintext), "path": plaintext_path}

    request_body, request_body_path = path_value(
        data, "requestBody", "request.body", "request.bodyText", "ciphertext"
    )
    checks["request_body"] = {"ok": non_empty(request_body), "path": request_body_path}

    status, status_path = path_value(data, "status", "httpStatus", "response.status")
    checks["http_status"] = {
        "ok": isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599,
        "path": status_path,
        "value_type": type(status).__name__,
    }

    route, route_path = path_value(
        data, "route", "request.route", "request.url", "url", "request.path"
    )
    checks["final_route"] = {"ok": non_empty(route), "path": route_path}

    response, response_path = path_value(data, "response", "businessResponse", "body")
    checks["business_response"] = {"ok": non_empty(response), "path": response_path}

    error_marker = marker_in(result)
    checks["no_error_marker"] = {"ok": error_marker is None, "marker": error_marker}

    session = payload.get("session") or payload.get("browser") or {}
    session_checks: dict[str, Any] = {"provided": bool(session)}
    if session:
        connected = session.get("connected", session.get("bridge", {}).get("connected"))
        tab_id = session.get("tabId", session.get("tab", {}).get("tabId"))
        document_id = session.get("documentId", session.get("tab", {}).get("documentId"))
        session_checks.update({
            "connected": connected is True,
            "tab_id": non_empty(tab_id),
            "document_id": non_empty(document_id),
        })
    elif require_session:
        session_checks["reason"] = "session_metadata_required"

    required = [item["ok"] for item in checks.values()]
    if require_session:
        required.extend(session_checks.get(key, False) for key in ("connected", "tab_id", "document_id"))
    return {
        "passed": all(required),
        "evidence": {
            "plaintext_present": checks["plaintext"]["ok"],
            "request_body_present": checks["request_body"]["ok"],
            "final_route_present": checks["final_route"]["ok"],
            "http_status_present": checks["http_status"]["ok"],
            "business_response_present": checks["business_response"]["ok"],
        },
        "checks": checks,
        "session": session_checks,
        "reportable_success": all(required),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live browser/JSRPC evidence.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-session", action="store_true",
                        help="Require connected bridge, tabId and documentId metadata.")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = validate(payload, require_session=args.require_session)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
