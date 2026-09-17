#!/usr/bin/env python3
"""Build a lightweight JSRA evidence graph from probe and module dumps.

Creates nodes (events) and edges (parent-child, fingerprint_flow, temporal)
to correlate producers and consumers via matching SHA-256 fingerprints.

Usage:
  python3 scripts/build_evidence_graph.py \
    --probe artifacts/probe_dump.json \
    --modules artifacts/module_dump.json \
    --output artifacts/evidence_graph.json
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from common import dump_json, flatten_events, load_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a lightweight JSRA evidence graph.")
    parser.add_argument("--probe", required=True, help="Path to probe_dump.json.")
    parser.add_argument("--modules", required=False, help="Path to module_dump.json.")
    parser.add_argument("--output", required=True, help="Path to output evidence_graph.json.")
    args = parser.parse_args()

    probe = load_json(args.probe, {})
    modules = load_json(args.modules, {}) if args.modules else {}
    events = flatten_events(probe)

    nodes = []
    edges = []
    by_trace = defaultdict(list)
    producers = defaultdict(list)
    consumers = defaultdict(list)

    for event in events:
        event_id = str(event.get("event_id"))
        trace_id = str(event.get("trace_id") or "unscoped")
        nodes.append({"id": event_id, "kind": "event", "data": event})
        by_trace[trace_id].append(event)
        parent = event.get("parent_event_id")
        if parent:
            edges.append({"from": str(parent), "to": event_id, "type": "parent"})
        if event.get("output_fingerprint"):
            producers[event["output_fingerprint"]].append(event_id)
        if event.get("input_fingerprint"):
            consumers[event["input_fingerprint"]].append(event_id)

    # Fingerprint flow edges (producer -> consumer).  A runtime hook often
    # creates a new trace id for the network call after the crypto call has
    # completed, so requiring equal trace ids loses the most useful edges.
    # Pair each consumer with the nearest preceding producer instead.  Exact
    # fingerprints remain the proof signal; the time relation only disambiguates
    # repeated values and prevents future-to-past edges.
    event_ids = {str(event.get("event_id")) for event in events}
    for fp, source_ids in producers.items():
        source_events = [
            next((event for event in events if str(event.get("event_id")) == source_id), {})
            for source_id in source_ids
            if source_id in event_ids
        ]
        for target_id in consumers.get(fp, []):
            if target_id not in event_ids:
                continue
            target_event = next((e for e in events if str(e.get("event_id")) == target_id), {})
            target_time = target_event.get("timestamp")
            preceding = [
                event for event in source_events
                if str(event.get("event_id")) != target_id
                and (
                    not isinstance(target_time, (int, float))
                    or not isinstance(event.get("timestamp"), (int, float))
                    or event.get("timestamp") <= target_time
                )
            ]
            if not preceding:
                continue
            source_event = max(
                preceding,
                key=lambda event: event.get("timestamp", 0)
                if isinstance(event.get("timestamp"), (int, float)) else 0,
            )
            source_id = str(source_event.get("event_id"))
            source_time = source_event.get("timestamp")
            delta = None
            if isinstance(source_time, (int, float)) and isinstance(target_time, (int, float)):
                delta = max(0, target_time - source_time)
            edges.append({
                "from": source_id, "to": target_id,
                "type": "fingerprint_flow",
                "fingerprint": fp,
                "trace_id": source_event.get("trace_id"),
                "target_trace_id": target_event.get("trace_id"),
                "same_trace": source_event.get("trace_id") == target_event.get("trace_id"),
                "time_delta_ms": delta,
            })

    # Temporal edges (within same trace)
    for trace_id, trace_events in by_trace.items():
        ordered = sorted(trace_events, key=lambda e: e.get("timestamp", 0))
        for left, right in zip(ordered, ordered[1:]):
            edges.append({
                "from": str(left.get("event_id")),
                "to": str(right.get("event_id")),
                "type": "temporal",
                "trace_id": trace_id
            })

    # Module/globals as candidate source nodes
    for item in (modules.get("modules") or []) + (modules.get("globals") or []):
        node_id = str(item.get("id") or item.get("path") or item.get("name"))
        nodes.append({"id": node_id, "kind": "candidate_source", "data": item})

    result = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "events": len(events),
            "traces": len(by_trace),
            "fingerprint_flows": sum(1 for e in edges if e["type"] == "fingerprint_flow")
        },
    }
    dump_json(args.output, result)
    print(f"[OK] evidence graph: {args.output} ({result['stats']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
