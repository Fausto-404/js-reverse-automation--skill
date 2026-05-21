# Hook 调试规则

本规则用于在 Phase 2-3 对高价值节点做最小 Hook，目标是补齐入口、调用签名、依赖和运行时上下文证据。

## 适用范围
- 网络证据已经锁定目标请求，但还缺少入口函数证据。
- 需要确认参数在某个函数调用前后是否发生变化。
- 需要确认返回值、`this` 绑定、异步行为或全局依赖。

## 最小 Hook 原则
- 先 Hook 通用边界，再 Hook 业务函数。
- 先记录，再改写；默认不要 replace 原函数。
- 单次只增加一个观测点，避免多个 Hook 混在一起污染证据。
- 页面已加载时优先用 `evaluate_script` 注入观测代码。
- 如果页面会刷新或跳转，用 `navigate_page(initScript=...)` 在下一次导航前预注入。

## 推荐 Hook 顺序
1. `window.fetch`
2. `XMLHttpRequest.prototype.open`
3. `XMLHttpRequest.prototype.send`
4. `JSON.stringify`
5. 明确命中的业务函数
6. 必要时再补 `eval` / `Function` / Promise 相关节点

## 每个 Hook 至少记录
- Hook 点路径
- 命中条件
- 入参摘要
- 返回值摘要
- 调用栈摘要
- 是否改变页面行为
- 注入方式：`evaluate_script` 或 `navigate_page(initScript=...)`

## 入口确认规则
- 业务函数 Hook 至少要证明以下两点之一：
  - 明文输入与请求中的目标参数存在可验证映射关系
  - 函数返回值直接进入请求体、Header 或 Cookie
- 如果只看到加密库内部调用，而没有调用方上下文，不足以认定为最终入口。

## 依赖提取规则
- 明确记录：
  - `this` 绑定来自哪里
  - 依赖哪些全局对象或闭包对象
  - 是否需要异步等待
  - 是否需要页面先完成某个 bootstrap
- 这些信息最终必须进入 `artifacts/phase3_dependencies.json` 和 `analysis_result.json`。

## 风险控制
- 不要默认冻结大量原型。
- 不要为了方便观测而全局替换所有加密 API。
- 一旦某个 Hook 造成业务分支变化，先回退到更小范围，再继续。
