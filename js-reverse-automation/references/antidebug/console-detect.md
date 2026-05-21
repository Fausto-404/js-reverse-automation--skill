# Console 检测规则

当目标站点篡改 console API，用于检测 DevTools 或隐藏运行时证据时，使用此规则。

## 现象
- `console.log`、`console.table` 或 `console.clear` 被覆写。
- 当请求流程被触发时，控制台输出消失。
- 时间差检查依赖 console 渲染的副作用。

## 处理方式
- 恢复或代理 `console.log`、`console.table` 和 `console.clear`。
- 保留日志输出，便于捕获调用栈和 hook 结果。
- 优先使用方法级 patch，不要上来就做全局大范围 hook。

## 需要记录的证据
- 受影响的 console 方法
- 覆写来源提示
- console 恢复后是否改变了页面行为

## 风险说明
- 与执行流 hook 相比，console patch 风险较低，但在强化过的 bundle 上仍可能触发完整性检查。

## 可直接注入的 Hook 片段

### 1. 保护 `console.log` / `trace` / `groupCollapsed` / `groupEnd`

```js
(() => {
  'use strict';

  const readonlyProps = ['log', 'trace', 'groupCollapsed', 'groupEnd'];
  const readonlyConsole = new Proxy(console, {
    set(t, k, v, r) {
      if (readonlyProps.includes(k)) {
        console.groupCollapsed(`%cBlocked overwrite: console.${String(k)}`, 'color: #ff6348;', v);
        console.trace();
        console.groupEnd();
        return true;
      }
      return Reflect.set(t, k, v, r);
    }
  });

  Object.defineProperty(window, 'console', {
    configurable: true,
    enumerable: false,
    get() {
      return readonlyConsole;
    },
    set(v) {
      console.groupCollapsed('%cBlocked overwrite: window.console', 'color: #ff6348;', v);
      console.trace();
      console.groupEnd();
    }
  });
})();
```

### 2. 阻止 `console.clear()`

```js
(() => {
  'use strict';
  console.clear = function () {};
})();
```

### 3. 阻止 `console.table()` 被用于时间差或 getter 诱导检测

```js
(() => {
  'use strict';
  console.table = function () {};
})();
```

## 使用后检查
- `console.log` 等方法是否仍可用于观察运行时数据
- 控制台输出是否不再被清屏或干扰
- 页面是否因为 console 完整性检查产生新异常
