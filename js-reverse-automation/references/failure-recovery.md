# 失败恢复

本文档定义了在不破坏主链路的前提下，如何诊断、记录并恢复失败。

## 失败记录格式

每个失败或警告都应使用如下结构：

```json
{
  "phase": 2,
  "code": "ENTRYPOINT_NOT_CONFIRMED",
  "summary": "Found keyword matches but no runtime evidence.",
  "evidence": [
    "page-side fetch/XHR observation captured the parameter after encryption but before request send"
  ],
  "impact": "Cannot generate a reliable JSRPC artifact.",
  "next_action": "Add hook output or stack-frame evidence for the candidate entrypoint."
}
```

## 分阶段恢复规则

### Phase 0
- 缺少必填字段
  - 立即停止。
  - 按输入契约的精确格式要求补齐字段。
- URL 非法
  - 立即停止。
  - 要求提供完整的 `http` 或 `https` URL。

### Phase 1
- 浏览器连接失败
  - 记录浏览器版本、MCP 附着错误，以及标签页是否可达。
  - 在确认目标浏览器实例已经打开后重试一次。
- 请求复现失败
  - 检查可选 fetch 示例是否可以手工复现。
  - 如果不能，捕获最接近的网络请求，并将 Phase 1 标记为失败。
- 请求过多，无法确认目标请求
  - 先做单变量对比，只改变一个目标输入值。
  - 结合 `references/network-capture.md` 中的收缩规则，确认首选请求后再进入源码定位。
- 浏览器内成功，但页面外复现失败
  - 优先怀疑协议层差异、预热请求、Header/Cookie 依赖或频率限制。
  - 结合 `references/protocol-resilience.md` 记录差异，不要直接回退为“算法未确认”。

### Phase 2
- 存在候选入口，但没有运行时证据
  - 标记为 `partial`。
  - 在未缩小到一个带证据的首选入口之前，不得继续。
- 只能命中加密库，回不到业务入口
  - 标记为 `partial`。
  - 先补页面内调用栈、序列化点或业务函数 Hook，不得把库函数直接写入最终入口。
- 检测到反调试
  - 从 `references/antidebug/` 中选择匹配范围最小的规则。
  - 记录风险和引用的精确文件。

### Phase 3
- 运行时上下文不完整
  - 记录缺失的全局对象、模块或 `this` 绑定。
  - 保持产物为 `partial`，并阻止继续生成代码。
- 异步行为未知
  - 视为阻断项。
  - 必须通过真实调用或 Promise 检查来确认。
- 协议层依赖不清楚
  - 记录哪些条件是在页面内观测到的，哪些已经被证明是生成链路必需条件。
  - 不要把未验证的 Header、Cookie 或连接特征直接固化进最终产物。

### Phase 4-7
- 产物生成成功，但校验失败
  - 保留已生成文件。
  - 将校验报告标记为失败。
  - 输出文件级修复建议。

### Phase 8
- 校验检查失败
  - 返回 `status=failed`。
  - 包含扁平化的 `next_actions` 列表。

## 强制诊断信息

当任一阶段失败时，最终输出必须包含：
- failed phase id
- failure code
- summary
- evidence
- impact
- next action
- 下游生成是否被跳过，或是否带警告继续完成

## 反调试规则选择

将 `references/antidebug/` 视作规则文档，而不是嵌套 Skill：
- `debugger-loop.md`
  - 重复触发的 `debugger`、`eval`、`Function`、`constructor` 篡改
- `console-detect.md`
  - console 方法覆写、`console.clear`、`console.table`、日志抑制
- `timer-check.md`
  - 时间差检查、Promise 时序、性能探针
- `env-detect.md`
  - 窗口大小、devtools、webdriver、UA 检查
- `proxy-guard.md`
  - 因代理、扩展、history、close、redirect hook 导致的请求复现阻断
- `dynamic-alias.md`
  - 混淆别名、动态 resolver、加密包装器、异步间接层

只有当某条规则确实改变了调查路径或风险面时，才应引用它。

## 恢复原则
- 先补网络证据，再补源码证据，再补 Hook 证据。
- 只有当反检测真正阻断链路时，才进入 patch 验证。
- 协议层问题优先记录为差异与风险，只有验证过的依赖才能进入最终生成逻辑。
- 任何 patch 都不得被默认为最终生成代码的依赖。
