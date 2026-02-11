---
name: js-reverse-automation-bypass-debugger
description: 绕过无限 debugger（eval/new Function/constructor 注入），并伪装 toString 以降低完整性校验风险。仅在确认存在 debugger 反调试时启用。
---

# Bypass Debugger

用于移除 eval/new Function/constructor 中的 `debugger` 语句，并对 `Function.prototype.toString` 做最小伪装，降低函数完整性校验触发的概率。

## 先读这些信息
- 仅在确认存在 `debugger` 反调试（如 eval/new Function 动态拼接）时启用。
- 这是注入级“绕过”，不改变业务逻辑与调用关系，但会修改全局 `Function` 与 `eval` 行为。
- 若站点存在严格的函数完整性校验，应先评估风险再启用。

## 需要收集的输入
- 目标 URL（用于确定注入范围与时机）
- `debugger` 触发点或调用路径（可选）
- 是否允许修改 `Function.prototype.toString`

<label>目标网址：</label>
<input type="text" placeholder="https://example.com" />

<label>触发点说明（可选）：</label>
<input type="text" placeholder="如：eval 中含 debugger / new Function 频繁触发" />

<label>是否允许修改 toString：</label>
<input type="text" placeholder="yes / no" />

## 工作流程
1) 在页面加载早期注入（`document-start` 优先）。
2) 替换 `eval`、`Function`、`Function.prototype.constructor`：
   - 所有字符串参数中的 `debugger` 关键字被移除。
3) 伪装 `Function.prototype.toString`：
   - 对 `eval` / `Function` / `Function.prototype.constructor` 返回原生样式。
4) 触发原始流程验证是否停止进入断点。

## 产出
- 可直接注入的绕过片段（保持与 AntiDebug_Breaker 行为一致）：

```js
(() => {
  'use strict';

  const tempEval = eval;
  const tempToString = Function.prototype.toString;

  Function.prototype.toString = function () {
    if (this === eval) {
      return 'function eval() { [native code] }';
    } else if (this === Function) {
      return 'function Function() { [native code] }';
    } else if (this === Function.prototype.toString) {
      return 'function toString() { [native code] }';
    } else if (this === Function.prototype.constructor) {
      return 'function Function() { [native code] }';
    }
    return tempToString.apply(this, arguments);
  };

  window.eval = function () {
    if (typeof arguments[0] === 'string') {
      arguments[0] = arguments[0].replaceAll(/debugger/g, '');
    }
    return tempEval(...arguments);
  };

  const OriginalFunction = Function;
  Function = function () {
    for (let i = 0; i < arguments.length; i++) {
      if (typeof arguments[i] === 'string') {
        arguments[i] = arguments[i].replaceAll(/debugger/g, '');
      }
    }
    return OriginalFunction(...arguments);
  };

  Function.prototype = OriginalFunction.prototype;

  Function.prototype.constructor = function () {
    for (let i = 0; i < arguments.length; i++) {
      if (typeof arguments[i] === 'string') {
        arguments[i] = arguments[i].replaceAll(/debugger/g, '');
      }
    }
    return OriginalFunction(...arguments);
  };

  Function.prototype.constructor.prototype = Function.prototype;
})();
```

- 最终输出必须注明：`已启用技能: Bypass Debugger`

## 交付前检查
- `debugger` 是否不再触发
- `Function.prototype.toString` 返回值是否符合预期
- 目标页面核心功能是否未被影响
- 若存在完整性校验，确认未引入新异常
