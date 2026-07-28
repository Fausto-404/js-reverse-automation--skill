# 能力边界

## 能做
- 页面导航、evaluate_script、initScript 预注入
- Hook fetch/XHR/crypto/WebSocket/库
- Webpack 模块捕获
- 证据驱动候选发现
- 差分验证
- JSRPC/Flask/Burp 产物生成

## 不能做
- 闭包未导出函数
- WASM 未导出内部函数
- Service Worker 内部闭包
- ES module import 拦截
- VMP 静态还原
- CSP WebSocket 绕过
- 跨域 iframe
- VM 保护 JS

## 模块内部加密
当加密函数在模块内部时，按顺序尝试：
1. initScript Hook `Object.defineProperty`
2. initScript Hook `Function.prototype`
3. 搜索 RSA 实例
4. 静态 AST 分析
5. 源码分析 + Python 实现

## 置信度
- `high`：真实运行时调用 + 差分验证
- `medium`：单一证据源
- `low`：仅启发式匹配

## 策略值
- `global_path`：函数在 window 上
- `runtime_hook`：Hook 调用栈发现
- `webpack_export`：Webpack 模块导出
- `async_crypto`：异步加密
- `initscript_hook`：initScript Hook
- `static_ast`：静态 AST 分析
- `source_analysis`：源码分析
- `manual_observed_only`：有证据未确认
- `unsupported`：所有方法失败
