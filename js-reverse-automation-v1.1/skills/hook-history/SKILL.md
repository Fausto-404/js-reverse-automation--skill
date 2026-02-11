---
name: js-reverse-automation-hook-history
description: 重写 history.go/back 以避免网站反调试返回上一页或特定历史页面。仅在确认存在强制回退时启用。
---

# hook history

重写 `history.go` 与 `history.back`，阻断页面被强制回退。

## 先读这些信息
- 仅在确认存在强制回退行为时启用。
- 会改变页面正常导航行为，调试结束后应关闭。

## 需要收集的输入
- 是否需要阻断 `history.go` 与 `history.back`

<label>阻断 history.go/back：</label>
<input type="text" placeholder="yes / no" />

## 工作流程
1) 覆盖 `history.go` 与 `history.back` 为 no-op。
2) 触发相关逻辑确认是否阻断成功。

## 产出
- 可直接注入的 hook 片段：

```js
(() => {
  'use strict';
  window.history.go = function () {};
  window.history.back = function () {};
})();
```

- 最终输出必须注明：`已启用技能: hook history`

## 交付前检查
- 页面是否不再被强制回退
- 功能是否未受影响
