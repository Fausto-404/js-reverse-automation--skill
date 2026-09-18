#!/usr/bin/env python3
"""Emit a low-side-effect adversarial runtime probe.

The generated probe is deliberately split into observation and intervention:
observation records anti-debug/anti-hook/environment signals, while intervention
only applies the explicitly requested debugger-source filter.  Every installed
patch is tracked and can be restored through ``uninstall()``.

Usage:
  python3 scripts/emit_adversarial_runtime_probe.py \
    --output generated/adversarial_runtime_probe.js
  python3 scripts/emit_adversarial_runtime_probe.py \
    --mode intervene --output generated/adversarial_runtime_probe.js
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


HOOK_REGISTRY = (Path(__file__).with_name("hook_registry.js")).read_text(encoding="utf-8")

TEMPLATE = r'''(() => {
  "use strict";
  const PROBE_ID = "adversarial-runtime";
  const CONFIG = __CONFIG__;
  const KEYWORDS = /pass(word)?|token|secret|authorization|cookie|session|credential/i;
  const root = window;
__HOOK_REGISTRY__
  const registry = getHookRegistry(root);

  if (root.__JSRA_ADVERSARIAL__ && root.__JSRA_ADVERSARIAL__.probe_id === PROBE_ID) {
    return root.__JSRA_ADVERSARIAL__;
  }

  const native = {
    json: JSON.stringify.bind(JSON),
    setTimeout: window.setTimeout.bind(window),
    setInterval: window.setInterval.bind(window),
    clearInterval: window.clearInterval.bind(window),
    fetch: window.fetch,
    eval: window.eval,
    Function: window.Function,
    defineProperty: Object.defineProperty,
    getOwnPropertyDescriptor: Object.getOwnPropertyDescriptor,
    getPrototypeOf: Object.getPrototypeOf,
    toString: Function.prototype.toString,
  };

  const state = {
    probe_id: PROBE_ID,
    mode: CONFIG.mode,
    installedAt: Date.now(),
    events: [],
    patches: [],
    realms: [{ realm_id: "main", kind: "window", url: location.href }],
    maxEvents: CONFIG.maxEvents,
    dropped: 0,
    suppressed: 0,
    suppressedByPath: {},
    health: { installed: true, lostPatches: 0, externalChanges: 0, reconcileErrors: 0, restored: false }
  };
  let counter = 0;
  let healTimer = null;
  let observer = null;
  const active = new Map();

  function id(prefix) {
    counter += 1;
    return `${prefix}-${Date.now().toString(36)}-${counter.toString(36)}`;
  }
  function preview(value, key = "") {
    if (KEYWORDS.test(String(key))) return "<redacted>";
    if (value === null) return "null";
    if (value === undefined) return "undefined";
    if (typeof value === "function") return "[function]";
    if (value instanceof ArrayBuffer) return `[ArrayBuffer:${value.byteLength}]`;
    if (ArrayBuffer.isView(value)) return `[${value.constructor.name}:${value.byteLength}]`;
    if (value && typeof value === "object") return `[${value.constructor && value.constructor.name || "object"}]`;
    const text = String(value);
    return CONFIG.captureRaw ? text.slice(0, 160) : `${typeof value}:${text.length}`;
  }
  function emit(type, detail = {}) {
    const event = {
      event_id: id("adv"),
      trace_id: detail.trace_id || id("trace"),
      type,
      path: detail.path || null,
      function: detail.function || null,
      input: preview(detail.input, detail.key),
      output: preview(detail.output, detail.key),
      metadata: detail.metadata || {},
      timestamp: Date.now()
    };
    if (state.events.length >= state.maxEvents) {
      state.events.shift();
      state.dropped += 1;
    }
    state.events.push(event);
    return event;
  }
  function descriptor(target, key) {
    try {
      let current = target;
      while (current) {
        const desc = native.getOwnPropertyDescriptor(current, key);
        if (desc) return { owner: current, desc };
        current = native.getPrototypeOf(current);
      }
    } catch (_) {}
    return null;
  }
  function installPatch(name, target, key, factory, metadata = {}) {
    if (!target || typeof target[key] !== "function") return null;
    emit("patch.install", { path: name, metadata: { ...metadata, key } });
    const layerId = `adversarial:${name}`;
    const layer = registry.add(target, key, layerId, original => {
      const replacement = factory(original);
      try {
        if (original && original.prototype && replacement && replacement.prototype)
          replacement.prototype = original.prototype;
      } catch (_) {}
      return replacement;
    });
    if (!layer) return null;
    const patch = { name, target, key, layerId, installed: true };
    state.patches.push(patch);
    active.set(name, patch);
    patch.reconcile = () => {
      const result = registry.reconcile(target, key);
      if (result.changed) {
        emit(result.status === "error" ? "patch.reconcile_error" : "patch.reconciled", {
          path: name, metadata: { key, status: result.status, error: result.error || null }
        });
        if (result.status === "error") state.health.reconcileErrors += 1;
        else state.health.externalChanges += 1;
      }
      return result;
    };
    return patch;
  }
  function wrap(target, key, type, path, options = {}) {
    const sampleEvery = Math.max(1, Number(options.sampleEvery || 1));
    const eventBudget = Number.isFinite(Number(options.eventBudget))
      ? Math.max(0, Number(options.eventBudget)) : Infinity;
    const burst = Math.max(0, Number(options.burst || 0));
    let invocationCount = 0;
    function shouldRecord() {
      invocationCount += 1;
      const selected = invocationCount <= eventBudget &&
        (invocationCount <= burst || invocationCount % sampleEvery === 0);
      if (!selected) {
        state.suppressed += 1;
        state.suppressedByPath[path] = (state.suppressedByPath[path] || 0) + 1;
      }
      return selected;
    }
    return installPatch(path, target, key, original => function(...args) {
      if (typeof options.skip === "function" && options.skip.call(this, args))
        return original.apply(this, args);
      const recordInvocation = shouldRecord();
      const traceId = id("trace");
      if (recordInvocation)
        emit(`${type}.call`, { trace_id: traceId, path, function: path, input: args[0], metadata: { argc: args.length } });
      let result;
      try {
        result = original.apply(this, args);
      } catch (error) {
        if (recordInvocation)
          emit(`${type}.error`, { trace_id: traceId, path, function: path, metadata: { error: String(error) } });
        throw error;
      }
      if (result && typeof result.then === "function") {
        return result.then(value => {
          if (recordInvocation)
            emit(`${type}.return`, { trace_id: traceId, path, function: path, output: value });
          return value;
        }, error => {
          if (recordInvocation)
            emit(`${type}.reject`, { trace_id: traceId, path, function: path, metadata: { error: String(error) } });
          throw error;
        });
      }
      if (recordInvocation)
        emit(`${type}.return`, { trace_id: traceId, path, function: path, output: result });
      return result;
    }, options);
  }
  function watchGetter(target, key, path) {
    const found = descriptor(target, key);
    if (!found || !found.desc || typeof found.desc.get !== "function" || found.desc.configurable === false)
      return false;
    const original = found.desc;
    const replacement = { ...original, get() {
      const value = original.get.call(this);
      emit("environment.property_read", { path, key, output: value, metadata: { owner: path } });
      return value;
    }};
    try {
      native.defineProperty(found.owner, key, replacement);
      state.patches.push({ name: `getter:${path}`, target: found.owner, key, descriptor: original, installed: true });
      return true;
    } catch (error) {
      emit("patch.error", { path, metadata: { error: String(error) } });
      return false;
    }
  }
  function resolve(path) {
    return String(path).split(".").reduce((value, key) => value == null ? null : value[key], root);
  }
  function watchProperties() {
    const paths = CONFIG.properties || [
      "navigator.webdriver", "navigator.userAgent", "navigator.platform",
      "navigator.languages", "navigator.plugins", "screen.width", "screen.height",
      "window.innerWidth", "window.innerHeight", "window.outerWidth", "window.outerHeight",
      "document.cookie"
    ];
    for (const path of paths) {
      const parts = path.split(".");
      const key = parts.pop();
      const parent = resolve(parts.join("."));
      if (parent && watchGetter(parent, key, path))
        emit("environment.watch_installed", { path });
    }
  }
  function observeDynamicCode() {
    const stripDebugger = source => typeof source === "string"
      ? source.replace(/\bdebugger\s*;?/g, "") : source;
    installPatch("window.eval", root, "eval", original => function(source) {
      const next = CONFIG.mode === "intervene" ? stripDebugger(source) : source;
      if (next !== source) emit("intervention.debugger_source", { path: "window.eval", input: source, metadata: { action: "strip" } });
      emit("dynamic.eval.call", { path: "window.eval", input: next });
      return original.call(this, next);
    });
    installPatch("window.Function", root, "Function", original => function(...args) {
      const last = args.length - 1;
      if (CONFIG.mode === "intervene" && last >= 0 && typeof args[last] === "string") {
        const next = stripDebugger(args[last]);
        if (next !== args[last]) emit("intervention.debugger_source", { path: "window.Function", input: args[last], metadata: { action: "strip" } });
        args[last] = next;
      }
      emit("dynamic.function.call", { path: "window.Function", input: args[last], metadata: { argc: args.length } });
      return new.target ? Reflect.construct(original, args, new.target) : original.apply(this, args);
    });
    root.Function.prototype = native.Function.prototype;
  }
  function observeNetwork() {
    if (typeof root.fetch === "function") {
      wrap(root, "fetch", "network.fetch", "window.fetch");
    }
    if (root.XMLHttpRequest) {
      wrap(root.XMLHttpRequest.prototype, "open", "network.xhr_open", "XMLHttpRequest.open");
      wrap(root.XMLHttpRequest.prototype, "setRequestHeader", "network.xhr_header", "XMLHttpRequest.setRequestHeader");
      wrap(root.XMLHttpRequest.prototype, "send", "network.xhr_send", "XMLHttpRequest.send");
    }
    if (root.Response) {
      ["json", "text", "arrayBuffer", "blob"].forEach(key => wrap(root.Response.prototype, key, "network.response", `Response.${key}`));
    }
    if (root.WebSocket) wrap(root.WebSocket.prototype, "send", "network.websocket", "WebSocket.send", {
      skip: function() {
        try {
          const url = String(this && this.url || "");
          return (CONFIG.controlWebSocketUrls || []).some(fragment => url.includes(fragment));
        } catch (_) { return false; }
      }
    });
  }
  function observeCrypto() {
    if (!root.crypto || !root.crypto.subtle) return;
    ["encrypt", "decrypt", "sign", "verify", "digest", "importKey", "exportKey", "deriveKey", "deriveBits", "generateKey"].forEach(key => {
      wrap(root.crypto.subtle, key, "crypto.subtle", `crypto.subtle.${key}`);
    });
    if (typeof root.crypto.getRandomValues === "function") wrap(root.crypto, "getRandomValues", "crypto.random", "crypto.getRandomValues");
  }
  function observeLoaders() {
    if (root.Worker) {
      installPatch("window.Worker", root, "Worker", original => function(...args) {
        emit("realm.worker_create.call", { path: "window.Worker", input: args[0], metadata: { argc: args.length } });
        return new original(...args);
      });
    }
    if (root.SharedWorker) {
      installPatch("window.SharedWorker", root, "SharedWorker", original => function(...args) {
        emit("realm.shared_worker_create.call", { path: "window.SharedWorker", input: args[0], metadata: { argc: args.length } });
        return new original(...args);
      });
    }
    if (root.WebAssembly) {
      ["instantiate", "instantiateStreaming"].forEach(key => {
        if (typeof root.WebAssembly[key] === "function") wrap(root.WebAssembly, key, "loader.wasm", `WebAssembly.${key}`);
      });
    }
    if (root.document && root.MutationObserver) {
      observer = new MutationObserver(records => records.forEach(record => record.addedNodes && Array.from(record.addedNodes).forEach(node => {
        if (node && node.tagName === "SCRIPT") emit("loader.script", { path: "script.src", input: node.src, metadata: { async: !!node.async, type: node.type || "" } });
        if (node && node.tagName === "IFRAME") emit("realm.iframe_create", { path: "iframe.src", input: node.src });
      })));
      observer.observe(root.document.documentElement || root.document, { childList: true, subtree: true });
    }
  }
  function observeControlFlow() {
    if (!CONFIG.controlFlow) return;
    if (root.console) {
      ["clear", "table"].forEach(key => {
        if (typeof root.console[key] === "function")
          wrap(root.console, key, "control.console", `console.${key}`, { sampleEvery: 1, eventBudget: 64 });
      });
    }
    if (root.history) {
      ["pushState", "replaceState", "back", "forward", "go"].forEach(key => {
        if (typeof root.history[key] !== "function") return;
        installPatch(`history.${key}`, root.history, key, original => function(...args) {
          const blocked = CONFIG.mode === "intervene" && ["back", "forward", "go"].includes(key);
          emit(blocked ? "intervention.history_blocked" : "control.history.call", {
            path: `history.${key}`, input: args[0], metadata: { argc: args.length, blocked }
          });
          if (blocked) return undefined;
          return original.apply(this, args);
        });
      });
    }
    if (root.Storage && root.Storage.prototype) {
      ["getItem", "setItem", "removeItem", "clear"].forEach(key => {
        if (typeof root.Storage.prototype[key] !== "function") return;
        wrap(root.Storage.prototype, key, "control.storage", `Storage.${key}`, {
          sampleEvery: 1,
          eventBudget: 128,
          skip: function(args) {
            return key !== "clear" && typeof args[0] === "string" && !KEYWORDS.test(args[0]);
          }
        });
      });
    }
    if (typeof root.close === "function") {
      installPatch("window.close", root, "close", original => function(...args) {
        const blocked = CONFIG.mode === "intervene";
        emit(blocked ? "intervention.close_blocked" : "control.close.call", {
          path: "window.close", metadata: { argc: args.length, blocked }
        });
        if (blocked) return undefined;
        return original.apply(this, args);
      });
    }
  }
  function observeIntegrity() {
    const options = {
      eventBudget: CONFIG.integrityEventBudget,
      sampleEvery: CONFIG.integritySampleEvery,
      burst: CONFIG.integrityBurst,
    };
    // Browser libraries call these methods at very high frequency.  Capture
    // an initial burst plus bounded samples so integrity evidence cannot evict
    // crypto/network events from the ring buffer.
    wrap(Function.prototype, "toString", "integrity.toString", "Function.prototype.toString", options);
    wrap(Object, "getOwnPropertyDescriptor", "integrity.descriptor", "Object.getOwnPropertyDescriptor", options);
    wrap(Object, "getPrototypeOf", "integrity.prototype", "Object.getPrototypeOf", options);
  }
  function install() {
    watchProperties();
    observeDynamicCode();
    observeNetwork();
    observeControlFlow();
    observeCrypto();
    observeLoaders();
    observeIntegrity();
    if (CONFIG.persistent) {
      healTimer = native.setInterval(() => state.patches.slice().forEach(patch => {
        try { if (patch.reconcile) patch.reconcile(); } catch (error) {
          emit("patch.reconcile_error", { path: patch.name, metadata: { error: String(error) } });
          state.health.reconcileErrors += 1;
        }
      }), CONFIG.healIntervalMs);
    }
    emit("probe.ready", { metadata: { mode: CONFIG.mode, persistent: CONFIG.persistent } });
  }
  function restore() {
    if (healTimer) native.clearInterval(healTimer);
    if (observer) observer.disconnect();
    for (const patch of state.patches.slice().reverse()) {
      try {
        if (patch.descriptor) native.defineProperty(patch.target, patch.key, patch.descriptor);
        else if (patch.layerId) registry.remove(patch.target, patch.key, patch.layerId);
      } catch (_) {}
    }
    state.health.restored = true;
    state.health.installed = false;
    emit("probe.restored");
  }
  const api = {
    probe_id: PROBE_ID,
    state,
    export() { return { probe_id: PROBE_ID, exportedAt: Date.now(), state: { ...state, events: state.events.slice(), patches: state.patches.map(p => ({ name: p.name, key: p.key, installed: p.installed })) } }; },
    clear() { state.events.length = 0; state.dropped = 0; state.suppressed = 0; state.suppressedByPath = {}; },
    uninstall: restore,
    markTrace(label = "manual") { return id(label); }
  };
  root.__JSRA_ADVERSARIAL__ = api;
  install();
  return api;
})();
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit JSRA adversarial runtime probe.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("observe", "intervene"), default="observe")
    parser.add_argument("--max-events", type=int, default=5000)
    parser.add_argument("--integrity-event-budget", type=int, default=256,
                        help="Maximum integrity-hook invocations recorded per method.")
    parser.add_argument("--integrity-sample-every", type=int, default=64,
                        help="After the initial burst, record every Nth integrity invocation.")
    parser.add_argument("--integrity-burst", type=int, default=16,
                        help="Record the first N integrity invocations in full.")
    parser.add_argument("--heal-interval-ms", type=int, default=1000)
    parser.add_argument("--properties", default="")
    parser.add_argument("--control-websocket-url", action="append", default=[],
                        help="URL fragment for a JSRPC/control WebSocket to leave untouched.")
    parser.add_argument("--no-control-flow", action="store_true",
                        help="Skip console/history/storage/window.close observation.")
    parser.add_argument("--capture-raw", action="store_true")
    parser.add_argument("--no-persistent", action="store_true")
    args = parser.parse_args()
    properties = [item.strip() for item in args.properties.split(",") if item.strip()]
    if not properties:
        properties = [
            "navigator.webdriver", "navigator.userAgent", "navigator.platform",
            "navigator.languages", "navigator.plugins", "screen.width", "screen.height",
            "window.innerWidth", "window.innerHeight", "window.outerWidth", "window.outerHeight",
            "document.cookie"
        ]
    config = {
        "mode": args.mode,
        "maxEvents": max(100, args.max_events),
        "integrityEventBudget": max(1, args.integrity_event_budget),
        "integritySampleEvery": max(1, args.integrity_sample_every),
        "integrityBurst": max(0, args.integrity_burst),
        "healIntervalMs": max(250, args.heal_interval_ms),
        "properties": properties,
        "captureRaw": bool(args.capture_raw),
        "persistent": not args.no_persistent,
        "controlWebSocketUrls": args.control_websocket_url or ["127.0.0.1:12080", "localhost:12080"],
        "controlFlow": not args.no_control_flow,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = TEMPLATE.replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
    content = content.replace("__HOOK_REGISTRY__", HOOK_REGISTRY)
    output.write_text(content, encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output), "mode": args.mode}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
