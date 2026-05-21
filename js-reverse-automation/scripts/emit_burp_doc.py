#!/usr/bin/env python3
"""Generate Burp autoDecoder integration documentation from analysis_result.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--output", required=True, help="Generated markdown file path.")
    return parser.parse_args()


def load_json(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("analysis_result.json must contain a JSON object")
    return data


def build_doc(analysis: dict) -> str:
    flask = analysis["flask"]
    burp = analysis["burp"]
    jsrpc = analysis["jsrpc"]
    parameters = ", ".join(analysis.get("parameters", {}).keys())
    proxy_url = f"http://{flask['listen_host']}:{flask['listen_port']}{flask['route']}"

    return f"""# Burp autoDecoder Integration

## Overview
- Target URL: {analysis["input"]["target_url"]}
- Parameters handled: {parameters}
- Local proxy: `{proxy_url}`
- JSRPC action: `{jsrpc["action_name"]}`

## autoDecoder Configuration
- Decoder type: `{burp["decoder_type"]}`
- Method: `{burp["method"]}`
- URL: `{proxy_url}`

## Request Form Fields
- `dataBody`: original request body string
- `dataHeaders`: original request headers string, optional but recommended for `Content-Length` rewrites

## Return Contract
- Return only the new request body when header rewrite is not required.
- Return `dataHeaders + "\\r\\n\\r\\n\\r\\n\\r\\n" + dataBody` when header rewrite is required.

## Validation Steps
1. Start the browser-side JSRPC injection and confirm the action is registered.
2. Start the generated Flask proxy and call `GET /healthz`.
3. Configure Burp autoDecoder with the URL above.
4. Replay a request containing: {parameters}.
5. Confirm the target field is replaced and `Content-Length` stays consistent.
6. For CLI checks, prefer `curl -sS -w "\\n"` to force a newline after response.

## Troubleshooting
- If the proxy returns the original body, check whether the target parameter exists in `dataBody`.
- If Burp reports malformed headers, confirm the return value uses `\\r\\n` line separators and the four-CRLF header/body split.
- If the field is not updated, verify JSRPC group `{jsrpc["group"]}` and action `{jsrpc["action_name"]}` match the browser registration.
- If terminal output ends with `%` in zsh, that is usually the shell prompt shown after a response without trailing newline, not part of HTTP body.
"""


def main() -> int:
    args = parse_args()
    analysis = load_json(args.analysis)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_doc(analysis), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
