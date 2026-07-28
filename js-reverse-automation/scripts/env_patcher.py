#!/usr/bin/env python3
"""Environment patcher for running obfuscated JS in Node.js VM sandbox.

Diagnoses missing browser APIs and generates patches to make the JS runnable.

Usage:
  python3 scripts/env_patcher.py --input bundle.js --output artifacts/env_report.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from common import dump_json, load_json


DIAGNOSE_SCRIPT = r'''
const vm = require('vm');
const fs = require('fs');

const input = process.argv[2];
const code = fs.readFileSync(input, 'utf8');

// Create sandbox with basic browser APIs
const sandbox = {
  window: {}, self: {}, global: {}, globalThis: {},
  console: { log: () => {}, warn: () => {}, error: () => {} },
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  setInterval: (fn, ms) => setInterval(fn, ms),
  clearTimeout: (id) => clearTimeout(id),
  clearInterval: (id) => clearInterval(id),
  atob: (s) => Buffer.from(s, 'base64').toString('binary'),
  btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
  TextEncoder: TextEncoder,
  TextDecoder: TextDecoder,
  URL: URL,
  URLSearchParams: URLSearchParams,
};

// Make window/self/global/globalThis point to sandbox
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.global = sandbox;
sandbox.globalThis = sandbox;

// Proxy to track undefined access
const undefinedPaths = new Set();
const proxy = new Proxy(sandbox, {
  get(target, prop) {
    if (prop === Symbol.unscopables) return undefined;
    if (prop in target) return target[prop];
    if (typeof prop === 'string' && !prop.startsWith('_')) {
      undefinedPaths.add(prop);
    }
    return undefined;
  },
  set(target, prop, value) {
    target[prop] = value;
    return true;
  }
});

// Run in VM
const context = vm.createContext(proxy);
try {
  vm.runInContext(code, context, { timeout: 5000 });
  console.log(JSON.stringify({
    success: true,
    error: null,
    undefinedPaths: Array.from(undefinedPaths).sort(),
    stats: { events: undefinedPaths.size }
  }));
} catch (error) {
  console.log(JSON.stringify({
    success: false,
    error: error.message,
    undefinedPaths: Array.from(undefinedPaths).sort(),
    stats: { events: undefinedPaths.size }
  }));
}
'''


def diagnose(js_path: str) -> dict:
    """Run diagnosis on a JS file to find missing browser APIs."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(DIAGNOSE_SCRIPT)
        diag_script = f.name

    try:
        result = subprocess.run(
            ['node', diag_script, js_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"success": False, "error": result.stderr, "undefinedPaths": []}
    except Exception as e:
        return {"success": False, "error": str(e), "undefinedPaths": []}
    finally:
        Path(diag_script).unlink(missing_ok=True)


# Mapping from undefined paths to required modules
MODULE_MAP = {
    'navigator': 'bom/navigator',
    'location': 'bom/location',
    'screen': 'bom/screen',
    'localStorage': 'bom/storage',
    'sessionStorage': 'bom/storage',
    'crypto': 'bom/crypto',
    'performance': 'bom/performance',
    'history': 'bom/history',
    'document': 'dom/document',
    'Element': 'dom/elements',
    'HTMLElement': 'dom/elements',
    'Event': 'dom/event',
    'fetch': 'webapi/fetch',
    'XMLHttpRequest': 'webapi/xhr',
    'Blob': 'webapi/blob',
    'FormData': 'webapi/blob',
    'File': 'webapi/blob',
    'WebSocket': 'webapi/network',
    'TextEncoder': 'encoding/textencoder',
    'TextDecoder': 'encoding/textencoder',
    'atob': 'encoding/atob',
    'btoa': 'encoding/atob',
}


def select_modules(undefined_paths: list[str]) -> list[str]:
    """Select required modules based on undefined paths."""
    modules = set()
    for path in undefined_paths:
        for prefix, module in MODULE_MAP.items():
            if path.startswith(prefix) or path == prefix:
                modules.add(module)
    return sorted(modules)


def main() -> int:
    parser = argparse.ArgumentParser(description="Environment patcher for JS sandbox.")
    parser.add_argument("--input", required=True, help="Path to JS file.")
    parser.add_argument("--output", required=True, help="Path to output report.")
    args = parser.parse_args()

    report = diagnose(args.input)
    if report.get("undefinedPaths"):
        report["selectedModules"] = select_modules(report["undefinedPaths"])

    dump_json(args.output, report)
    print(json.dumps({
        "success": report.get("success", False),
        "undefinedPaths": len(report.get("undefinedPaths", [])),
        "selectedModules": len(report.get("selectedModules", [])),
        "output": args.output
    }, ensure_ascii=False))
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
