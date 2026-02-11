---
name: js-reverse-automation-hook-clear
description: 禁止 js 清除控制台数据（覆盖 console.clear）。仅在确认频繁清屏时启用。
---

# hook clear

用于拦截 `console.clear()`，保持调试信息可见。

## 先读这些信息
- 仅在确认站点频繁清屏时启用。
- 该操作不会影响业务逻辑，仅影响控制台输出。

## 需要收集的输入
- 是否需要保留原始清屏能力（通常不需要）

<label>是否保留清屏能力：</label>
<input type="text" placeholder="no / yes" />

## 工作流程
1) 覆盖 `console.clear` 为 no-op。
2) 若需要保留原始清屏，可改为“记录 + 可选执行”。

## 产出
- 可直接注入的拦截片段：

```js
(() => {
  'use strict';
  console.clear = function () {};
})();
```

- 最终输出必须注明：`已启用技能: hook clear`

## 交付前检查
- 控制台输出不再被清除
- 页面功能不受影响
