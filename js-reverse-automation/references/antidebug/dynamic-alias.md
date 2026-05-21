# 动态别名规则

当入口函数被别名、包装函数、加密 facade 或异步间接层遮蔽时，使用此规则。

## 现象
- 请求参数已经变化，但看不到稳定的全局路径。
- 多层包装函数逐层委托到真正的加密或签名函数。
- 缺少 source map，且对象路径在每次刷新后都变化。

## 处理方式
- 当稳定性较低时，优先使用 resolver 策略，而不是硬编码对象路径。
- 记录包装链，以及解析出可调用函数所需的最小运行时前置条件。
- 记录生成的 JSRPC 是否使用 resolver，而不是静态路径。

## 需要记录的证据
- 包装链
- resolver 触发条件
- 解析前所需的运行时依赖

## 风险说明
- 基于 resolver 的生成方式比静态路径更不稳定。只有当校验报告明确记录了残余风险时，才应接受这种方式。

## 可直接注入的 Hook 片段

### 1. Hook CryptoJS

适用场景：
- 目标站点使用 CryptoJS
- 需要快速定位 AES / DES / MD5 / SHA / HMAC 的参数来源

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

### 2. Hook JSEncrypt RSA

适用场景：
- 目标站点使用 JSEncrypt
- 想直接拿到 RSA 公钥、私钥、明文和密文

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

## 使用后检查
- 是否成功打印出加密包装链中的关键参数
- 是否能定位到真实的 CryptoJS 或 JSEncrypt 调用点
- 页面功能是否未因重写底层 `call/apply` 而异常
