---
name: js-reverse-automation-hook-cryptojs
description: Hook CryptoJS 当中的所有 对称&哈希&HMAC 算法（AES/DES/MD5/SHA 等），输出关键参数与密文。仅在确认使用 CryptoJS 时启用。
---

# Hook CryptoJS

用于捕获 CryptoJS 对称加解密与哈希/HMAC 的输入、密钥、IV、模式等信息。

## 先读这些信息
- 仅在确认目标使用 CryptoJS 时启用。
- 该 hook 会覆盖 `Function.prototype.apply`，存在被检测或兼容性风险。
- 输出信息仅用于定位与验证，不改变原始业务逻辑。

## 需要收集的输入
- 目标是否使用 CryptoJS（库版本可选）
- 是否只关心对称加解密或哈希/HMAC

<label>CryptoJS 版本（可选）：</label>
<input type="text" placeholder="如 4.2.0" />

<label>目标类型：</label>
<input type="text" placeholder="symmetric / hash / both" />

## 工作流程
1) 通过 `Function.prototype.apply` 拦截 CryptoJS 内部调用。
2) 识别对称加解密对象结构并输出密钥、IV、模式、填充等。
3) 识别 Hash/HMAC finalize 并输出明文与密文。

## 产出
- 可直接注入的 hook 片段（与 AntiDebug_Breaker 行为一致）：

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
      default: return '未获取到';
    }
  }

  const tempApply = Function.prototype.apply;
  Function.prototype.apply = function () {
    // Symmetric encrypt
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
            console.log('对称加密后的密文：', encryptText);
          } else {
            console.log('对称加密后的密文：由于toString方法并未获取到，请自行使用上方打印的对象进行toString调用输出密文。');
          }

          const key = arguments[1][0].key.toString();
          if (key !== '[object Object]') {
            console.log('对称加密Hex key：', key);
          } else {
            console.log('对称加密Hex key：由于toString方法并未获取到，请自行使用上方打印的对象进行toString调用输出key。');
          }

          const iv = arguments[1][0].iv;
          if (iv) {
            if (iv.toString() !== '[object Object]') {
              console.log('对称加密Hex iv：', iv.toString());
            } else {
              console.log('对称加密Hex iv：由于toString方法并未获取到，请自行使用上方打印的对象进行toString调用输出iv。');
            }
          } else {
            console.log('对称加密时未用到iv');
          }

          if (arguments[1][0].padding) {
            console.log('对称加密时的填充模式：', arguments[1][0].padding);
          }
          if (arguments[1][0].mode && Object.hasOwn(arguments[1][0].mode, 'Encryptor')) {
            console.log('对称加密时的运算模式：', arguments[1][0].mode.Encryptor.processBlock);
          }
          if (arguments[1][0].key && Object.hasOwn(arguments[1][0].key, 'sigBytes')) {
            console.log('对称加密时的密钥长度：', getSigBytes(arguments[1][0].key.sigBytes));
          }
          console.log('%c---------------------------------------------------------------------', 'color: green;');
        } else {
          console.groupCollapsed('如果上方正常输出了对称加密的key、iv等加密参数可忽略本条信息。');
          console.log(...arguments);
          console.log('对称加密：由于一些必要因素导致未能输出key、iv等加密参数，请自行使用上方打印的对象进行toString调用输出key、iv等加密参数。');
          console.log('%c---------------------------------------------------------------------', 'color: green;');
          console.groupEnd();
        }
      }
    // Symmetric decrypt
    } else if (
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
            console.log('对称解密Hex key：', key);
          } else {
            console.log('对称解密Hex key：由于toString方法并未获取到，请自行使用上方打印的对象进行toString调用输出key。');
          }

          if (Object.hasOwn(arguments[1][2], 'iv') && arguments[1][2].iv) {
            const iv2 = arguments[1][2].iv.toString();
            if (iv2 !== '[object Object]') {
              console.log('对称解密Hex iv：', iv2);
            } else {
              console.log('对称解密Hex iv：由于toString方法并未获取到，请自行使用上方打印的对象进行toString调用输出iv。');
            }
          } else {
            console.log('对称解密时未用到iv');
          }

          if (Object.hasOwn(arguments[1][2], 'padding') && arguments[1][2].padding) {
            console.log('对称解密时的填充模式：', arguments[1][2].padding);
          }
          if (Object.hasOwn(arguments[1][2], 'mode') && arguments[1][2].mode) {
            console.log('对称解密时的运算模式：', arguments[1][2].mode.Encryptor.processBlock);
          }
          if (time === 0) {
            console.log('可使用我的脚本进行fuzz加解密参数（算法、模式、填充方式等）：https://github.com/0xsdeo/Fuzz_Crypto_Algorithms');
            time += 1;
          }
          console.log('%c---------------------------------------------------------------------', 'color: green;');
        }
      }
    // Hash / HMAC
    } else if (
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
        if (arguments[0].__proto__.__proto__.finalize.toString().indexOf('哈希/HMAC') === -1) {
          const tempFinalize = arguments[0].__proto__.__proto__.finalize;
          arguments[0].__proto__.__proto__.finalize = function () {
            if (!Object.hasOwn(this, 'init')) {
              const hash = tempFinalize.call(this, ...arguments);
              console.log('哈希/HMAC 加密 原始数据：', ...arguments);
              console.log('哈希/HMAC 加密 密文：', hash.toString());
              console.log('哈希/HMAC 加密 密文长度：', hash.toString().length);
              console.log('注：如果是HMAC加密，本脚本是hook不到密钥的，需自行查找。');
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

- 最终输出必须注明：`已启用技能: Hook CryptoJS`

## 交付前检查
- CryptoJS 相关日志是否出现
- 对称加解密参数输出是否完整
- 哈希/HMAC 是否正常输出
- 目标页面功能是否未受影响
