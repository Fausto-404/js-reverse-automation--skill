#!/usr/bin/env python3
"""Generate a Webpack/module runtime discovery probe JS file.

The probe attempts to discover module systems (Webpack 4/5, Vite, Rollup)
and extract candidate exports. Results written to window.__JSRA_MODULES__.

Uses the webpackChunk*.push() trick to capture __webpack_require__ without
batch-executing uninitialized module factories.

Usage:
  python3 scripts/emit_module_probe.py --output generated/module_probe.js
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROBE = r'''(() => {
  "use strict";
  const dump = {
    version: "2.1.0",
    timestamp: Date.now(),
    bundlers: [],
    modules: [],
    globals: [],
    errors: []
  };
  const seen = new Set();

  function previewSource(fn) {
    try { return Function.prototype.toString.call(fn).slice(0, 1200); } catch (_) { return ""; }
  }

  function addExport(moduleId, path, value, source) {
    if (typeof value !== "function") return;
    const id = `${source}:${moduleId}:${path}`;
    if (seen.has(id)) return;
    seen.add(id);
    dump.modules.push({
      id, source, module_id: String(moduleId),
      export_path: path, name: value.name || path,
      type: "function", source_snippet: previewSource(value)
    });
  }

  function walkExports(moduleId, value, prefix, source, depth = 0) {
    if (depth > 2 || value == null) return;
    if (typeof value === "function") addExport(moduleId, prefix || "default", value, source);
    if ((typeof value === "object" || typeof value === "function") && value) {
      let keys = [];
      try { keys = Object.keys(value).slice(0, 100); } catch (_) { return; }
      keys.forEach(key => {
        let child; try { child = value[key]; } catch (_) { return; }
        const next = prefix ? `${prefix}.${key}` : key;
        if (typeof child === "function") addExport(moduleId, next, child, source);
        else if (depth < 2 && child && typeof child === "object")
          walkExports(moduleId, child, next, source, depth + 1);
      });
    }
  }

  function inspectRequire(req, source) {
    if (!req) return;
    try {
      window.__JSRA_WEBPACK_REQUIRE_MAP__ = window.__JSRA_WEBPACK_REQUIRE_MAP__ || {};
      window.__JSRA_WEBPACK_REQUIRE_MAP__[source] = req;
      if (!window.__JSRA_WEBPACK_REQUIRE__) window.__JSRA_WEBPACK_REQUIRE__ = req;
    } catch (_) {}
    const cache = req.c || {};
    Object.keys(cache).forEach(id => {
      try { walkExports(id, cache[id] && cache[id].exports, "", source); }
      catch (error) { dump.errors.push(String(error)); }
    });
    dump.bundlers.push({
      type: "webpack", source,
      cached_modules: Object.keys(cache).length,
      factories: req.m ? Object.keys(req.m).length : null
    });
  }

  // === Webpack 5: hook webpackChunk*.push() ===
  Object.keys(window).filter(k => /^webpackChunk/.test(k)).forEach(key => {
    const chunk = window[key];
    if (!Array.isArray(chunk) || typeof chunk.push !== "function") return;
    let captured = null;
    const token = `jsra_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    try {
      // Push a dummy chunk to capture __webpack_require__
      chunk.push([[token], {}, function(__webpack_require__) {
        captured = __webpack_require__;
      }]);
      if (captured) inspectRequire(captured, key);
    } catch (error) {
      dump.errors.push(`${key}: ${error}`);
    }
  });

  // === Webpack 3/4: webpackJsonp ===
  if (typeof window.webpackJsonp === "function") {
    dump.bundlers.push({
      type: "webpack-legacy", source: "webpackJsonp",
      note: "Detected; use runtime-specific adapter if require is not exposed."
    });
  }

  // === Global exports scan ===
  Object.getOwnPropertyNames(window).slice(0, 5000).forEach(key => {
    let value; try { value = window[key]; } catch (_) { return; }
    if (typeof value === "function") {
      const source = previewSource(value);
      if (/encrypt|decrypt|sign|hmac|digest|hash|rsa|aes|sm2|sm4|crypto/i.test(key + " " + source)) {
        dump.globals.push({
          id: `global:${key}`, path: `window[${JSON.stringify(key)}]`,
          name: key, type: "function", source_snippet: source
        });
      }
    }
  });

  window.__JSRA_MODULE_DUMP__ = dump;
  console.info("[JSRA] module probe complete", dump);
  return dump;
})();
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit safe Webpack/global module probe.")
    parser.add_argument("--output", required=True, help="Output JS file path.")
    args = parser.parse_args()

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PROBE, encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
