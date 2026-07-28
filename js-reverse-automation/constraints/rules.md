# 约束规则

## 硬性约束
1. 不把模型推断直接标记为已验证事实
2. `high` 置信度必须包含真实运行时调用或真实差分匹配证据
3. 不批量执行未知 Webpack module factory
4. 默认不保留敏感字段原文
5. 主动调用候选前必须检查 `safe_to_invoke`
6. JSRPC 只负责调用页面真实函数，禁止重写加密算法
7. 没有真实入口和请求字段关联时，不得生成可用于 Burp 的成功转换

## 能力边界
- **能做**：页面导航、evaluate_script、initScript 预注入、Hook fetch/XHR/crypto/WebSocket/库、Webpack 模块捕获、证据驱动候选发现、差分验证
- **不能做**：闭包未导出函数、WASM 未导出内部函数、Service Worker 内部闭包、ES module import 拦截、VMP 静态还原、CSP WebSocket 绕过、跨域 iframe、VM 保护 JS

## 策略值
- `global_path`：函数在 window 上
- `runtime_hook`：通过 Hook 调用栈发现
- `webpack_export`：Webpack 模块导出
- `async_crypto`：异步加密
- `initscript_hook`：initScript Hook
- `static_ast`：静态 AST 分析
- `source_analysis`：源码分析 + Python 实现
- `manual_observed_only`：有证据但未确认
- `unsupported`：所有方法都失败

## 候选不变量
- `verified=true` 必须有至少一条 `verification` 类型证据
- `confidence=high` 必须同时满足 `verified=true`
- 所有候选必须标记来源
- 失败验证不得删除，应保留为负证据
