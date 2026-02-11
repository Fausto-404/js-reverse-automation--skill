---
name: js-reverse-automation-hook-table
description: 覆盖 console.table 以绕过基于时间差的反调试或 console.table 诱导检测。仅在确认使用该手法时启用。
---

# Hook table

用于阻断 `console.table` 被用于时间差或 getter 触发的反调试逻辑。

## 先读这些信息
- 仅在确认站点依赖 `console.table` 进行时间差检测时启用。
- 这是最小改动：将 `console.table` 变成 no-op。

## 需要收集的输入
- 触发点说明（如：`console.table` 被频繁调用且触发异常）

<label>触发点说明（可选）：</label>
<input type="text" placeholder="如：console.table + performance.now 组合" />

## 工作流程
1) 覆盖 `console.table` 为 no-op。
2) 如站点做函数完整性校验，可补充 `Function.prototype.toString` 伪装（可选）。

## 产出
- 可直接注入的拦截片段：

```js
(() => {
  'use strict';
  console.table = function () {};
})();
```

- 最终输出必须注明：`已启用技能: Hook table`

## 交付前检查
- 时间差检测是否被解除
- 控制台功能是否可接受地退化
