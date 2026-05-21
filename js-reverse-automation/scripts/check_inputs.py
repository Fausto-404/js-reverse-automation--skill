#!/usr/bin/env python3
"""Validate and normalize Phase 0 input for the JS reverse automation skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to raw input JSON.")
    parser.add_argument("--output", required=True, help="Path to normalized output JSON.")
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


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    return data


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    raw = load_json(input_path)

    missing = [
        field
        for field in ("target_url", "parameters", "environment_constraints")
        if not raw.get(field)
    ]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    normalized = {
        "target_url": ensure_http_url(str(raw["target_url"]).strip()),
        "parameters": normalize_parameters(raw["parameters"]),
        "environment_constraints": str(raw["environment_constraints"]).strip(),
        "fetch_example": str(raw.get("fetch_example", "")).strip(),
        "notes": raw.get("notes", []),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps({"status": "ok", "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
