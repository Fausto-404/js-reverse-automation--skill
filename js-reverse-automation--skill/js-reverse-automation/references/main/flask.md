---
name: flask-jsrpc-proxy-template
description: 面向 Burp autoDecoder 的 Flask 代理服务模板，用于将请求体交给 JSRPC 生成加密后的结果并回填。适用于需要自动签名/加密参数回填的场景。
---

# Flask JSRPC 代理工具模板

## 目标
- 接收 Burp autoDecoder 的编码请求
- 解析请求体
- 调用 JSRPC 生成加密/签名
- 回填加密/签名后的值并返回给 Burp

## 输入
- `dataBody`：autoDecoder 传入的请求体（默认表单字段）
- `dataHeaders`：autoDecoder 传入的请求头（默认表单字段）

## 输出
- 更新后的请求体（可包含更新后的请求头）

## 可配置项
- JSRPC 地址（如 `http://127.0.0.1:12080/go`）
- JSRPC 参数：`group`、`action`
- 签名字段名（默认 `sign`）
- 超时时间、日志级别

## 代码模板
```python
from flask import Flask, request
import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

JSRPC_URL = "http://127.0.0.1:12080/go"
JSRPC_GROUP = "fausto"
JSRPC_ACTION = "generate_sign"
SIGN_FIELD = "sign"
TIMEOUT = 5

@app.route('/encode', methods=['POST'])
def handle_encode():
    app.logger.info("--- 收到来自 Burp/autoDecoder 的编码请求 ---")

    data_body = request.form.get('dataBody', '')
    data_headers = request.form.get('dataHeaders', '')

    if not data_body:
        app.logger.error("未接收到 dataBody")
        return data_headers + "\r\n\r\n\r\n\r\n" + data_body if data_headers else data_body

    try:
        json_data = json.loads(data_body)
    except json.JSONDecodeError as e:
        app.logger.error(f"解析 JSON 失败: {e}")
        return data_headers + "\r\n\r\n\r\n\r\n" + data_body if data_headers else data_body

    old_sign = json_data.pop(SIGN_FIELD, None)
    app.logger.info(f"已移除旧签名: {old_sign}")

    params_for_jsrpc = {
        "group": JSRPC_GROUP,
        "action": JSRPC_ACTION,
        "param": json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))
    }

    try:
        jsrpc_response = requests.get(JSRPC_URL, params=params_for_jsrpc, timeout=TIMEOUT)
        jsrpc_response.raise_for_status()
        result = jsrpc_response.json()
        new_sign = result.get('data', '')
    except requests.exceptions.RequestException as e:
        app.logger.error(f"调用 JSRPC 失败: {e}")
        new_sign = ""
    except json.JSONDecodeError as e:
        app.logger.error(f"解析 JSRPC 返回失败: {e}")
        new_sign = ""

    json_data[SIGN_FIELD] = new_sign
    new_data_body = json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))

    if data_headers:
        new_content_length = len(new_data_body)
        new_headers = data_headers.replace(
            f"Content-Length: {len(data_body)}",
            f"Content-Length: {new_content_length}"
        )
        return new_headers + "\r\n\r\n\r\n\r\n" + new_data_body

    return new_data_body

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=True)
```

## 使用说明
- Burp autoDecoder 将请求体与头部作为表单字段传入 `/encode`
- 服务返回的内容将被 autoDecoder 用于替换原始请求

## 注意事项
- JSRPC 端口/参数需与注入端一致
- 若加密依赖更多字段，需在加密前补齐
