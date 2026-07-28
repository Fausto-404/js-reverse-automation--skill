#!/usr/bin/env python3
"""Evidence-driven encryption/signature candidate discovery.

Consumes runtime events, Webpack exports, globals, optional static AST results,
and manual hints.  Scores candidates across 8 dimensions and tracks verification
status.

Usage:
  python3 scripts/detect_encryption.py \
    --probe-artifacts artifacts/probe_dump.json \
    --module-artifacts artifacts/module_dump.json \
    --evidence-graph artifacts/evidence_graph.json \
    --analysis analysis_result.json \
    --output artifacts/encryption_candidates.json
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from typing import Any

from common import dump_json, flatten_events, iter_stack_lines, keyword_score, load_json

STACK_FN = re.compile(r"(?:at\s+)?([\w$.[\]<>-]+)\s*(?:\(|@)")


def canonical_id(source: str, name: str, module_id: str = "") -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.:$\-]+", "_", name or "anonymous")
    return f"{source}:{module_id}:{clean}" if module_id else f"{source}:{clean}"


def ensure_candidate(store: dict[str, dict], cid: str, name: str, source: str, **extra: Any) -> dict:
    candidate = store.setdefault(cid, {
        "id": cid, "name": name or "anonymous", "source": source, "type": extra.get("type", "function"),
        "module_id": extra.get("module_id"), "path": extra.get("path") or name,
        "source_snippet": extra.get("source_snippet", ""), "evidence": [], "scores": {},
        "verified": False, "verification": [],
    })
    for key, value in extra.items():
        if value not in (None, "", []):
            candidate[key] = value
    return candidate


def build_candidates(probe: dict, modules: dict, graph: dict, analysis: dict) -> list[dict]:
    store: dict[str, dict] = {}
    events = flatten_events(probe)
    event_by_id = {str(e.get("event_id")): e for e in events}
    fingerprint_edges = [e for e in graph.get("edges", []) if e.get("type") == "fingerprint_flow"]

    # === Runtime functions and stack frames ===
    for event in events:
        function = event.get("function") or event.get("name")
        event_type = str(event.get("type", ""))
        if function and not event_type.startswith("network."):
            cid = canonical_id("runtime", str(function))
            role = "primitive" if event_type.startswith(("crypto.", "encoding.", "serializer.")) else "entrypoint"
            c = ensure_candidate(store, cid, str(function), "runtime", role=role)
            c["evidence"].append({
                "type": "runtime_event",
                "event_id": event.get("event_id"),
                "event_type": event.get("type"),
                "trace_id": event.get("trace_id")
            })
            if event.get("output_fingerprint"):
                c.setdefault("output_fingerprints", []).append(event["output_fingerprint"])

        # Stack frame extraction
        for line in iter_stack_lines(event):
            match = STACK_FN.search(line)
            if match:
                name = match.group(1)
                if name in ("Error", "record", "wrapped"):
                    continue
                cid = canonical_id("stack", name)
                c = ensure_candidate(store, cid, name, "stack")
                c["evidence"].append({
                    "type": "runtime_stack",
                    "event_id": event.get("event_id"),
                    "line": line[:300]
                })

    # === Real Webpack exports ===
    for item in modules.get("modules", []) or []:
        name = item.get("export_path") or item.get("name") or "anonymous"
        cid = canonical_id("webpack", name, str(item.get("module_id", "unknown")))
        module_id = str(item.get("module_id", ""))
        export_path = item.get("export_path") or name
        webpack_source = str(item.get("source") or "default")
        runtime_path = f"webpack:{webpack_source}:{module_id}:{export_path}"
        ensure_candidate(
            store, cid, name, "webpack",
            type="webpack_export", module_id=module_id,
            path=runtime_path, export_path=export_path,
            source_snippet=item.get("source_snippet", "")
        )["evidence"].append({"type": "module_export", "source": item.get("source")})

    # === Global functions ===
    for item in modules.get("globals", []) or []:
        name = item.get("name") or item.get("path") or "anonymous"
        cid = canonical_id("global", name)
        ensure_candidate(
            store, cid, name, "global",
            path=item.get("path"), source_snippet=item.get("source_snippet", "")
        )["evidence"].append({"type": "global_function"})

    # === Optional static AST candidates ===
    for item in modules.get("static", []) or []:
        name = item.get("name") or item.get("path") or "anonymous"
        cid = canonical_id("static", name)
        ensure_candidate(
            store, cid, name, "static",
            path=item.get("path") or name,
            source_snippet=item.get("source_snippet", ""),
            location=item.get("location")
        )["evidence"].append({"type": "static_ast", "signals": item.get("signals", [])})

    # === Manual hints (backward-compatible, evidence only) ===
    for param_name, config in (analysis.get("parameters") or {}).items():
        entry = config.get("entrypoint") or {}
        name = entry.get("path")
        if name:
            cid = canonical_id("hint", name)
            c = ensure_candidate(
                store, cid, name, "hint",
                type=entry.get("type", "hint"), path=name,
                source_snippet=entry.get("source_hint", "")
            )
            c["parameter"] = param_name
            c["evidence"].append({"type": "manual_hint", "details": entry.get("evidence", [])})

    # === Cross-source name correlation ===
    normalized = defaultdict(list)
    for c in store.values():
        normalized[re.sub(r"[^a-z0-9]", "", c["name"].lower())].append(c)
    for group in normalized.values():
        if len(group) > 1:
            sources = sorted({c["source"] for c in group})
            for c in group:
                c["evidence"].append({"type": "cross_source_name", "sources": sources})

    # === Score each candidate ===
    for c in store.values():
        evidence_types = [e.get("type") for e in c["evidence"]]
        runtime_count = evidence_types.count("runtime_event") + evidence_types.count("runtime_stack")
        network_correlation = (
            1.0 if c["verified"]
            else (0.5 if runtime_count and any(
                str(e.get("event_type", "")).startswith("network") for e in c["evidence"]
            ) else 0.0)
        )
        scores = {
            "name": keyword_score(c["name"]),
            "source_keyword": keyword_score(c.get("source_snippet", "")),
            "runtime_stack": min(1.0, runtime_count / 3),
            "request_correlation": network_correlation,
            "input_output_flow": 1.0 if c["verified"] else (0.3 if c.get("output_fingerprints") else 0.0),
            "module_export": 1.0 if c["source"] == "webpack" else (0.6 if c["source"] == "global" else 0.0),
            "cross_source": 1.0 if "cross_source_name" in evidence_types else 0.0,
            "verification": 1.0 if c["verified"] else 0.0,
        }
        weights = {
            "name": .12, "source_keyword": .10, "runtime_stack": .17,
            "request_correlation": .16, "input_output_flow": .18,
            "module_export": .08, "cross_source": .07, "verification": .12
        }
        total = round(sum(scores[k] * weights[k] for k in weights), 3)
        c["scores"] = scores
        c["total_score"] = total
        c["confidence"] = (
            "high" if c["verified"] and total >= .62
            else ("medium" if total >= .38 else "low")
        )
        c["evidence"] = c["evidence"][:100]

    return sorted(store.values(), key=lambda x: (x["verified"], x["total_score"]), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-driven encryption/signature candidate discovery.")
    parser.add_argument("--probe-artifacts", required=True, help="Path to probe_dump.json.")
    parser.add_argument("--module-artifacts", help="Path to module_dump.json.")
    parser.add_argument("--evidence-graph", help="Path to evidence_graph.json.")
    parser.add_argument("--static-artifacts", help="Path to static_candidates.json.")
    parser.add_argument("--analysis", help="Path to analysis_result.json.")
    parser.add_argument("--output", required=True, help="Path to output candidates JSON.")
    args = parser.parse_args()

    probe = load_json(args.probe_artifacts, {})
    modules = load_json(args.module_artifacts, {}) if args.module_artifacts else {}
    graph = load_json(args.evidence_graph, {}) if args.evidence_graph else {}
    static_artifacts = load_json(args.static_artifacts, {}) if args.static_artifacts else {}
    if static_artifacts:
        modules = dict(modules)
        modules.setdefault("static", []).extend(static_artifacts.get("candidates", []))
    analysis = load_json(args.analysis, {}) if args.analysis else {}

    candidates = build_candidates(probe, modules, graph, analysis)
    result = {
        "version": "2.1.0",
        "candidates": candidates,
        "stats": {
            "total": len(candidates),
            "high": sum(c["confidence"] == "high" for c in candidates),
            "medium": sum(c["confidence"] == "medium" for c in candidates),
            "low": sum(c["confidence"] == "low" for c in candidates),
            "verified": sum(c["verified"] for c in candidates)
        }
    }
    dump_json(args.output, result)
    print(f"[OK] candidate discovery: {args.output} {result['stats']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
