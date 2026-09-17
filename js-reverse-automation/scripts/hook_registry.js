// Shared hook composition runtime.
// The function stays local to each generated probe while the registry state is
// shared through window, allowing independently generated probes to compose.
function getHookRegistry(root) {
  const registryKey = "__JSRA_HOOK_REGISTRY__";
  const existing = root[registryKey];
  if (existing && existing.version === 1) return existing;

  const targets = new WeakMap();

  function targetEntries(target, create = false) {
    let entries = targets.get(target);
    if (!entries && create) {
      entries = new Map();
      targets.set(target, entries);
    }
    return entries;
  }

  function entryFor(target, key, create = false) {
    const entries = targetEntries(target, create);
    if (!entries) return null;
    let entry = entries.get(key);
    if (!entry && create) {
      if (!target || typeof target[key] !== "function") return null;
      entry = {
        target,
        key,
        base: target[key],
        current: target[key],
        layers: []
      };
      entries.set(key, entry);
    }
    return entry || null;
  }

  function assign(entry, value) {
    try {
      entry.target[entry.key] = value;
      return entry.target[entry.key] === value;
    } catch (_) {
      return false;
    }
  }

  function rebuild(entry) {
    let current = entry.base;
    for (const layer of entry.layers) {
      current = layer.factory(current);
      if (typeof current !== "function")
        throw new TypeError(`Hook factory did not return a function: ${layer.id}`);
    }
    entry.current = current;
    if (!assign(entry, current)) throw new TypeError(`Hook assignment failed: ${entry.key}`);
    return current;
  }

  function adoptExternal(entry) {
    const current = entry.target[entry.key];
    if (current !== entry.current && typeof current === "function") {
      entry.base = current;
      return true;
    }
    return false;
  }

  function add(target, key, id, factory) {
    if (!target || typeof target[key] !== "function") return null;
    const entry = entryFor(target, key, true);
    const duplicate = entry.layers.find(layer => layer.id === id);
    if (duplicate) {
      adoptExternal(entry);
      try { rebuild(entry); } catch (_) {}
      return { entry, id, duplicate: true };
    }
    adoptExternal(entry);
    const layer = { id, factory };
    entry.layers.push(layer);
    try {
      rebuild(entry);
      return { entry, id, duplicate: false };
    } catch (error) {
      entry.layers = entry.layers.filter(item => item !== layer);
      try { rebuild(entry); } catch (_) {}
      throw error;
    }
  }

  function reconcile(target, key) {
    const entry = entryFor(target, key, false);
    if (!entry) return { status: "none", changed: false };
    const changed = adoptExternal(entry);
    if (!changed) return { status: "ok", changed: false };
    try {
      rebuild(entry);
      return { status: "rebuilt", changed: true };
    } catch (error) {
      return { status: "error", changed: true, error: String(error) };
    }
  }

  function remove(target, key, id) {
    const entry = entryFor(target, key, false);
    if (!entry) return false;
    entry.layers = entry.layers.filter(layer => layer.id !== id);
    if (entry.layers.length === 0) {
      assign(entry, entry.base);
      const entries = targetEntries(target, false);
      if (entries) entries.delete(key);
      return true;
    }
    rebuild(entry);
    return true;
  }

  const registry = {
    version: 1,
    add,
    reconcile,
    remove,
    native(target, key) {
      const entry = entryFor(target, key, false);
      return entry ? entry.base : target && target[key];
    },
    internalDepth: 0,
    runInternal(callback) {
      this.internalDepth += 1;
      try { return callback(); } finally { this.internalDepth -= 1; }
    }
  };
  root[registryKey] = registry;
  return registry;
}
