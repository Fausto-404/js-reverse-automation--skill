---
name: js-reverse-automation
description: 通过 chrome-devtools-mcp 连接真实浏览器，自动定位前端加密入口，生成 JSRPC 注入代码、Flask 代理和 Burp autoDecoder 对接文档。
metadata:
  version: "2.1.0"
  author: Fausto-404
---

# JS 逆向自动化

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
5. 验证输出

## 详细工作流
详见 `workflow/pipeline.md`

## 约束规则
详见 `constraints/rules.md`

## 参考资料（按需加载）
- 反调试：`references/antidebug-patterns.md`
- 复杂入口：`references/advanced-entrypoints.md`
- 证据收集：`references/evidence-collection.md`
- 能力边界：`references/capability-boundaries.md`
- 输出契约：`references/output-contract.md`

## Token 预算
- 单次调用：50,000 token
- 最大工具调用：20 次
- 停止条件：找到入口并验证通过 / 所有降级策略失败 / Token 预算耗尽
