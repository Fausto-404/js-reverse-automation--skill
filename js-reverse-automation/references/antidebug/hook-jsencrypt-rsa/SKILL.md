---
name: js-reverse-automation-hook-jsencrypt-rsa
description: Hook JSEncrypt 加密库中的 RSA 算法，输出公私钥与明文/密文。仅在确认使用 JSEncrypt 时启用。
---

# Hook JSEncrypt RSA

用于捕获 JSEncrypt 的 RSA 加解密过程，输出公钥、私钥、原始数据与密文。

## 先读这些信息
- 仅在确认目标使用 JSEncrypt 时启用。
- 该 hook 会覆盖 `Function.prototype.call`，存在被检测或兼容性风险。
- 输出仅用于定位与验证，不改变原始业务逻辑。

## 需要收集的输入
- 目标是否使用 JSEncrypt（库版本可选）

<label>JSEncrypt 版本（可选）：</label>
<input type="text" placeholder="如 3.x" />

## 工作流程
1) 通过 `Function.prototype.call` 拦截 JSEncrypt 实例调用。
2) 在 `encrypt/decrypt` 上注入打印逻辑。
3) 输出公私钥、明文与密文。

## 产出
- 可直接注入的 hook 片段（与 AntiDebug_Breaker 行为一致）：

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
        if (arguments[0].__proto__.__proto__.encrypt.toString().indexOf('RSA加密') === -1) {
          const tempEncrypt = arguments[0].__proto__.__proto__.encrypt;
          arguments[0].__proto__.__proto__.encrypt = function () {
            const encryptText = tempEncrypt.bind(this, ...arguments)();
            console.log('RSA 公钥：\n', this.getPublicKey());
            console.log('RSA加密 原始数据：', ...arguments);
            console.log('RSA加密 Base64 密文：', f(encryptText));
            console.log('%c---------------------------------------------------------------------', 'color: green;');
            return encryptText;
          };
        }

        if (arguments[0].__proto__.__proto__.decrypt.toString().indexOf('RSA解密') === -1) {
          const tempDecrypt = arguments[0].__proto__.__proto__.decrypt;
          arguments[0].__proto__.__proto__.decrypt = function () {
            const decryptText = tempDecrypt.bind(this, ...arguments)();
            console.log('RSA 私钥：\n', this.getPrivateKey());
            console.log('RSA解密 Base64 原始数据：', f(...arguments));
            console.log('RSA解密 明文：', decryptText);
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

- 最终输出必须注明：`已启用技能: Hook JSEncrypt RSA`

## 交付前检查
- RSA 加解密日志是否出现
- 公私钥与明密文是否输出完整
- 目标页面功能是否未受影响
