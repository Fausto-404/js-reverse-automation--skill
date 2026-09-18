---
name: js-reverse-automation
description: 通过 chrome-devtools-mcp 连接真实浏览器，自动定位前端加密入口，生成 JSRPC 注入代码、Flask 代理和 Burp autoDecoder 对接文档。
metadata:
  author: Fausto-404
---

# JS 逆向自动化

通过 JSRPC 与真实浏览器完成前端加密入口定位、运行时取证、对抗分析、验证和工程化交付。浏览器连接、文档身份和 action 级结果必须形成可复核证据链。

## 适用场景
- 登录/注册页面密码加密
- API 请求签名
- 表单字段加密
- 响应数据解密

## 输入格式
```
Target URL: https://xxx/login
Parameters To Analyze: password
Optional Fetch Example: fetch("https://xxx/api/login", {...})
```

## 核心流程
1. **预分析 Fetch Example**（如果有）→ 提取加密算法、参数格式、目标 URL
2. 打开页面 → 注入 Hook → 触发目标动作
3. 捕获网络请求 → 定位加密函数
4. 注册 JSRPC → 生成 Flask/Burp 产物
5. 验证输出 → 按标准最终交付格式输出完整结果

遇到反调试、反 Hook、JSVMP、动态 Cookie、环境型签名或动态加载时，先生成并运行 `adversarial_runtime_probe.js`；只有观察到明确对抗信号后，才使用 `--mode intervene` 或源码级插桩。

## 详细工作流
详见 `workflow/pipeline.md`

## 对抗与验证能力

- **对抗运行时探针**：反调试、完整性检查、环境属性、动态代码、响应链、Worker/WebSocket/WASM/iframe 加载事件。
- **持久 Hook**：页面重新赋值后自动检测丢失并尝试恢复；所有 Patch 可通过 `uninstall()` 回滚。
- **Hook 组合**：对抗探针与运行时加密探针共享 `__JSRA_HOOK_REGISTRY__`，同一 API 采用可卸载的分层包装，外部替换只触发一次重建。
- **安全证据**：原始捕获采用有界循环引用安全快照，避免 CryptoJS/JSEncrypt 对象导致导出失败。
- **浏览器会话契约**：注入、调用和导航绑定到当前 tab/document；断线、超时、暂停或导航后不复用旧引用，避免把未知状态误报成成功。
- **控制流观测**：可选观察控制台清理、历史导航、存储访问和关闭页面等干扰信号；只有明确启用干预模式时才阻止受控动作，默认不改变业务行为。
- **源码级保守插桩**：针对明确选择的简单属性读取生成 tap，不默认改写全量代码。
- **对抗差分**：比较基线与干预后的事件、请求、错误和新增证据；差分报告不等于目标已被绕过。
- **完整交付**：标准 JSRPC 产物在调用期间捕获最终 `fetch/XHR` 网络请求，返回明文、最终 route、密文/签名请求体、HTTP 状态和业务响应；最终结果同时保留分析结果、验证表、可复制命令、关闭命令、Burp autoDecoder 配置和生成产物；对抗信息作为补充证据追加。
- **能力边界**：验证码、WebAuthn、设备证明、跨域隔离 Realm 和未导出的 WASM 内部函数仍需保留为人工或 unsupported 路径。

## 交付前强制检查

生成 Flask 代理后必须执行：

```bash
python3 scripts/check_delivery_contract.py \
  --proxy generated/flask_proxy.py \
  --output artifacts/delivery_contract.json
```

该检查必须同时通过 JSRPC 地址归一化、Burp `application/octet-stream` 完整报文、`Content-Length` 重建和 `dataBody` wrapper 四项回归。`jsrpc.base_url` 可以填写 `http://127.0.0.1:12080` 或 `http://127.0.0.1:12080/go`，生成器必须保证最终只请求一次 `/go`。

端口监听不等于 JSRPC 可用。最终报告前还必须使用真实浏览器执行 action 级 smoke test，并确认返回 `plaintext`、最终 route、非空 `requestBody`、HTTP 状态和业务响应；`/list` 无 action、`/go` 返回 400 或 Flask 返回 502 时，不得写“Flask 代理验证通过”。

将 action 级结果保存后执行：

```bash
python3 scripts/validate_browser_evidence.py \
  --input artifacts/jsrpc_smoke.json \
  --output artifacts/browser_evidence.json
```

如果同时保存了浏览器桥接状态、`tabId` 和当前 `documentId`，再增加 `--require-session`。超时、断线、待恢复或文档身份变化只能标记为未确认，不能通过重放旧请求来补证据。

Burp 整包模式必须支持外层 `Content-Type: application/octet-stream`，从内层 HTTP 报文识别真实 Content-Type，返回完整改写报文；请求/响应方向仍每次只能选择一个，解密接口和加密接口可以同时配置。

## 约束规则
详见 `constraints/rules.md`

## 参考资料（按需加载）
- 反调试：`references/antidebug-patterns.md`
- 复杂入口：`references/advanced-entrypoints.md`
- 证据收集：`references/evidence-collection.md`
- 能力边界：`references/capability-boundaries.md`
- 输出契约：`references/output-contract.md`
- 最终报告模板：`references/final-report-template.md`
- 对抗运行时：`references/adversarial-runtime.md`
- 浏览器会话与证据：`references/browser-session-contract.md`

## Token 预算
- 单次调用：50,000 token
- 最大工具调用：20 次
- 停止条件：找到入口并验证通过 / 所有降级策略失败 / Token 预算耗尽
