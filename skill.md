---
name: js-reverse-automation
description: 通过 MCP 连接浏览器，为目标自动化搭建JS环境，定位签名/加密函数入口，生成 JSRPC 代码，创建 Flask 代理，并输出 Burp autoDecoder 配置。用于分析 JS 加密/签名逻辑、JSRPC代码生成、或搭建完整工具链的需求。
---

# JS 逆向自动化技能

## 补充模板引用
- 使用时先阅读本主技能，再按需加载补充模板：`JSRPC.md`（JSRPC 注入模板）、`flask.md`（Flask 代理模板）、`burp-autodecoder.md`（Burp autoDecoder 配置说明模板）。

## 使用本技能完成
- 通过 MCP 连接真实浏览器
- 定位 JS 中的签名/加密入口
- 基于模板生成 JSRPC 注入代码
- 构建 Flask 代理与 Burp autoDecoder 配置
- 验证端到端流程可用

## 需要收集的输入
- 目标 URL 或功能需求（如“生成 sign/enc”）
- 环境限制（浏览器版本、代理、插件）

<label>目标网址：</label>
<input type="text" placeholder="https://example.com" />

<label>需要分析的加密参数：</label>
<input type="text" placeholder="例如 sign / enc / token" />

<label>Fetch 示例（可选）：</label>
<textarea rows="6" placeholder="粘贴 fetch 请求示例，便于识别参数与签名位置"></textarea>


## 需要交付的输出
1. JSRPC 注入代码（模板 + 站点适配）
2. Flask 代理服务（API 封装 + 错误处理）
3. Burp autoDecoder 配置说明
4. **完整的加密/签名逻辑代码**（可直接复制用于人工调试）
5. 验证记录（示例调用 + 期望输出）

## 工作流程
### 阶段一：初始化与连接
1. 通过 MCP 连接浏览器
2. 加载目标页面并打开 DevTools

### 阶段二：分析与入口定位
1. 触发签名流程并抓取调用栈
2. 检查打包代码并定位 sign/encrypt等函数
3. 确认入口类型：全局 / 对象方法 / 动态 resolver

### 阶段三：生成与注入 JSRPC
1. 基于模板生成 JSRPC 注入代码
   - 配置入口路径或 resolver
   - 需要时绑定 `this`
   - 处理同步 / Promise 异步
   - 规范化输入/输出
   - 添加错误兜底
2. 注入并注册 JSRPC action
3. 验证 JSRPC 调用是否返回预期结果
4. 输出完整的加密/签名逻辑代码片段（含所需依赖与调用示例），便于人工调试

### 阶段四：构建服务端代理
1. 生成 Flask 代理
    - JSRPC 客户端连接
    - API 路由封装
    - 结构化错误处理
2. 启动服务并做健康检查

### 阶段五：集成与交付
1. 输出 Burp autoDecoder 配置说明
2. 端到端验证并记录结果
3. 提供维护建议与更新要点

## 交付前检查
- 入口定位稳定且可复现
- `this` 绑定正确
- Promise/异步处理正确
- 输入/输出规范化正确
- 错误有兜底且不影响调用
- Burp/Flask 配置端到端可用
- 加密/签名逻辑代码完整可独立运行
