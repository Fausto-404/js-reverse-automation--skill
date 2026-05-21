#!/usr/bin/env python3
"""Merge Phase 0-3 outputs into the canonical analysis_result.json artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase0", required=True, help="Normalized Phase 0 input JSON.")
    parser.add_argument("--phase1", required=True, help="Phase 1 trace JSON.")
    parser.add_argument("--phase2", required=True, help="Phase 2 entrypoint JSON.")
    parser.add_argument("--phase3", required=True, help="Phase 3 dependency JSON.")
    parser.add_argument("--output", required=True, help="analysis_result.json output path.")
    parser.add_argument("--group", default="reverse", help="Default JSRPC group.")
    parser.add_argument("--action-prefix", default="generate", help="Prefix for JSRPC actions.")
    return parser.parse_args()


def load_json(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return value or "action"


def require_parameter_map(payload: dict, name: str) -> dict:
    parameters = payload.get("parameters")
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError(f"{name} must contain a non-empty parameters object")
    return parameters


def main() -> int:
    args = parse_args()
    phase0 = load_json(args.phase0)
    phase1 = load_json(args.phase1)
    phase2 = load_json(args.phase2)
    phase3 = load_json(args.phase3)

    phase2_parameters = require_parameter_map(phase2, "phase2")
    phase3_parameters = require_parameter_map(phase3, "phase3")

    requested = phase0.get("parameters", [])
    if not isinstance(requested, list) or not requested:
        raise ValueError("phase0 parameters must be a non-empty list")

    merged_parameters: dict[str, dict] = {}
    warnings: list[str] = []

    for parameter in requested:
        if parameter not in phase2_parameters:
            raise ValueError(f"phase2 missing parameter: {parameter}")
        if parameter not in phase3_parameters:
            raise ValueError(f"phase3 missing parameter: {parameter}")

        entrypoint_info = phase2_parameters[parameter]
        preferred = entrypoint_info.get("preferred_entrypoint")
        if not isinstance(preferred, dict):
            raise ValueError(f"phase2 preferred_entrypoint missing for parameter: {parameter}")

        phase3_info = phase3_parameters[parameter]
        call_signature = phase3_info.get("call_signature")
        runtime = phase3_info.get("runtime")
        dependencies = phase3_info.get("dependencies", [])
        if not isinstance(call_signature, dict):
            raise ValueError(f"phase3 call_signature missing for parameter: {parameter}")
        if not isinstance(runtime, dict):
            raise ValueError(f"phase3 runtime missing for parameter: {parameter}")
        if not isinstance(dependencies, list):
            raise ValueError(f"phase3 dependencies must be a list for parameter: {parameter}")

        if preferred.get("type") == "resolver":
            warnings.append(f"{parameter}: resolver entrypoint is less stable than a static path")

        merged_parameters[parameter] = {
            "entrypoint": preferred,
            "call_signature": call_signature,
            "runtime": runtime,
            "dependencies": dependencies,
            "candidates": entrypoint_info.get("candidates", []),
        }

    primary_parameter = requested[0]
    action_name = f"{args.action_prefix}_{slugify(primary_parameter)}"
    group = slugify(args.group)
    analysis = {
        "skill": {"name": "js-reverse-automation", "version": "2.0.0"},
        "input": phase0,
        "trace": phase1,
        "parameters": merged_parameters,
        "jsrpc": {
            "group": group,
            "action_name": action_name,
            "transport": {
                "ws_url": f"ws://127.0.0.1:12080/ws?group={group}&name=skill",
                "go_url": "http://127.0.0.1:12080/go",
            },
        },
        "flask": {"listen_host": "127.0.0.1", "listen_port": 5000, "route": "/encode"},
        "burp": {
            "decoder_type": "HTTP",
            "method": "POST",
            "form_fields": ["dataBody", "dataHeaders"],
        },
        "diagnostics": {
            "status": "ready",
            "warnings": warnings,
            "residual_risks": [],
        },
        "validation_targets": {
            "jsrpc_file": "generated/jsrpc_inject.js",
            "flask_file": "generated/flask_proxy.py",
            "burp_file": "generated/burp-autodecoder.md",
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(analysis, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps({"status": "ok", "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
