#!/usr/bin/env python3
"""Validate and normalize Phase 0 input for the JS reverse automation skill.

Usage:
  python3 scripts/check_inputs.py --input <raw> --output artifacts/phase0_input.json
  python3 scripts/check_inputs.py --analysis analysis_result.json --schema schemas/analysis_result.schema.json --output artifacts/input_validation.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from common import dump_json, load_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Path to raw input JSON (Phase 0 mode).")
    parser.add_argument("--analysis", help="Path to analysis_result.json (schema validation mode).")
    parser.add_argument("--schema", default="", help="Path to JSON schema for analysis validation.")
    parser.add_argument("--output", required=True, help="Path to output JSON.")
    return parser.parse_args()


def ensure_http_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("target_url must be an absolute http or https URL")
    return value


def normalize_parameters(value: object) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.replace("/", ",").split(",")]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value]
    else:
        raise ValueError("parameters must be a string or a list of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            normalized.append(item)

    if not normalized:
        raise ValueError("parameters must not be empty")
    return normalized


def validate_phase0(raw: dict) -> dict:
    """Validate and normalize Phase 0 input."""
    missing = [field for field in ("target_url", "parameters") if not raw.get(field)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    return {
        "target_url": ensure_http_url(str(raw["target_url"]).strip()),
        "parameters": normalize_parameters(raw["parameters"]),
        "fetch_example": str(raw.get("fetch_example", "")).strip(),
        "notes": raw.get("notes", []),
    }


def validate_analysis_schema(analysis: dict, schema_path: str) -> list[str]:
    """Validate analysis_result.json against JSON schema if jsonschema is available."""
    if not schema_path:
        return []
    try:
        from jsonschema import Draft202012Validator
        schema = load_json(schema_path)
        errors = [e.message for e in Draft202012Validator(schema).iter_errors(analysis)]
        return errors
    except ImportError:
        return ["jsonschema not installed; skipping schema validation"]
    except FileNotFoundError:
        return [f"schema file not found: {schema_path}"]


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)

    # Phase 0 mode: validate raw input
    if args.input:
        raw = load_json(Path(args.input))
        normalized = validate_phase0(raw)
        dump_json(output_path, normalized)
        print(json.dumps({"status": "ok", "output": str(output_path)}, ensure_ascii=False))
        return 0

    # Schema validation mode: validate analysis_result.json
    if args.analysis:
        analysis = load_json(Path(args.analysis))

        # Check authorization.confirmed if present
        auth = analysis.get("authorization", {})
        if auth and not auth.get("confirmed"):
            print("[ERROR] authorization.confirmed must be true")
            return 2

        schema_path = args.schema or str(Path(__file__).parents[1] / "schemas" / "analysis_result.schema.json")
        errors = validate_analysis_schema(analysis, schema_path)
        if errors:
            for error in errors:
                print(f"[ERROR] {error}")
            return 2

        dump_json(output_path, {"status": "ok", "analysis": analysis})
        print(f"[OK] input validated: {output_path}")
        return 0

    print("[ERROR] either --input or --analysis must be specified")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
