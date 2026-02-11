---
name: js-reverse-automation-hook-close
description: 重写 window.close 以避免网站反调试关闭当前页面。仅在确认存在强制关闭时启用。
---

# hook close

重写 `window.close`，阻断页面被强制关闭。

## 先读这些信息
- 仅在确认存在强制关闭行为时启用。
- 会改变页面正常关闭行为，调试结束后应关闭。

## 需要收集的输入
- 是否需要阻断 `window.close`

<label>阻断 window.close：</label>
<input type="text" placeholder="yes / no" />

## 工作流程
1) 覆盖 `window.close` 为 no-op。
2) 触发相关逻辑确认是否阻断成功。

## 产出
- 可直接注入的 hook 片段：

```js
(() => {
  'use strict';
  window.close = function () {};
})();
```

- 最终输出必须注明：`已启用技能: hook close`

## 交付前检查
- 页面是否不再被强制关闭
- 功能是否未受影响
