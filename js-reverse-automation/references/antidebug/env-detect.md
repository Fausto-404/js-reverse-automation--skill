# 环境检测规则

当目标站点在启用签名或加密路径之前，会先检查浏览器环境属性时，使用此规则。

## 现象
- 分支逻辑依赖 viewport 大小、DevTools 是否打开、webdriver 标记、UA 或扩展状态。
- 同一页面在不同浏览器配置下表现不一致。
- 打开 DevTools 后，请求链路消失。

## 处理方式
- 记录精确的环境判断条件。
- 只 patch 为复现所必需的属性，例如 viewport 尺寸或 webdriver 标记。
- 在诊断信息和残余风险说明中记录这些 patch。

## 需要记录的证据
- 被检查的属性
- 原始值
- 替换值
- 受影响的源码提示

## 风险说明
- 环境伪装可能导致对生产行为的判断失真。应仅用于调查，并明确记录。

## 可直接注入的 Hook 片段

### 1. 固定窗口尺寸

适用场景：
- 站点通过 `innerHeight` / `innerWidth`
- 或 `outerHeight` / `outerWidth`
- 来判断是否打开 DevTools

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

## 使用后检查
- 打开 DevTools 后是否不再触发尺寸检测
- 页面布局是否出现不可接受的错位
