#!/usr/bin/env python3
"""Shared utilities for JSRA scripts.

Provides JSON I/O with atomic writes, SHA-256 fingerprinting, sensitive data
redaction, probe dump event flattening, keyword scoring, and stack iteration.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

SENSITIVE_KEYS = re.compile(
    r"pass(word)?|token|secret|authorization|cookie|session|credential", re.I
)
KEYWORDS_HIGH = ("encrypt", "decrypt", "cipher", "sign", "hmac", "digest", "hash")
KEYWORDS_MEDIUM = ("rsa", "aes", "des", "sm2", "sm3", "sm4", "md5", "sha", "base64", "crypto")
KEYWORDS_LOW = ("encode", "decode", "token", "nonce", "secret")


def load_json(path: str | Path, default: Any = None) -> Any:
    """Load JSON from *path*, returning *default* if the file is missing."""
    p = Path(path)
    if not p.exists():
        if default is not None:
            return default
        raise FileNotFoundError(p)
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: str | Path, value: Any) -> None:
    """Atomically write *value* as JSON to *path* (via rename)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    temp.replace(p)


def fingerprint(value: Any) -> str:
    """Return ``sha256:<hex>`` for the canonical JSON of *value*."""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def redact(value: Any, key: str = "", max_len: int = 96) -> Any:
    """Recursively redact sensitive fields and truncate long strings."""
    if SENSITIVE_KEYS.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k), max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key, max_len) for v in value[:20]]
    text = str(value)
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def flatten_events(probe: dict) -> list[dict]:
    """Normalise legacy probe dump collections into a flat event list.

    The v2.0 probe stores events in separate lists (``requests``, ``crypto``,
    ``serializers``, ``calls``, ``encoders``).  The v2.1 probe uses a single
    ``events`` list with a ``type`` field.  This function merges both formats
    so downstream code always sees a flat list.
    """
    events = list(probe.get("events") or [])
    mapping = {
        "requests": "network.request",
        "crypto": "crypto.operation",
        "serializers": "serializer.operation",
        "calls": "function.call",
        "encoders": "encoding.operation",
    }
    for collection, default_type in mapping.items():
        for index, raw in enumerate(probe.get(collection) or []):
            event = dict(raw)
            event.setdefault("type", default_type)
            event.setdefault("event_id", f"legacy-{collection}-{index}")
            event.setdefault("timestamp", index)
            events.append(event)
    return events


def keyword_score(text: str) -> float:
    """Score *text* against crypto-related keyword tiers."""
    lower = (text or "").lower()
    if any(k in lower for k in KEYWORDS_HIGH):
        return 1.0
    if any(k in lower for k in KEYWORDS_MEDIUM):
        return 0.7
    if any(k in lower for k in KEYWORDS_LOW):
        return 0.35
    return 0.0


def iter_stack_lines(event: dict) -> Iterable[str]:
    """Yield stack lines from an event, normalising dict/str/list formats."""
    stack = event.get("stack") or event.get("stack_lines") or []
    if isinstance(stack, str):
        yield from stack.splitlines()
    elif isinstance(stack, list):
        for line in stack:
            if isinstance(line, dict):
                yield " ".join(str(line.get(k, "")) for k in ("function", "url", "line", "column"))
            else:
                yield str(line)
