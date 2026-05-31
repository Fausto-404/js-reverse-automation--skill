#!/usr/bin/env python3
"""Generate a Webpack/module runtime discovery probe JS file.

The probe attempts to discover module systems (Webpack 4/5, Vite, Rollup)
and extract candidate exports. Results written to window.__JSRA_MODULES__.

Usage:
  python3 scripts/emit_module_probe.py --output generated/module_probe.js
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Output JS file path.")
    return parser.parse_args()


def build_probe() -> str:
    return """// emit_module_probe.py
// Module Runtime Discovery Probe v1
(function() {
  'use strict';

  if (window.__JSRA_MODULES__) return;

  var result = window.__JSRA_MODULES__ = {
    version: 'module-probe-v1',
    installedAt: Date.now(),
    detected: false,
    type: 'unknown',
    requireAvailable: false,
    requirePath: null,
    moduleCacheKeys: [],
    candidateExports: [],
    chunkArrays: [],
    globalExports: [],
    errors: [],
    dump: function() {
      return JSON.stringify({
        detected: this.detected,
        type: this.type,
        requireAvailable: this.requireAvailable,
        requirePath: this.requirePath,
        moduleCacheKeys: this.moduleCacheKeys.slice(0, 200),
        candidateExports: this.candidateExports,
        chunkArrays: this.chunkArrays,
        globalExports: this.globalExports.slice(0, 100),
        errors: this.errors
      });
    },
    clear: function() {
      this.detected = false;
      this.type = 'unknown';
      this.requireAvailable = false;
      this.requirePath = null;
      this.moduleCacheKeys = [];
      this.candidateExports = [];
      this.chunkArrays = [];
      this.globalExports = [];
      this.errors = [];
    }
  };

  // === 1. Detect Webpack chunk arrays ===
  function detectChunkArrays() {
    var found = [];

    // Webpack 3/4: webpackJsonp
    if (Array.isArray(window.webpackJsonp)) {
      found.push({ name: 'webpackJsonp', length: window.webpackJsonp.length });
    }

    // Webpack 5: webpackChunk* patterns
    var keys = Object.keys(window);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      if (k.indexOf('webpackChunk') === 0 && Array.isArray(window[k])) {
        found.push({ name: k, length: window[k].length });
      }
    }

    // Loadable components
    if (window.__LOADABLE_LOADED_CHUNKS__ && Array.isArray(window.__LOADABLE_LOADED_CHUNKS__)) {
      found.push({ name: '__LOADABLE_LOADED_CHUNKS__', length: window.__LOADABLE_LOADED_CHUNKS__.length });
    }

    return found;
  }

  // === 2. Try to capture __webpack_require__ ===
  function tryCaptureRequire() {
    var require = null;
    var requirePath = null;

    // Strategy 1: Hook webpackJsonp push to capture require
    if (Array.isArray(window.webpackJsonp) && !window.__JSRA_require_captured) {
      window.__JSRA_require_captured = true;
      var origPush = Array.prototype.push;
      window.webpackJsonp.push = function() {
        var args = arguments;
        // Webpack 4: push([chunkIds, moreModules, executeModules])
        // The modules object keys are module IDs, values are functions(require, module, exports)
        for (var i = 0; i < args.length; i++) {
          var chunk = args[i];
          if (Array.isArray(chunk) && chunk.length >= 2) {
            var modules = chunk[1];
            if (modules && typeof modules === 'object') {
              // Create a fake require to extract __webpack_require__
              var fakeModules = {};
              var fakeModuleCache = {};
              var fakeRequire = function(id) {
                if (fakeModuleCache[id]) return fakeModuleCache[id].exports;
                var m = fakeModuleCache[id] = { id: id, exports: {} };
                if (fakeModules[id]) {
                  fakeModules[id](fakeRequire, m, m.exports);
                }
                return m.exports;
              };
              // Copy module factories
              var moduleIds = Object.keys(modules);
              for (var j = 0; j < moduleIds.length; j++) {
                fakeModules[moduleIds[j]] = modules[moduleIds[j]];
              }
              // Try to find __webpack_require__ in the first module
              if (moduleIds.length > 0) {
                try {
                  // The require function itself IS __webpack_require__
                  window.__JSRA_require = fakeRequire;
                  window.__JSRA_require_m = fakeModules;
                  require = fakeRequire;
                  requirePath = 'window.__JSRA_require';
                } catch(e) {
                  result.errors.push({ strategy: 'webpackJsonp hook', error: e.message });
                }
              }
            }
          }
        }
        return origPush.apply(this, arguments);
      };
    }

    // Strategy 2: Check if __webpack_require__ is already exposed
    if (!require) {
      var candidates = ['__webpack_require__', '__webpack_modules__', 'webpackJsonp'];
      for (var i = 0; i < candidates.length; i++) {
        if (typeof window[candidates[i]] === 'function') {
          require = window[candidates[i]];
          requirePath = 'window.' + candidates[i];
          break;
        }
      }
    }

    // Strategy 3: Search window for webpack require-like functions
    if (!require) {
      var allKeys = Object.keys(window);
      for (var i = 0; i < allKeys.length; i++) {
        var k = allKeys[i];
        try {
          var v = window[k];
          if (typeof v === 'function' && v.c && typeof v.c === 'object') {
            // __webpack_require__ has a .c (module cache) property
            require = v;
            requirePath = 'window.' + k;
            break;
          }
        } catch(e) {}
      }
    }

    return { require: require, path: requirePath };
  }

  // === 3. Enumerate module cache exports ===
  function enumerateExports(require) {
    var candidates = [];
    try {
      var cache = require.c || require.cache || {};
      var keys = Object.keys(cache);
      result.moduleCacheKeys = keys.slice(0, 500);

      for (var i = 0; i < Math.min(keys.length, 200); i++) {
        try {
          var mod = cache[keys[i]];
          if (!mod || !mod.exports) continue;
          var exp = mod.exports;
          var exportKeys = Object.keys(exp);

          for (var j = 0; j < exportKeys.length; j++) {
            var ek = exportKeys[j];
            var val = exp[ek];
            if (typeof val === 'function') {
              var src = '';
              try { src = val.toString().substring(0, 200); } catch(e) {}
              candidates.push({
                moduleId: keys[i],
                exportName: ek,
                type: 'function',
                srcSnippet: src,
                arity: val.length
              });
            } else if (typeof val === 'object' && val !== null) {
              // Check for default export with function properties
              var subKeys = Object.keys(val).slice(0, 10);
              for (var k = 0; k < subKeys.length; k++) {
                if (typeof val[subKeys[k]] === 'function') {
                  candidates.push({
                    moduleId: keys[i],
                    exportName: ek + '.' + subKeys[k],
                    type: 'function',
                    arity: val[subKeys[k]].length
                  });
                }
              }
            }
          }
        } catch(e) {}
      }
    } catch(e) {
      result.errors.push({ strategy: 'enumerateExports', error: e.message });
    }
    return candidates;
  }

  // === 4. Detect global exports (Vite/Rollup/ESM) ===
  function detectGlobalExports() {
    var exports = [];
    var known = ['CryptoJS', 'JSEncrypt', 'md5', 'sha256', 'sha1', 'aes', 'Base64',
                 'encrypt', 'decrypt', 'sign', 'verify', 'hash', 'hmac'];

    var keys = Object.keys(window);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      if (k.charAt(0) === '_') continue;
      try {
        var v = window[k];
        if (typeof v === 'function') {
          var src = '';
          try { src = v.toString().substring(0, 100); } catch(e) {}
          exports.push({ name: k, type: 'function', srcSnippet: src });
        } else if (typeof v === 'object' && v !== null) {
          var subKeys = Object.keys(v).slice(0, 5);
          for (var j = 0; j < subKeys.length; j++) {
            if (typeof v[subKeys[j]] === 'function') {
              exports.push({ name: k + '.' + subKeys[j], type: 'function' });
            }
          }
        }
      } catch(e) {}
    }
    return exports;
  }

  // === 5. Detect Vite/Rollup ===
  function detectViteRollup() {
    var info = { detected: false, type: 'unknown' };

    // Vite: __vite_plugin_meta__, import.meta.hot
    if (window.__vite_plugin_meta__ || document.querySelector('script[type="module"]')) {
      info.detected = true;
      info.type = 'vite';
    }

    // Rollup: check for rollup-specific globals
    if (window.__rollup_plugin__) {
      info.detected = true;
      info.type = 'rollup';
    }

    return info;
  }

  // === Main execution ===
  try {
    var chunks = detectChunkArrays();
    result.chunkArrays = chunks;

    if (chunks.length > 0) {
      result.detected = true;
      // Determine Webpack version
      var hasWP5 = chunks.some(function(c) { return c.name.indexOf('webpackChunk') === 0; });
      var hasWP4 = chunks.some(function(c) { return c.name === 'webpackJsonp'; });
      result.type = hasWP5 ? 'webpack5' : (hasWP4 ? 'webpack4' : 'unknown');

      var capture = tryCaptureRequire();
      if (capture.require) {
        result.requireAvailable = true;
        result.requirePath = capture.path;
        result.candidateExports = enumerateExports(capture.require);
      }
    } else {
      var viteInfo = detectViteRollup();
      if (viteInfo.detected) {
        result.detected = true;
        result.type = viteInfo.type;
      }
    }

    // Always detect global exports
    result.globalExports = detectGlobalExports();

  } catch(e) {
    result.errors.push({ strategy: 'main', error: e.message });
  }

  console.log('[JSRA] Module probe v1: detected=' + result.detected + ' type=' + result.type +
    ' require=' + result.requireAvailable + ' candidates=' + result.candidateExports.length);
})();
"""


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_probe(), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
