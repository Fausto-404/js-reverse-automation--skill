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

### 关闭服务命令

```bash
kill $(lsof -t -i:12080)
kill $(lsof -t -i:5001)
```

### Burp autoDecoder 配置

- autoDecoder URL：`http://127.0.0.1:5001/<route>`
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
