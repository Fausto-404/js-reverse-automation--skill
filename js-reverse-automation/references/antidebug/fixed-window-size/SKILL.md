---
name: js-reverse-automation-fixed-window-size
description: 固定浏览器高度宽度值以绕过前端检测用户是否打开控制台。仅在确认尺寸检测时启用。
---

# Fixed window size

用于固定 `window.innerHeight/innerWidth/outerHeight/outerWidth`，绕过基于窗口尺寸变化的 DevTools 检测。

## 先读这些信息
- 仅在确认站点通过窗口尺寸判断 DevTools 是否打开时启用。
- 该策略会影响响应式布局，可能造成 UI 误差。

## 需要收集的输入
- 期望固定的内外尺寸（建议与真实屏幕尺寸相近）

<label>innerHeight：</label>
<input type="text" placeholder="660" />

<label>innerWidth：</label>
<input type="text" placeholder="1366" />

<label>outerHeight：</label>
<input type="text" placeholder="760" />

<label>outerWidth：</label>
<input type="text" placeholder="1400" />

## 工作流程
1) 读取原始属性描述符，保留原 setter。
2) 用 `Object.defineProperty` 固定 getter 返回值。
3) setter 统一回写固定值，避免被页面脚本改写。

## 产出
- 可直接注入的固定尺寸片段：

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

- 最终输出必须注明：`已启用技能: Fixed window size`

## 交付前检查
- DevTools 打开后不再触发尺寸检测
- 页面关键布局未出现严重异常
