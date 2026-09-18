# 反调试与环境对抗模式

本文汇总六类反调试规则中的反调试、反检测和环境校验模式。每个章节保留检测特征、补丁代码、证据要求和风险提示。

**基本原则：**先验证，再修改；使用最小补丁；记录影响范围。关于 chrome-devtools-mcp 的能力边界，参阅 `capability-boundaries.md`。

**验证顺序：**
1. 不加补丁，先记录原始现象。
2. 判断问题类型：`debugger`/动态代码构造、控制台清理或日志抑制、计时或 Promise 计时、视口/ webdriver / UA / DevTools 检测、导航/关闭/历史记录干扰。
3. 每次只选择一条最小规则进行验证。
4. 比较前后差异：请求是否恢复、Hook 是否开始产生日志、调用栈是否可见、页面是否产生新的异常。

**验收标准：**
- 补丁后产生可用于后续分析的新证据。
- 能解释补丁的影响范围和残余风险。
- 补丁不改变最终生成的 JSRPC / Flask / Burp 代码结构。

**禁止行为：**
- 未验证就同时启用多条反调试规则。
- 大范围伪造环境，只为了提高“看起来能运行”的概率。
- 将仅用于调试的补丁写入最终生成产物的依赖。

---

## 1. Debugger 循环

**来源：** `debugger-loop.md`

### 检测特征
- 目标请求发送前 DevTools 持续暂停。
- `eval`、`Function` 或 `constructor` 收到包含 `debugger` 的源码字符串。
- 同一调用栈反复出现，始终到不了参数变化位置。

### 需要记录
- 触发问题的 API（`eval`、`Function` 或 `constructor`）。
- 源码提示或调用栈帧。
- 是否需要伪装 `toString`。

### 补丁：绕过动态 `debugger`

适用于 `eval`、`new Function`、`Function.prototype.constructor` 以及持续触发 `debugger` 的动态组装代码。

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

### 补丁后验证
- 页面不再因 `debugger` 反复中断。
- `Function.prototype.toString` 相关检查不产生新的异常。
- 主要业务流程仍可正常执行。

### 风险
- 该规则会改变全局执行行为，可能触发完整性检查。应尽量缩小影响范围并记录影响面。

---

## 2. 控制台检测

**来源：** `console-detect.md`

### 检测特征
- `console.log`、`console.table` 或 `console.clear` 被覆盖。
- 触发请求流程后控制台输出消失。
- 计时检测依赖控制台渲染副作用。

### 需要记录
- 受影响的控制台方法。
- 覆盖操作的源码提示。
- 恢复控制台后页面行为是否改变。

### 补丁一：保护 `console.log` / `trace` / `groupCollapsed` / `groupEnd`（Proxy 方法）

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

### 补丁二：阻止 `console.clear()`

```js
(() => {
  'use strict';
  console.clear = function () {};
})();
```

### 补丁三：阻止 `console.table()`（用于计时或 Getter 诱导检测）

```js
(() => {
  'use strict';
  console.table = function () {};
})();
```

### 补丁后验证
- 仍可使用 `console.log` 等方法观察运行时数据。
- 控制台输出不再被清空或干扰。
- 页面不会因控制台完整性检查产生新的异常。

### 风险
- 与执行流 Hook 相比，控制台补丁风险较低，但在加固构建中仍可能触发完整性检查。

---

## 3. 计时检测

**来源：** `timer-check.md`

### 检测特征
- 只有单步调试时流程才中断。
- 调试状态下 Promise 回调或计时器处理器进入不同分支。
- `performance.now`、`Date.now` 或时间间隔差值决定是否发送请求。

### 需要记录
- 使用的计时原语。
- 观测到的阈值。
- 绕过后解锁的分支或回调。

### 补丁：Hook Promise Resolve

适用于快速定位异步回调入口，或确认哪个 Promise resolve 产生了关键参数。

```js
(() => {
  'use strict';

  const OriginalPromise = Promise;

  Promise = function (callback) {
    if (!callback) {
      return new OriginalPromise(callback);
    }
    const originCallback = callback;
    callback = function (resolve, reject) {
      const originResolve = resolve;
      resolve = function (result) {
        if (result && !(result instanceof Promise)) {
          try {
            console.groupCollapsed('[Promise resolve]');
            console.log(result);
            console.trace();
            console.groupEnd();
          } catch (e) {}
        }
        return originResolve.apply(this, arguments);
      };
      return originCallback(resolve, reject);
    };
    return new OriginalPromise(callback);
  };

  Promise.prototype = OriginalPromise.prototype;
  Object.defineProperties(Promise, Object.getOwnPropertyDescriptors(OriginalPromise));
})();
```

### 补丁后验证
- Promise 链仍可正常执行。
- 可以看到 resolve 参数和调用栈。
- 页面没有明显性能下降。

### 风险
- 时间归一化可能掩盖真实竞态，只应在跟踪期间使用，不得默认静默启用。

---

## 4. 环境检测

**来源：** `env-detect.md`

### 检测特征
- 分支逻辑依赖视口尺寸、DevTools 打开状态、webdriver 标志、UA 或扩展状态。
- 同一页面在不同浏览器配置下表现不一致。
- 打开 DevTools 后请求链消失。

### 需要记录
- 被检查的属性。
- 原始值。
- 替换值。
- 受影响的源码提示。

### 补丁：修正窗口尺寸

适用于网站使用 `innerHeight` / `innerWidth` 或 `outerHeight` / `outerWidth` 判断 DevTools 是否打开的场景。

```js
(() => {
  'use strict';

  const innerHeightValue = 660;
  const innerWidthValue = 1366;
  const outerHeightValue = 760;
  const outerWidthValue = 1400;

  const innerHeightDesc = Object.getOwnPropertyDescriptor(window, 'innerHeight');
  const innerWidthDesc = Object.getOwnPropertyDescriptor(window, 'innerWidth');
  const outerHeightDesc = Object.getOwnPropertyDescriptor(window, 'outerHeight');
  const outerWidthDesc = Object.getOwnPropertyDescriptor(window, 'outerWidth');

  Object.defineProperty(window, 'innerHeight', {
    get() { return innerHeightValue; },
    set() { return innerHeightDesc.set.call(window, innerHeightValue); }
  });

  Object.defineProperty(window, 'innerWidth', {
    get() { return innerWidthValue; },
    set() { return innerWidthDesc.set.call(window, innerWidthValue); }
  });

  Object.defineProperty(window, 'outerHeight', {
    get() { return outerHeightValue; },
    set() { return outerHeightDesc.set.call(window, outerHeightValue); }
  });

  Object.defineProperty(window, 'outerWidth', {
    get() { return outerWidthValue; },
    set() { return outerWidthDesc.set.call(window, outerWidthValue); }
  });
})();
```

### 补丁后验证
- 打开 DevTools 后不再触发尺寸检测。
- 页面布局没有不可接受的变形。

### 风险
- 环境伪造可能影响对正式环境行为的判断，只能用于调查，并且必须明确记录。

---

## 5. 代理与导航保护

**来源：** `proxy-guard.md`

### 检测特征
- `window.close`、`history.back`、重定向 Hook 或卸载处理器中断跟踪流程。
- 只有配置代理后请求才失败。
- 页面导航后扩展或注入脚本被阻止。

### 需要记录
- 保护类型（`close`、`history`、`redirect`、`proxy`、`extension`）。
- 源码提示。
- 处理后请求重放是否成功。

### 补丁一：阻止 `window.close`

```js
(() => {
  'use strict';
  window.close = function () {};
})();
```

### 补丁二：阻止 `history.go` / `history.back`

```js
(() => {
  'use strict';
  window.history.go = function () {};
  window.history.back = function () {};
})();
```

### 补丁三：导航前断点（用于定位源码）

适用于页面即将导航，需要定位导航发生瞬间源码的场景。

```js
(() => {
  'use strict';

  window.onbeforeunload = () => {
    debugger;
    return false;
  };
})();
```

### 补丁后验证
- 页面不再被强制关闭或返回上一页。
- 导航前可以稳定命中断点。
- 调试结束后及时移除这些补丁。

### 风险
- 导航保护补丁可能改变页面状态。条件允许时，应移除补丁后重新验证请求链。

---

## 6. 动态别名（密码库 Hook）

**来源：** `dynamic-alias.md`

### 检测特征
- 请求参数发生变化，但看不到稳定的全局路径。
- 多层包装函数逐层转发到真正的加密或签名函数。
- 缺少 source map，且对象路径每次刷新都会变化。

### 策略
- 稳定性较低时，优先使用解析器策略，不要硬编码对象路径。
- 记录包装链，以及解析到可调用函数所需的最小运行时前置条件。
- 记录生成的 JSRPC 使用的是解析器还是静态路径。

### 需要记录
- 包装链。
- 解析器触发条件。
- 解析前需要满足的运行时依赖。

### 补丁一：Hook CryptoJS

适用于目标网站使用 CryptoJS，需要快速定位 AES / DES / MD5 / SHA / HMAC 参数来源的场景。

```js
(() => {
  'use strict';

  let time = 0;

  function hasEncryptProp(obj) {
    const requiredProps = [
      'ciphertext',
      'key',
      'iv',
      'algorithm',
      'mode',
      'padding',
      'blockSize',
      'formatter'
    ];
    if (!obj || typeof obj !== 'object') return false;
    for (const prop of requiredProps) {
      if (!(prop in obj)) return false;
    }
    return true;
  }

  function hasDecryptProp(obj) {
    const requiredProps = ['sigBytes', 'words'];
    if (!obj || typeof obj !== 'object') return false;
    for (const prop of requiredProps) {
      if (!(prop in obj)) return false;
    }
    return true;
  }

  function getSigBytes(size) {
    switch (size) {
      case 8: return '64bits';
      case 16: return '128bits';
      case 24: return '192bits';
      case 32: return '256bits';
      default: return 'unknown';
    }
  }

  const tempApply = Function.prototype.apply;
  Function.prototype.apply = function () {
    // === 对称加密检测 ===
    if (
      arguments.length === 2 &&
      arguments[0] &&
      arguments[1] &&
      typeof arguments[1] === 'object' &&
      arguments[1].length === 1 &&
      hasEncryptProp(arguments[1][0])
    ) {
      if (Object.hasOwn(arguments[0], '$super') && Object.hasOwn(arguments[1], 'callee')) {
        if (
          this.toString().indexOf('function()') !== -1 ||
          /^\s*function(?:\s*\*)?\s+[A-Za-z_$][\w$]*\s*\([^)]*\)\s*\{/.test(this.toString()) ||
          /^\s*function\s*\(\s*\)\s*\{/.test(this.toString())
        ) {
          console.log(...arguments);

          const encryptText = arguments[0].$super.toString.call(arguments[1][0]);
          if (encryptText !== '[object Object]') {
            console.log('Symmetric ciphertext:', encryptText);
          } else {
            console.log('Symmetric ciphertext: toString unavailable, use the printed object above to call toString manually.');
          }

          const key = arguments[1][0].key.toString();
          if (key !== '[object Object]') {
            console.log('Symmetric Hex key:', key);
          } else {
            console.log('Symmetric Hex key: toString unavailable, use the printed object above to call toString manually.');
          }

          const iv = arguments[1][0].iv;
          if (iv) {
            if (iv.toString() !== '[object Object]') {
              console.log('Symmetric Hex iv:', iv.toString());
            } else {
              console.log('Symmetric Hex iv: toString unavailable, use the printed object above to call toString manually.');
            }
          } else {
            console.log('Symmetric encryption: no iv used');
          }

          if (arguments[1][0].padding) {
            console.log('Padding mode:', arguments[1][0].padding);
          }
          if (arguments[1][0].mode && Object.hasOwn(arguments[1][0].mode, 'Encryptor')) {
            console.log('Block mode:', arguments[1][0].mode.Encryptor.processBlock);
          }
          if (arguments[1][0].key && Object.hasOwn(arguments[1][0].key, 'sigBytes')) {
            console.log('Key length:', getSigBytes(arguments[1][0].key.sigBytes));
          }
          console.log('%c---------------------------------------------------------------------', 'color: green;');
        } else {
          console.groupCollapsed('If the above correctly output the key/iv etc., ignore this message.');
          console.log(...arguments);
          console.log('Symmetric encryption: due to some necessary factors, key/iv etc. were not output. Use the printed object above to call toString manually.');
          console.log('%c---------------------------------------------------------------------', 'color: green;');
          console.groupEnd();
        }
      }
    }
    // === 对称解密检测 ===
    else if (
      arguments.length === 2 &&
      arguments[0] &&
      arguments[1] &&
      typeof arguments[1] === 'object' &&
      arguments[1].length === 3 &&
      hasDecryptProp(arguments[1][1])
    ) {
      if (Object.hasOwn(arguments[0], '$super') && Object.hasOwn(arguments[1], 'callee')) {
        if (this.toString().indexOf('function()') === -1 && arguments[1][0] === 2) {
          console.log(...arguments);

          const key = arguments[1][1].toString();
          if (key !== '[object Object]') {
            console.log('Symmetric decrypt Hex key:', key);
          } else {
            console.log('Symmetric decrypt Hex key: toString unavailable, use the printed object above to call toString manually.');
          }

          if (Object.hasOwn(arguments[1][2], 'iv') && arguments[1][2].iv) {
            const iv2 = arguments[1][2].iv.toString();
            if (iv2 !== '[object Object]') {
              console.log('Symmetric decrypt Hex iv:', iv2);
            } else {
              console.log('Symmetric decrypt Hex iv: toString unavailable, use the printed object above to call toString manually.');
            }
          } else {
            console.log('Symmetric decryption: no iv used');
          }

          if (Object.hasOwn(arguments[1][2], 'padding') && arguments[1][2].padding) {
            console.log('Decrypt padding mode:', arguments[1][2].padding);
          }
          if (Object.hasOwn(arguments[1][2], 'mode') && arguments[1][2].mode) {
            console.log('Decrypt block mode:', arguments[1][2].mode.Encryptor.processBlock);
          }
          if (time === 0) {
            console.log('如需继续确认算法类型，请结合当前页面的实际调用参数和输出长度进行定向验证。');
            time += 1;
          }
          console.log('%c---------------------------------------------------------------------', 'color: green;');
        }
      }
    }
    // === 哈希/HMAC 检测 ===
    else if (
      arguments.length === 2 &&
      arguments[0] &&
      arguments[1] &&
      typeof arguments[0] === 'object' &&
      typeof arguments[1] === 'object'
    ) {
      if (
        arguments[0].__proto__ &&
        Object.hasOwn(arguments[0].__proto__, '$super') &&
        Object.hasOwn(arguments[0].__proto__, '_doFinalize') &&
        arguments[0].__proto__.__proto__ &&
        Object.hasOwn(arguments[0].__proto__.__proto__, 'finalize')
      ) {
        if (arguments[0].__proto__.__proto__.finalize.toString().indexOf('Hash/HMAC') === -1) {
          const tempFinalize = arguments[0].__proto__.__proto__.finalize;
          arguments[0].__proto__.__proto__.finalize = function () {
            if (!Object.hasOwn(this, 'init')) {
              const hash = tempFinalize.call(this, ...arguments);
              console.log('Hash/HMAC raw data:', ...arguments);
              console.log('Hash/HMAC ciphertext:', hash.toString());
              console.log('Hash/HMAC ciphertext length:', hash.toString().length);
              console.log('Note: If HMAC, this script cannot hook the key. Search for it manually.');
              console.log('%c---------------------------------------------------------------------', 'color: green;');
              return hash;
            }
            return tempFinalize.call(this, ...arguments);
          };
        }
      }
    }
    return tempApply.call(this, ...arguments);
  };
})();
```

### 补丁二：Hook JSEncrypt RSA

适用于目标网站使用 JSEncrypt，需要直接获取 RSA 公钥、私钥、明文和密文的场景。

```js
(() => {
  'use strict';

  let u, c = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  function f(t) {
    let e, i, r = '';
    for (e = 0; e + 3 <= t.length; e += 3) {
      i = parseInt(t.substring(e, e + 3), 16);
      r += c.charAt(i >> 6) + c.charAt(63 & i);
    }
    if (e + 1 == t.length) {
      i = parseInt(t.substring(e, e + 1), 16);
      r += c.charAt(i << 2);
    } else if (e + 2 == t.length) {
      i = parseInt(t.substring(e, e + 2), 16);
      r += c.charAt(i >> 2) + c.charAt((3 & i) << 4);
    }
    while ((3 & r.length) > 0) r += '=';
    return r;
  }

  function hasRSAProp(obj) {
    const requiredProps = [
      'constructor',
      'getPrivateBaseKey',
      'getPrivateBaseKeyB64',
      'getPrivateKey',
      'getPublicBaseKey',
      'getPublicBaseKeyB64',
      'getPublicKey',
      'parseKey',
      'parsePropertiesFrom'
    ];
    if (!obj || typeof obj !== 'object') return false;
    for (const prop of requiredProps) {
      if (!(prop in obj)) return false;
    }
    return true;
  }

  const tempCall = Function.prototype.call;
  Function.prototype.call = function () {
    if (
      arguments.length === 1 &&
      arguments[0] &&
      arguments[0].__proto__ &&
      typeof arguments[0].__proto__ === 'object' &&
      hasRSAProp(arguments[0].__proto__)
    ) {
      if (
        '__proto__' in arguments[0].__proto__ &&
        arguments[0].__proto__.__proto__ &&
        Object.hasOwn(arguments[0].__proto__.__proto__, 'encrypt') &&
        Object.hasOwn(arguments[0].__proto__.__proto__, 'decrypt')
      ) {
        if (arguments[0].__proto__.__proto__.encrypt.toString().indexOf('RSA encrypt') === -1) {
          const tempEncrypt = arguments[0].__proto__.__proto__.encrypt;
          arguments[0].__proto__.__proto__.encrypt = function () {
            const encryptText = tempEncrypt.bind(this, ...arguments)();
            console.log('RSA public key:\n', this.getPublicKey());
            console.log('RSA encrypt plaintext:', ...arguments);
            console.log('RSA encrypt Base64 ciphertext:', f(encryptText));
            console.log('%c---------------------------------------------------------------------', 'color: green;');
            return encryptText;
          };
        }

        if (arguments[0].__proto__.__proto__.decrypt.toString().indexOf('RSA decrypt') === -1) {
          const tempDecrypt = arguments[0].__proto__.__proto__.decrypt;
          arguments[0].__proto__.__proto__.decrypt = function () {
            const decryptText = tempDecrypt.bind(this, ...arguments)();
            console.log('RSA private key:\n', this.getPrivateKey());
            console.log('RSA decrypt Base64 input:', f(...arguments));
            console.log('RSA decrypt plaintext:', decryptText);
            console.log('%c---------------------------------------------------------------------', 'color: green;');
            return decryptText;
          };
        }
      }
    }
    return tempCall.bind(this, ...arguments)();
  };
})();
```

### 补丁后验证
- 成功从密码学包装链输出关键参数。
- 可以定位真实的 CryptoJS 或 JSEncrypt 调用位置。
- 重写底层 `call`/`apply` 后页面功能没有损坏。

### 风险
- 重写 `call`/`apply` 会影响全局作用域，可能触发加固构建的完整性检查。

---

## 7. 模式快速选择

| 模式 | 现象 | 文件 |
|---|---|---|
| Debugger 循环 | 反复出现 `debugger`，或 `eval`/`Function`/`constructor` 被篡改 | `debugger-loop.md` |
| 控制台检测 | 控制台方法被覆盖、调用 `console.clear`/`console.table`、日志被抑制 | `console-detect.md` |
| 计时检测 | 计时差值检查、Promise 计时、性能探针 | `timer-check.md` |
| 环境检测 | 视口尺寸、DevTools、webdriver、UA 检查 | `env-detect.md` |
| 代理与导航保护 | 导航、关闭、历史记录、重定向 Hook 阻止请求重放 | `proxy-guard.md` |
| 动态别名 | 混淆别名、动态解析器、密码学包装、异步间接调用 | `dynamic-alias.md` |

只有在某条规则确实改变调查路径或风险面时，才引用并启用它。
