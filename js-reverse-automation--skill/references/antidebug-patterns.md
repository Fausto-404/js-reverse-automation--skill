# Anti-Debug Patterns

This document consolidates all anti-debug, anti-detection, and environment verification patterns from the six individual antidebug rule files. Each section preserves detection signatures, patch code, evidence requirements, and risk warnings.

**General Principle:** Verify before patch. Use the minimal patch. Record the impact. Reference `capability-boundaries.md` for what chrome-devtools-mcp can and cannot do.

**Verification Order (from anti-detection-verification.md):**
1. Record the original phenomenon without patch.
2. Determine the problem type: `debugger` / dynamic code construction, console cleanup or log suppression, timing or Promise timing, viewport / webdriver / UA / DevTools detection, navigation / close / history interference.
3. Select only one minimal rule to verify.
4. Compare before/after differences: whether requests resume, whether hooks start producing logs, whether call stacks become visible, whether the page introduces new exceptions.

**Acceptance Criteria:**
- After patch, new evidence usable for Phase 2-3 is produced.
- The impact surface and residual risks of the patch can be explained.
- The patch does not change the shape of the final JSRPC / Flask / Burp code to be generated.

**Prohibited Behaviors:**
- Enabling multiple anti-debug rules simultaneously without verification.
- Broadly faking the environment to improve "looks like it works" probability.
- Writing debug-only patches as dependencies of the final generated artifacts.

---

## 1. Debugger Loop

**Source:** `debugger-loop.md`

### Detection Signatures
- DevTools keeps pausing before the target request is sent.
- `eval`, `Function`, or `constructor` receives source code strings containing `debugger`.
- The same call stack repeats and never reaches the parameter change point.

### What to Record
- Which API triggers the problem (`eval`, `Function`, or `constructor`)
- Source hint or call stack frame
- Whether `toString` disguise is needed

### Patch: Bypass Dynamic `debugger`

Applicable to: `eval`, `new Function`, `Function.prototype.constructor`, dynamically assembled code that continuously hits `debugger`.

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

### Post-Patch Verification
- The page no longer repeatedly breaks on `debugger`.
- `Function.prototype.toString` related checks do not trigger new exceptions.
- The main business flow can still execute normally.

### Risk
- This rule changes global execution behavior and may trigger integrity checks. Minimize the scope of effect and record the impact surface.

---

## 2. Console Detection

**Source:** `console-detect.md`

### Detection Signatures
- `console.log`, `console.table`, or `console.clear` has been overwritten.
- Console output disappears when the request flow is triggered.
- Timing checks depend on console rendering side effects.

### What to Record
- Which console methods are affected
- Source hint of the overwrite
- Whether restoring console changes page behavior

### Patch 1: Protect `console.log` / `trace` / `groupCollapsed` / `groupEnd` (Proxy method)

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

### Patch 2: Block `console.clear()`

```js
(() => {
  'use strict';
  console.clear = function () {};
})();
```

### Patch 3: Block `console.table()` (used for timing or getter-induction detection)

```js
(() => {
  'use strict';
  console.table = function () {};
})();
```

### Post-Patch Verification
- `console.log` and similar methods can still be used to observe runtime data.
- Console output is no longer cleared or interfered with.
- The page does not produce new exceptions due to console integrity checks.

### Risk
- Compared to execution flow hooks, console patches have lower risk, but on hardened bundles they may still trigger integrity checks.

---

## 3. Timer Check

**Source:** `timer-check.md`

### Detection Signatures
- Flow only interrupts during single-step debugging.
- Promise callbacks or timer handlers take different branches under debugging state.
- `performance.now`, `Date.now`, or interval delta controls whether the request is sent.

### What to Record
- Which timing primitive is used
- The observed threshold
- Which branch or callback was unlocked by the bypass

### Patch: Hook Promise Resolve

Applicable when: you want to quickly locate async callback entry points, or need to know which Promise resolve produced the key parameter.

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

### Post-Patch Verification
- Promise chains still execute normally.
- Successfully see resolve parameters and call stacks.
- No obvious performance degradation on the page.

### Risk
- Time normalization may mask real race conditions. It should only be used during tracing, not silently enabled by default.

---

## 4. Environment Detection

**Source:** `env-detect.md`

### Detection Signatures
- Branch logic depends on viewport size, DevTools open state, webdriver flag, UA, or extension state.
- The same page behaves inconsistently under different browser configurations.
- After opening DevTools, the request chain disappears.

### What to Record
- The property being checked
- Original value
- Replacement value
- Affected source code hint

### Patch: Fix Window Dimensions

Applicable when: the site uses `innerHeight` / `innerWidth` or `outerHeight` / `outerWidth` to detect whether DevTools is open.

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

### Post-Patch Verification
- After opening DevTools, size detection is no longer triggered.
- Page layout does not have unacceptable distortion.

### Risk
- Environment spoofing may distort judgment of production behavior. Should only be used for investigation and explicitly recorded.

---

## 5. Proxy Guard

**Source:** `proxy-guard.md`

### Detection Signatures
- `window.close`, `history.back`, redirect hook, or unload handler interrupts the tracing flow.
- Requests fail only after configuring a proxy.
- After page navigation, extension or injected scripts are blocked.

### What to Record
- Guard type (`close`, `history`, `redirect`, `proxy`, `extension`)
- Source hint
- Whether request replay succeeds after handling

### Patch 1: Block `window.close`

```js
(() => {
  'use strict';
  window.close = function () {};
})();
```

### Patch 2: Block `history.go` / `history.back`

```js
(() => {
  'use strict';
  window.history.go = function () {};
  window.history.back = function () {};
})();
```

### Patch 3: Break Before Navigation (for locating the source)

Applicable when: the page is about to navigate and you need to locate the source code at the moment of navigation.

```js
(() => {
  'use strict';

  window.onbeforeunload = () => {
    debugger;
    return false;
  };
})();
```

### Post-Patch Verification
- The page is no longer forcibly closed or navigated back.
- Before navigation, the breakpoint can be stably hit.
- These patches are removed promptly after debugging.

### Risk
- Navigation guard patches may change page state. When conditions allow, re-verify the request chain after removing the patch.

---

## 6. Dynamic Alias (Crypto Library Hooks)

**Source:** `dynamic-alias.md`

### Detection Signatures
- Request parameters have changed, but no stable global path is visible.
- Multiple layers of wrapper functions delegate layer by layer to the real crypto or signing function.
- Missing source map, and object paths change after every refresh.

### Strategy
- When stability is low, prefer the resolver strategy over hardcoding object paths.
- Record the wrapper chain and the minimal runtime preconditions needed to resolve to a callable function.
- Record whether the generated JSRPC uses a resolver rather than a static path.

### What to Record
- Wrapper chain
- Resolver trigger conditions
- Runtime dependencies needed before resolution

### Patch 1: Hook CryptoJS

Applicable when: the target site uses CryptoJS and you need to quickly locate the parameter source for AES / DES / MD5 / SHA / HMAC.

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
    // === Symmetric Encryption Detection ===
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
    // === Symmetric Decryption Detection ===
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
            console.log('Fuzz crypto algorithms script: https://github.com/0xsdeo/Fuzz_Crypto_Algorithms');
            time += 1;
          }
          console.log('%c---------------------------------------------------------------------', 'color: green;');
        }
      }
    }
    // === Hash/HMAC Detection ===
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

### Patch 2: Hook JSEncrypt RSA

Applicable when: the target site uses JSEncrypt and you want to directly obtain the RSA public key, private key, plaintext, and ciphertext.

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

### Post-Patch Verification
- Successfully prints key parameters from the crypto wrapper chain.
- Can locate the real CryptoJS or JSEncrypt call site.
- Page functionality is not broken by rewriting the underlying `call`/`apply`.

### Risk
- Rewriting `call`/`apply` affects the global scope and may trigger integrity checks on hardened bundles.

---

## 7. Quick Reference: When to Use Each Pattern

| Pattern | Symptom | File |
|---|---|---|
| Debugger Loop | Repeated `debugger`, `eval`/`Function`/`constructor` tampering | `debugger-loop.md` |
| Console Detection | Console method overwrite, `console.clear`, `console.table`, log suppression | `console-detect.md` |
| Timer Check | Timing delta checks, Promise timing, performance probes | `timer-check.md` |
| Environment Detection | Viewport size, devtools, webdriver, UA checks | `env-detect.md` |
| Proxy Guard | Navigation, close, history, redirect hook blocking request replay | `proxy-guard.md` |
| Dynamic Alias | Obfuscated aliases, dynamic resolvers, crypto wrappers, async indirection | `dynamic-alias.md` |

Only reference a rule when it genuinely changes the investigation path or risk surface.
