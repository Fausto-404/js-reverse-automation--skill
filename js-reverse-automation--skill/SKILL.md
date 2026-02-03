---
name: js-reverse-automation
description: 通过 MCP 连接浏览器，为目标自动化搭建 JS 环境，定位签名/加密函数入口，生成 JSRPC 代码，创建 Flask 代理，并输出 Burp autoDecoder 配置。用于分析 JS 加密/签名逻辑、JSRPC 代码生成、或搭建完整工具链的需求。
---

# JS 逆向自动化技能

用于 JS 逆向自动化：通过 MCP 连接真实浏览器，定位签名/加密入口，生成 JSRPC 注入代码，搭建 Flask 代理，并输出 Burp autoDecoder 配置，完成端到端验证。

## 先读这些信息
- 目标站点的请求与签名参数（如 `sign` / `enc` / `token`）。
- 运行环境限制（浏览器版本、代理、插件、是否允许注入）。
- 现有请求示例（Fetch/抓包/接口说明）用于定位签名位置。

## 参考模板（按需加载）
- JSRPC 注入模板：`references/JSRPC.md`
- Flask 代理模板：`references/flask.md`
- Burp autoDecoder 说明模板：`references/burp-autodecoder.md`

## 需要收集的输入
- 目标 URL 或功能需求（如“生成 sign/enc”）
- 需要分析的加密参数名称
- 可复现的请求示例（可选）
- 环境限制（浏览器版本、代理、插件）

<label>目标网址：</label>
<input type="text" placeholder="https://example.com" />

<label>需要分析的加密参数：</label>
<input type="text" placeholder="例如 sign / enc / token" />

<label>Fetch 示例（可选）：</label>
<textarea rows="6" placeholder="粘贴 fetch 请求示例，便于识别参数与签名位置"></textarea>

## 工作流程
1) **初始化与连接**
   - 通过 MCP 连接真实浏览器。
   - 打开目标页面与 DevTools。

2) **分析与入口定位**
   - 触发加密/签名流程并捕获调用栈。
   - 定位打包代码中的 `sign` / `encrypt` 入口。
   - 确认入口类型：全局函数 / 对象方法 / 动态 resolver。

3) **生成与注入 JSRPC**
   - 基于模板生成注入代码：
     - 入口路径或 resolver 配置
     - 必要时绑定 `this`
     - 同步或 Promise 异步处理
     - 规范化输入/输出
     - 错误兜底
   - 注入并注册 JSRPC action。
   - 验证调用是否返回预期结果。
   - 输出完整加密/签名逻辑代码（含依赖与调用示例）。

4) **构建服务端代理**
   - 基于模板生成 Flask 代理：
     - JSRPC 客户端连接
     - API 路由封装
     - 结构化错误处理
   - 启动服务并做健康检查。

5) **集成与交付**
   - 输出 Burp autoDecoder 配置说明。
   - 端到端验证并记录结果。
   - 提供维护建议与更新要点。

## 产出
- JSRPC 注入代码（模板 + 站点适配）
- Flask 代理服务（API 封装 + 错误处理）
- Burp autoDecoder 配置说明
- 完整的加密/签名逻辑代码（可直接复制用于人工调试）
- 验证记录（示例调用 + 期望输出）

## 交付前检查
- 入口定位稳定且可复现
- `this` 绑定正确
- Promise/异步处理正确
- 输入/输出规范化正确
- 错误兜底完整且不影响调用
- Burp/Flask 配置端到端可用
- 加密/签名逻辑代码完整可独立运行
