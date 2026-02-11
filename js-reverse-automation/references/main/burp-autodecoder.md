---
name: burp-autodecoder-config
version: 1.0
language: zh-CN
description: 生成 Burp Suite autoDecoder 的配置说明文档，用于把请求体/头部交给本地代理服务进行编码或签名回填。
---

# Burp autoDecoder 配置说明（技能文档）

## 目标
- 输出可直接使用的 autoDecoder 配置说明
- 明确入参与返回格式
- 说明与本地代理（如 Flask）对接的约定

## 适用场景
- 需要在 Burp 中自动回填签名/加密字段
- 需要在发送前动态修改请求体或头部
- 与 JSRPC/本地服务联动

## 输入
- 代理服务地址（例如 `http://127.0.0.1:8888/encode`）
- 请求体类型（`application/json` 或 `application/x-www-form-urlencoded`）
- 需要改写的字段名（如 `sign`、`password`）
- 是否需要回填请求头（通常为 `Content-Length`）

## 输出
- autoDecoder 配置说明
- 参数传递约定
- 常见问题与排查建议

## 配置说明模板
### 1) Decoder 类型与地址
- Decoder 类型：`HTTP`
- URL：`http://127.0.0.1:8888/encode`
- Method：`POST`

### 2) Body 参数传递
autoDecoder 将原始请求体和请求头作为表单字段传递给代理服务。
- `dataBody`：原始请求体（完整字符串）
- `dataHeaders`：原始请求头（完整字符串，可选）

### 3) 代理服务返回格式
代理服务需返回：
- 仅请求体：直接返回新的请求体字符串
- 请求头+请求体：返回 `dataHeaders + "\r\n\r\n\r\n\r\n" + dataBody`

### 4) Content-Length 更新建议
- 若返回包含 headers，代理应更新 `Content-Length`
- 若未回传 headers，则由 Burp 使用新的 body 自动处理

## 示例（结合 Flask 代理）
- autoDecoder 请求体：
  - `dataBody`：`username=111111&password=raw&code=1234&role=000002`
  - `dataHeaders`：包含 `Content-Length` 的原始头
- 代理返回：
  - `password` 被替换为加密值
  - `Content-Length` 同步更新

## 常见问题
- Q: 返回后请求头乱码？
  - A: 确保返回头部字符串使用 `\r\n` 行分隔，头体间用 `\r\n\r\n\r\n\r\n` 分隔。
- Q: Content-Length 不匹配？
  - A: 代理返回时用新 body 的长度替换旧长度。
- Q: 表单与 JSON 都要支持？
  - A: 代理端先尝试 JSON 解析，失败后按 URL 编码表单处理。

## 交付清单
- autoDecoder 配置说明
- 代理端入参与返回格式
- 一条可执行示例（含字段替换说明）

