# 输出契约

本 Skill 使用单一规范化中间产物：`analysis_result.json`。

## 输入契约

Phase 0 的输入会被规范化为如下 JSON 结构：

```json
{
  "target_url": "https://example.com/login/index",
  "parameters": ["password"],
  "environment_constraints": "none",
  "fetch_example": "fetch(\"https://example.com/Login/CheckLogin\", {...})",
  "notes": []
}
```

规则：
- `target_url` 必须是完整的 `http` 或 `https` URL。
- `parameters` 必须是非空且去重后的字符串数组。
- `environment_constraints` 必须存在，即使其值为 `none`。
- `fetch_example` 是可选字段。

## Phase 1-3 产物契约

`artifacts/phase1_trace.json`

```json
{
  "browser": {
    "user_agent": "Mozilla/5.0 ...",
    "connected_via": "chrome-devtools-mcp",
    "tab_url": "https://example.com/login/index"
  },
  "request_replay": {
    "request_url": "https://example.com/Login/CheckLogin",
    "method": "POST",
    "content_type": "application/x-www-form-urlencoded; charset=UTF-8",
    "parameter_locations": {
      "password": "body"
    }
  },
  "evidence": [
    "page-side XHR/send observation captured the request before dispatch"
  ]
}
```

`artifacts/phase2_entrypoints.json`

```json
{
  "parameters": {
    "password": {
      "preferred_entrypoint": {
        "type": "object",
        "path": "window.loginVm.encryptPassword",
        "source_hint": "app.bundle.js:12031",
        "evidence": [
          "page-side stack output matched the request construction path",
          "observation code captured plaintext and ciphertext"
        ]
      },
      "candidates": []
    }
  }
}
```

`artifacts/phase3_dependencies.json`

```json
{
  "parameters": {
    "password": {
      "call_signature": {
        "args": ["plain_text"],
        "returns": "cipher_text",
        "async": false
      },
      "runtime": {
        "bind_this_path": "window.loginVm",
        "bootstrap": [],
        "globals": ["window.CryptoJS"]
      },
      "dependencies": [
        "window.CryptoJS.MD5"
      ]
    }
  }
}
```

## 规范化产物：`analysis_result.json`

最低要求结构如下：

```json
{
  "skill": {
    "name": "js-reverse-automation",
    "version": "1.3.0"
  },
  "input": {},
  "trace": {},
  "parameters": {
    "password": {
      "entrypoint": {},
      "call_signature": {},
      "runtime": {},
      "dependencies": []
    }
  },
  "jsrpc": {
    "group": "reverse",
    "action_name": "generate_password",
    "transport": {
      "ws_url": "ws://127.0.0.1:12080/ws?group=reverse&name=skill"
    }
  },
  "flask": {
    "listen_host": "127.0.0.1",
    "listen_port": 5000,
    "route": "/encode"
  },
  "burp": {
    "decoder_type": "HTTP",
    "method": "POST",
    "form_fields": ["dataBody", "dataHeaders"]
  },
  "diagnostics": {
    "status": "ready",
    "warnings": [],
    "residual_risks": []
  },
  "validation_targets": {
    "jsrpc_file": "generated/jsrpc_inject.js",
    "flask_file": "generated/flask_proxy.py",
    "burp_file": "generated/burp-autodecoder.md"
  }
}
```

强制规则：
- `skill`、`input`、`trace`、`parameters`、`jsrpc`、`flask`、`burp`、`diagnostics`、`validation_targets` 必须全部存在。
- `parameters` 必须覆盖 Phase 0 中请求的每一个参数。
- 每个参数都必须定义 `entrypoint.type`、`entrypoint.path` 或 `entrypoint.resolver_name` / `entrypoint.resolver_path`、`call_signature.async`，以及 `runtime.bind_this_path` 或 `runtime.bind_this_mode`。
- `runtime.bind_this_mode` 支持 `window`、`global`、`entrypoint_parent`、`none` 或 `null`；未指定 `bind_this_path` 时生成器按该模式决定 `this` 绑定。
- `jsrpc.action_name` 必须是确定性的，并与生成文件中的值一致。
- `diagnostics.status` 必须是 `ready`、`partial` 或 `failed` 之一。
- `trace` 中必须保留足够的请求级证据，至少能说明目标请求的 URL、方法、参数落点和关键证据来源。
- 如果使用了反检测 patch，`diagnostics.warnings` 或 `diagnostics.residual_risks` 中必须记录 patch 类型、影响范围和是否仅用于观察。

## 生成产物契约

### JSRPC 注入文件
- 必须基于 `analysis_result.json` 生成。
- 必须注册 `jsrpc.action_name` 中定义的 action。
- 必须包含：
  - 连接 bootstrap
  - 入口解析逻辑
  - `this` 绑定处理
  - sync/async 分支处理
- 成功返回约定：
  - 允许手工调用 `/go?group=...&action=...&param=111111`
  - 成功时应直接返回加密后的字符串结果，而不是嵌套对象
- 失败返回约定：
  - 返回带有固定前缀的字符串错误，例如 `__JSRPC_ERROR__:<parameter>:<name>:<message>`
- 必须支持JSRPC 注入代码有效性测试的链接（如http://127.0.0.1:12080/go?group=fausto&action=generate_password_md5&param=111111）
### Flask 代理文件
- 必须基于 `analysis_result.json` 生成。
- 必须能在 Python 3 下成功编译。
- 必须暴露：
  - `GET /healthz`
  - `POST <flask.route>`
- 必须支持：
  - JSON 请求体改写
  - form-urlencoded 请求体改写
  - 通过 `dataHeaders` 传递可选请求头
- 必须支持Flask 代理代码有效性测试的链接（如curl -X POST http://127.0.0.1:5000/encode \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "dataBody=username=111111&password=111111&code=1234&role=000002"）
### Burp autoDecoder 文档
- 必须基于 `analysis_result.json` 生成。
- 必须说明：
  - 本地代理 URL
  - HTTP 方法
  - 必需表单字段
  - 返回契约
  - 验证步骤
  - 排障说明

### 校验报告
- 必须是 JSON。
- 必须列出：
  - `status`
  - `checks`
  - `warnings`
  - `failures`
  - `next_actions`

## Phase 9 经验库契约：`references/evolution_matrix.json`

最低要求结构如下：

```json
{
  "domains": {
    "example.com": {
      "last_action_name": "generate_password",
      "route": "/encode",
      "last_behavioral_features": ["dynamic_resolver_export"],
      "last_validation_fingerprint": "sha256:...",
      "updated_at": "2026-05-21",
      "notes": "resolver patch used"
    }
  },
  "behavioral_features": {
    "dynamic_resolver_export": {
      "fingerprint_keywords": ["resolver", "resolver_path", "resolver_name"],
      "successful_patch_strategy": "使用 resolver 策略定位动态导出的运行时入口",
      "failed_attempts": [],
      "success_count": 1,
      "ste": {
        "strategic_principle": "入口路径不稳定时，优先沉淀 resolver 而不是沉淀静态对象路径。",
        "tactical_manual": [],
        "applicable_scenarios": ["dynamic-resolver"]
      },
      "updated_at": "2026-05-21"
    }
  }
}
```

规则：
- `domains` 和 `behavioral_features` 必须始终是 JSON object。
- 更新必须是增量合并，不能覆盖无关域名或无关特征。
- 写入必须使用文件锁和原子替换，防止并发或异常中断损坏文件。
- `success_count` 只统计新的校验指纹，重复运行同一份产物不能重复递增。
