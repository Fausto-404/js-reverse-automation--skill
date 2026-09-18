#!/usr/bin/env python3
"""回归检查生成的 JSRPC/Flask/Burp 交付契约。"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("jsra_delivery_contract_proxy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载代理：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_endpoint_normalization(module) -> dict[str, Any]:
    calls: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"data": {"requestBody": "loginId=admin&password2=ENC"}}

    def fake_get(url: str, **_: Any) -> FakeResponse:
        calls.append(url)
        return FakeResponse()

    original_get = module.requests.get
    try:
        module.requests.get = fake_get
        transform = module.CONFIG["transforms"][0]
        module.jsrpc_call(transform.get("action", module.CONFIG["jsrpc"]["action"]), "123456", transform)
    finally:
        module.requests.get = original_get

    if len(calls) != 1 or not calls[0].endswith("/go") or calls[0].endswith("/go/go"):
        raise AssertionError(f"JSRPC endpoint 归一化失败：{calls}")
    return {"ok": True, "called": calls[0]}


def check_packet_modes(module) -> dict[str, Any]:
    transform = module.CONFIG["transforms"][0]
    path = str(transform.get("path") or transform.get("id") or "password")
    field = path.removeprefix("$.").split(".")[-1]
    if transform.get("delivery_mode") == "request_body":
        fake_result = f"loginId=admin&{field}=ENC(123456)"
        expected_body = fake_result
    else:
        fake_result = "ENC(123456)"
        expected_body = f"loginId=admin&{urlencode({field: 'ENC(123456)'})}"
    module.jsrpc_call = lambda _action, _value, _transform: fake_result
    client = module.app.test_client()
    raw_packet = (
        "POST /newlogin/login.do?appName=arena&fromSite=77 HTTP/1.1\r\n"
        "Host: 127.0.0.1:8123\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        "Connection: close\r\n\r\n"
        f"loginId=admin&{field}=123456"
    )
    packet_response = client.post("/encode", data=raw_packet, content_type="application/octet-stream")
    packet_text = packet_response.get_data(as_text=True)
    if packet_response.status_code != 200:
        raise AssertionError(f"整包模式失败：HTTP {packet_response.status_code}: {packet_text}")
    if expected_body not in packet_text:
        raise AssertionError(f"整包模式没有替换 body：{packet_text}")
    expected_length = len(expected_body.encode())
    if f"Content-Length: {expected_length}" not in packet_text:
        raise AssertionError(f"整包模式没有同步 Content-Length：{packet_text}")

    wrapper_response = client.post(
        "/encode",
        data={"dataBody": f"loginId=admin&{field}=123456", "requestorresponse": "request"},
        content_type="application/x-www-form-urlencoded",
    )
    wrapper_text = wrapper_response.get_data(as_text=True)
    expected_wrapper = expected_body
    if wrapper_response.status_code != 200 or wrapper_text != expected_wrapper:
        raise AssertionError(f"dataBody wrapper 失败：HTTP {wrapper_response.status_code}: {wrapper_text}")
    return {"ok": True, "packet_status": packet_response.status_code, "wrapper_status": wrapper_response.status_code}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated Flask delivery contracts.")
    parser.add_argument("--proxy", required=True, help="Generated flask_proxy.py path.")
    parser.add_argument("--output", required=True, help="JSON report path.")
    args = parser.parse_args()
    module = load_module(Path(args.proxy))
    result = {
        "passed": True,
        "proxy": str(Path(args.proxy).resolve()),
        "endpoint_normalization": check_endpoint_normalization(module),
        "packet_modes": check_packet_modes(module),
        "live_action_required": True,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
