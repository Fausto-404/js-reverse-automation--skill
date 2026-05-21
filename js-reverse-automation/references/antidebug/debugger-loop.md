# Debugger 循环规则

当调查过程被重复触发的 `debugger` 或动态注入 `debugger` 的代码阻断时，使用此规则。

## 现象
- 在目标请求发送前，DevTools 持续暂停。
- `eval`、`Function` 或 `constructor` 接收到包含 `debugger` 的源码字符串。
- 同一段调用栈反复出现，却始终到不了参数变更点。

## 处理方式
- hook `eval`、`Function` 和 `Function.prototype.constructor`。
- 只从动态生成的源码文本中移除 `debugger`。
- 如果存在完整性检查，明确记录覆写 `Function.prototype.toString` 的风险。

## 需要记录的证据
- 触发问题的 API（`eval`、`Function` 或 `constructor`）
- 来源提示或调用栈帧
- 是否需要伪装 `toString`

## 风险说明
- 此规则会改变全局执行行为，并可能触发完整性检查。应尽量缩小作用范围，并记录影响面。

## 可直接注入的 Hook 片段

### 1. 绕过动态 `debugger`

适用场景：
- `eval`
- `new Function`
- `Function.prototype.constructor`
- 动态拼接代码后持续命中 `debugger`

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

## 使用后检查
- 页面是否不再反复断在 `debugger`
- `Function.prototype.toString` 相关检查是否未触发新异常
- 业务主流程是否仍可正常执行
