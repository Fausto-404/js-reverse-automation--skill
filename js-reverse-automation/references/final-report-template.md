# 最终报告模板

验证通过！现在输出最终结果。

---

## JS 逆向分析完成　　<任务名称>

### 分析结果

- 加密函数：`<函数路径>`
- 加密方式：`<算法/编码/组合>`
- 入口路径：`<页面入口或运行时路径>`
- 置信度：`高`（网络请求 + 运行时 Hook 双重验证）

### 验证结果

| 测试 | 输入 | 输出 |
|---|---|---|
| JSRPC | `<plaintext>` | `<ciphertext/signature>` |
| Flask 代理 | `<original body>` | `<transformed body>` |

### 验证命令

```bash
curl -sS --get \
  --data-urlencode group=<group> \
  --data-urlencode action=<action> \
  --data-urlencode 'param={"parameter":"<parameter>","value":"<plaintext>"}' \
  http://127.0.0.1:12080/go
```

预期结果必须包含明文、最终请求体、密文/签名和最终业务响应。

### Flask 代理验证

```bash
curl --noproxy '*' -sS -X POST http://127.0.0.1:<flask_port>/<route> \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'dataBody=<完整的原始 URL-encoded 请求体>' \
  --data-urlencode 'dataHeaders=<可选的请求头 JSON>'
```

预期结果必须返回代理改写后的请求体，其中目标字段已完成加密或签名；如果配置了响应透传，还应包含最终业务响应。

### Burp autoDecoder 页面配置

以下 `<flask_port>` 必须替换为 `artifacts/flask_status.json` 中服务实际返回的 `port`。如果默认端口被占用，服务管理器会自动选择备用端口。

#### 请求体加密

- 加密接口：`http://127.0.0.1:<flask_port>/encode`。
- 选择“请求数据包”；不要同时选择“响应数据包”。两者是互斥方向。
- 原始数据包区域粘贴完整 HTTP 请求，不要只粘贴 body。
- “处理请求头”：仅当签名或加密依赖请求头时勾选，否则不勾选。
- “请求 base64 编码”：只有请求体进入接口前需要 Base64 编码时勾选。
- “请求自动 base64 解码”：只有接口需要先自动还原 Base64 请求体时勾选。
- “Proxy、Repeater 等模块真实调试”：需要在 Burp Proxy/Repeater 联调时勾选，否则不勾选。

#### 响应体解密

- 解密接口：`http://127.0.0.1:<flask_port>/decode`。
- 取消选择“请求数据包”，改为选择“响应数据包”，不能同时选择两个方向。
- 原始数据包区域粘贴完整 HTTP 响应，不要只粘贴 body。
- “处理响应头”：仅当响应解密依赖响应头时勾选，否则不勾选。
- “响应 base64 编码”：只有响应体进入接口前需要 Base64 编码时勾选。
- “响应自动 base64 解码”：只有接口返回 Base64、需要还原二进制响应时勾选。
- 响应方向传递 `requestorresponse=response`；请求方向传递 `requestorresponse=request`。

启用请求头或响应头处理时，接口必须返回 `请求头 + "\\r\\n\\r\\n\\r\\n\\r\\n" + 改写后的请求/响应体`。

### 关闭服务命令

```bash
kill $(lsof -t -i:12080)
kill $(lsof -t -i:<flask_port>)
```

### Burp autoDecoder 配置

- 加密接口：`http://127.0.0.1:<flask_port>/encode`
- 解密接口：`http://127.0.0.1:<flask_port>/decode`（无响应解密需求时留空）
- HTTP 方法：`POST`
- 表单字段：`dataBody`、`dataHeaders`

### 生成的产物

- `analysis_result.json`
- `generated/jsrpc_inject.js`
- `generated/flask_proxy.py`
- `generated/burp-autodecoder.md`
- `artifacts/validation_report.json`

### 对抗分析追加

- 对抗类型：`<反调试/反 Hook/环境检测/动态加载>`
- 探针健康：`<丢失补丁/重建错误/丢弃事件>`
- 差分结论：`<观察结果/干预结果>`
