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
    jsrpc_server = analysis.get("jsrpc_server", {})
    flask_server = analysis.get("flask_server", {})
    parameters = list(analysis.get("parameters", {}).keys())
    proxy_url = f"http://{flask['listen_host']}:{flask['listen_port']}{flask['route']}"
    jsrpc_port = jsrpc_server.get("port", 12080)
    flask_port = flask_server.get("port", flask.get("listen_port", 5000))
    group = jsrpc["group"]
    action = jsrpc["action_name"]
    target_url = analysis["input"]["target_url"]

    # Build sample dataBody with placeholder values
    sample_params = "&".join(f"{p}=<plaintext>" for p in parameters)
    sample_data_body = f"username=testuser&{sample_params}&other_field=value"

    return f"""# Burp autoDecoder Integration

## Overview
- Target URL: {target_url}
- Parameters handled: {", ".join(parameters)}
- Local proxy: `{proxy_url}`
- JSRPC action: `{action}`
- JSRPC group: `{group}`

## Burp autoDecoder 配置步骤

### 1. 启动 JSRPC 服务器
```bash
python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action start
```

### 2. 启动 Flask 代理
```bash
python3 scripts/manage_services.py --service flask --analysis analysis_result.json --flask-file generated/flask_proxy.py --output artifacts/flask_status.json --action start
```

### 3. 在浏览器中注入 JSRPC
在 chrome-devtools-mcp 中：
- 刷新目标页面
- 注入 Hlclient（`scripts/JsEnv_Dev.js`）
- 注入 `generated/jsrpc_inject.js` 完整内容
- 验证：`curl 'http://127.0.0.1:{jsrpc_port}/list'` 确认 `{group}` 已注册

### 4. 配置 Burp autoDecoder
- 打开 Burp Suite → Project Options → Sessions → Rule Actions → Add → Run a macro
- 或使用 Burp 自动 Decoder 插件：
  - Decoder type: `{burp["decoder_type"]}`
  - Method: `{burp["method"]}`
  - URL: `{proxy_url}`
  - Form field `dataBody`: 原始请求体
  - Form field `dataHeaders`: 原始请求头（可选）

### 5. Validation Steps
```bash
# 验证 JSRPC 可用
curl 'http://127.0.0.1:{jsrpc_port}/go?group={group}&action={action}&param=test123'

# 验证 Flask 代理
curl -X POST {proxy_url} \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  --data-urlencode "dataBody={sample_data_body}"

# 验证 Flask 健康检查
curl 'http://127.0.0.1:{flask_port}/healthz'
```

### 6. 在 Burp 中重放请求
拦截目标请求（如 `{target_url}`），确认 `{", ".join(parameters)}` 字段被替换为加密后的值。

## 关闭服务
```bash
python3 scripts/manage_services.py --service jsrpc --analysis analysis_result.json --output artifacts/jsrpc_status.json --action stop
python3 scripts/manage_services.py --service flask --analysis analysis_result.json --output artifacts/flask_status.json --action stop
```

## Troubleshooting
- 如果代理返回原始 body，检查 `dataBody` 中是否包含目标参数 `{", ".join(parameters)}`
- 如果 Burp 报告 header 格式错误，确认返回值使用 `\\r\\n` 行分隔符和四个 CRLF 的 header/body 分割
- 如果字段未更新，验证 JSRPC group `{group}` 和 action `{action}` 是否与浏览器注册一致
- 如果终端输出以 `%` 结尾（zsh），那是 shell 提示符，不是 HTTP body 的一部分
- 如果 JSRPC 超时，检查浏览器页面是否已刷新（旧 WebSocket 连接可能已断开）
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
