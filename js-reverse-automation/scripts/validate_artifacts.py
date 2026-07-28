#!/usr/bin/env python3
"""Four-layer artifact validator.

Layer 1: Schema validation (analysis_result + candidates against JSON schemas)
Layer 2: Static validation (Python syntax, JS syntax via Node)
Layer 3: Candidate invariant checks (verified=true requires verification records)
Layer 4: Cross-file consistency (actions present in both jsrpc_inject.js and flask_proxy.py)

Usage:
  python3 scripts/validate_artifacts.py \
    --analysis analysis_result.json \
    --candidates artifacts/encryption_candidates.json \
    --generated generated/ \
    --report artifacts/validation_report.json
"""
from __future__ import annotations

import argparse
import ast
import json
import py_compile
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl

from common import dump_json, load_json


def check_schema(name: str, data: dict, schema_path: Path) -> dict:
    """Validate data against a JSON schema."""
    try:
        from jsonschema import Draft202012Validator
        schema = load_json(schema_path)
        errors = [e.message for e in Draft202012Validator(schema).iter_errors(data)]
        return {"name": name, "ok": not errors, "errors": errors}
    except ImportError:
        return {"name": name, "ok": True, "skipped": "jsonschema not installed"}
    except FileNotFoundError:
        return {"name": name, "ok": True, "skipped": f"schema not found: {schema_path}"}


def check_python(path: Path) -> dict:
    """Check Python syntax."""
    try:
        py_compile.compile(str(path), doraise=True)
        ast.parse(path.read_text(encoding="utf-8"))
        return {"name": f"python:{path.name}", "ok": True}
    except Exception as error:
        return {"name": f"python:{path.name}", "ok": False, "errors": [str(error)]}


def check_javascript(path: Path) -> dict:
    """Check JavaScript syntax via Node.js."""
    if not path.exists():
        return {"name": f"javascript:{path.name}", "ok": False, "errors": ["missing"]}
    node = shutil.which("node")
    if not node:
        return {"name": f"javascript:{path.name}", "ok": True, "skipped": "node unavailable"}
    proc = subprocess.run([node, "--check", str(path)], text=True, capture_output=True)
    return {
        "name": f"javascript:{path.name}",
        "ok": proc.returncode == 0,
        "errors": [proc.stderr.strip()] if proc.returncode else []
    }


def check_candidate_invariants(candidates: dict) -> dict:
    """Check candidate verification invariants."""
    errors = []
    for c in candidates.get("candidates", []):
        evidence_types = [e.get("type") for e in c.get("evidence", []) if isinstance(e, dict)]
        verification = c.get("verification")
        provenance = c.get("provenance")
        if c.get("confidence") == "high" and not c.get("verified"):
            errors.append(f"{c.get('id')}: high confidence without verification")
        if c.get("verified"):
            if not isinstance(verification, list) or not verification:
                errors.append(f"{c.get('id')}: verified without verification records")
            if c.get("source") == "hint" or c.get("type") == "hint":
                errors.append(f"{c.get('id')}: manual hint cannot be verified")
            matched = any(
                isinstance(record, dict) and (
                    record.get("matched") is True or record.get("verified") is True or
                    any(isinstance(test, dict) and test.get("matched") is True
                        for test in record.get("tests", []))
                )
                for record in (verification or [])
            )
            if not matched:
                errors.append(f"{c.get('id')}: no successful runtime/request match")
    return {"name": "candidate_invariants", "ok": not errors, "errors": errors}


def check_cross_file(analysis: dict, generated: Path) -> dict:
    """Check cross-file consistency between JSRPC and Flask."""
    errors = []
    jsrpc = (generated / "jsrpc_inject.js").read_text(encoding="utf-8") if (generated / "jsrpc_inject.js").exists() else ""
    flask = (generated / "flask_proxy.py").read_text(encoding="utf-8") if (generated / "flask_proxy.py").exists() else ""

    # Check action names
    action_name = analysis.get("jsrpc", {}).get("action_name", "")
    if action_name and action_name not in jsrpc:
        errors.append(f"action missing from jsrpc_inject.js: {action_name}")
    if action_name and action_name not in flask:
        errors.append(f"action missing from flask_proxy.py: {action_name}")

    # Check entrypoint resolution
    if "resolveEntrypoint" not in jsrpc and "resolvePath" not in jsrpc:
        errors.append("jsrpc_inject.js does not contain entrypoint resolution")

    return {"name": "cross_file_consistency", "ok": not errors, "errors": errors}


def mock_semantics() -> dict:
    """Check HTTP form semantics."""
    raw = "a=1&a=2&password=x+y&empty="
    pairs = parse_qsl(raw, keep_blank_values=True)
    errors = []
    if pairs[:2] != [("a", "1"), ("a", "2")]:
        errors.append("duplicate form keys not preserved")
    if pairs[-1] != ("empty", ""):
        errors.append("blank form value not preserved")
    return {"name": "mock_http_semantics", "ok": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="Four-layer artifact validator.")
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--candidates", help="Path to encryption_candidates.json.")
    parser.add_argument("--generated", required=True, help="Path to generated/ directory.")
    parser.add_argument("--report", required=True, help="Path to validation report JSON.")
    parser.add_argument("--e2e-result", help="Path to optional E2E result JSON.")
    args = parser.parse_args()

    base = Path(__file__).parents[1]
    generated = Path(args.generated)
    analysis = load_json(args.analysis)

    checks = []

    # Layer 1: Schema validation
    schema_path = base / "schemas" / "analysis_result.schema.json"
    if schema_path.exists():
        checks.append(check_schema("analysis_schema", analysis, schema_path))

    if args.candidates:
        candidates = load_json(args.candidates)
        candidates_schema = base / "schemas" / "candidates.schema.json"
        if candidates_schema.exists():
            checks.append(check_schema("candidate_schema", candidates, candidates_schema))
        checks.append(check_candidate_invariants(candidates))

    # Layer 2: Static validation
    for name in ("flask_proxy.py",):
        path = generated / name
        checks.append(check_python(path) if path.exists() else {"name": f"python:{name}", "ok": False, "errors": ["missing"]})
    for name in ("jsrpc_inject.js", "runtime_hook_probe.js", "module_probe.js"):
        checks.append(check_javascript(generated / name))

    # Layer 3: Cross-file consistency
    checks.append(check_cross_file(analysis, generated))
    checks.append(mock_semantics())

    # Layer 4: Optional real E2E
    if args.e2e_result:
        e2e = load_json(args.e2e_result, {})
        checks.append({"name": "real_e2e", "ok": bool(e2e.get("passed")), "details": e2e})

    report = {
        "version": "2.1.0",
        "passed": all(c.get("ok") for c in checks),
        "checks": checks
    }
    dump_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
