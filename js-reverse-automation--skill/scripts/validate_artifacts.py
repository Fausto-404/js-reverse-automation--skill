#!/usr/bin/env python3
"""Validate analysis_result.json and generated artifacts."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--jsrpc", required=True, help="Path to generated JSRPC file.")
    parser.add_argument("--flask", required=True, help="Path to generated Flask file.")
    parser.add_argument("--burp", required=True, help="Path to generated Burp markdown.")
    parser.add_argument("--output", required=True, help="Path to validation report JSON.")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def record(
    checks: list[dict],
    failures: list[dict],
    name: str,
    ok: bool,
    success_detail: str,
    failure_detail: str,
) -> None:
    detail = success_detail if ok else failure_detail
    checks.append({"check": name, "ok": ok, "detail": detail})
    if not ok:
        failures.append({"check": name, "detail": failure_detail})


def non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def has_runtime_binding(runtime: dict) -> bool:
    return non_empty_string(runtime.get("bind_this_path")) or non_empty_string(
        runtime.get("bind_this_mode")
    )


def valid_bind_this_mode(runtime: dict) -> bool:
    mode = runtime.get("bind_this_mode")
    if mode is None:
        return True
    return mode in {"window", "global", "entrypoint_parent", "none", "null"}


def has_entrypoint_locator(entrypoint: dict) -> bool:
    entrypoint_type = entrypoint.get("type")
    if entrypoint_type == "resolver":
        return non_empty_string(entrypoint.get("resolver_path")) or non_empty_string(
            entrypoint.get("resolver_name")
        )
    return non_empty_string(entrypoint.get("path")) or non_empty_string(
        entrypoint.get("resolver_name")
    )


def main() -> int:
    args = parse_args()
    analysis_path = Path(args.analysis)
    jsrpc_path = Path(args.jsrpc)
    flask_path = Path(args.flask)
    burp_path = Path(args.burp)
    report_path = Path(args.output)

    analysis = load_json(analysis_path)
    jsrpc_content = jsrpc_path.read_text(encoding="utf-8")
    flask_content = flask_path.read_text(encoding="utf-8")
    burp_content = burp_path.read_text(encoding="utf-8")

    checks: list[dict] = []
    failures: list[dict] = []
    warnings = list(analysis.get("diagnostics", {}).get("warnings", []))

    required_keys = [
        "skill",
        "input",
        "trace",
        "parameters",
        "jsrpc",
        "flask",
        "burp",
        "diagnostics",
        "validation_targets",
    ]
    for key in required_keys:
        record(
            checks,
            failures,
            f"analysis:{key}",
            key in analysis,
            f"top-level key present: {key}",
            f"missing top-level key: {key}",
        )

    requested_parameters = analysis.get("input", {}).get("parameters", [])
    parameters = analysis.get("parameters", {})
    requested_iter = requested_parameters if isinstance(requested_parameters, list) else []
    parameter_map = parameters if isinstance(parameters, dict) else {}
    record(
        checks,
        failures,
        "analysis:input:parameters",
        isinstance(requested_parameters, list) and bool(requested_parameters),
        "input parameters list is present",
        "analysis.input.parameters must be a non-empty list",
    )
    record(
        checks,
        failures,
        "analysis:parameters-object",
        isinstance(parameters, dict),
        "parameters object is present",
        "analysis.parameters must be a JSON object",
    )
    for parameter in requested_iter:
        record(
            checks,
            failures,
            f"analysis:parameter:{parameter}",
            parameter in parameter_map,
            f"parameter contract present: {parameter}",
            f"missing parameter contract for {parameter}",
        )
        if parameter in parameter_map:
            parameter_contract = parameter_map[parameter]
            entrypoint = parameter_contract.get("entrypoint")
            call_signature = parameter_contract.get("call_signature")
            runtime = parameter_contract.get("runtime")
            record(
                checks,
                failures,
                f"analysis:parameter:{parameter}:entrypoint",
                isinstance(entrypoint, dict),
                f"entrypoint contract present for {parameter}",
                f"missing entrypoint contract for {parameter}",
            )
            if isinstance(entrypoint, dict):
                record(
                    checks,
                    failures,
                    f"analysis:parameter:{parameter}:entrypoint-type",
                    non_empty_string(entrypoint.get("type")),
                    f"entrypoint type present for {parameter}",
                    f"missing entrypoint.type for {parameter}",
                )
                record(
                    checks,
                    failures,
                    f"analysis:parameter:{parameter}:entrypoint-locator",
                    has_entrypoint_locator(entrypoint),
                    f"entrypoint locator present for {parameter}",
                    (
                        "entrypoint must define path, resolver_name, or resolver_path "
                        f"for {parameter}"
                    ),
                )
            record(
                checks,
                failures,
                f"analysis:parameter:{parameter}:call-signature",
                isinstance(call_signature, dict),
                f"call signature present for {parameter}",
                f"missing call signature for {parameter}",
            )
            if isinstance(call_signature, dict):
                record(
                    checks,
                    failures,
                    f"analysis:parameter:{parameter}:call-signature-async",
                    isinstance(call_signature.get("async"), bool),
                    f"call_signature.async present for {parameter}",
                    f"call_signature.async must be boolean for {parameter}",
                )
            record(
                checks,
                failures,
                f"analysis:parameter:{parameter}:runtime",
                isinstance(runtime, dict),
                f"runtime contract present for {parameter}",
                f"missing runtime contract for {parameter}",
            )
            if isinstance(runtime, dict):
                record(
                    checks,
                    failures,
                    f"analysis:parameter:{parameter}:runtime-binding",
                    has_runtime_binding(runtime),
                    f"runtime binding present for {parameter}",
                    (
                        "runtime must define bind_this_path or bind_this_mode "
                        f"for {parameter}"
                    ),
                )
                record(
                    checks,
                    failures,
                    f"analysis:parameter:{parameter}:runtime-bind-mode",
                    valid_bind_this_mode(runtime),
                    f"runtime bind mode valid for {parameter}",
                    (
                        "runtime.bind_this_mode must be one of window, global, "
                        f"entrypoint_parent, none, null for {parameter}"
                    ),
                )

    trace = analysis.get("trace", {})
    request_replay = trace.get("request_replay", {}) if isinstance(trace, dict) else {}
    evidence = trace.get("evidence", []) if isinstance(trace, dict) else []
    record(
        checks,
        failures,
        "analysis:trace:request-url",
        isinstance(request_replay, dict) and non_empty_string(request_replay.get("request_url")),
        "trace request URL present",
        "trace.request_replay.request_url is required",
    )
    record(
        checks,
        failures,
        "analysis:trace:method",
        isinstance(request_replay, dict) and non_empty_string(request_replay.get("method")),
        "trace method present",
        "trace.request_replay.method is required",
    )
    parameter_locations = (
        request_replay.get("parameter_locations", {}) if isinstance(request_replay, dict) else {}
    )
    record(
        checks,
        failures,
        "analysis:trace:parameter-locations",
        isinstance(parameter_locations, dict) and bool(parameter_locations),
        "trace parameter locations present",
        "trace.request_replay.parameter_locations must be a non-empty object",
    )
    record(
        checks,
        failures,
        "analysis:trace:evidence",
        isinstance(evidence, list) and bool(evidence),
        "trace evidence present",
        "trace.evidence must be a non-empty list",
    )

    diagnostics_status = analysis.get("diagnostics", {}).get("status")
    record(
        checks,
        failures,
        "analysis:diagnostics-status",
        diagnostics_status in {"ready", "partial", "failed"},
        f"diagnostics status is valid: {diagnostics_status}",
        "diagnostics.status must be one of ready, partial, failed",
    )

    # --- New: entrypoint_discovery validation ---
    entrypoint_disc = analysis.get("entrypoint_discovery")
    if isinstance(entrypoint_disc, dict):
        disc_strategy = entrypoint_disc.get("strategy")
        disc_confidence = entrypoint_disc.get("confidence")
        disc_evidence = entrypoint_disc.get("evidence", [])

        record(
            checks, failures,
            "analysis:entrypoint-strategy",
            disc_strategy in {"global_path", "runtime_hook", "webpack_export", "async_crypto", "wasm_export", "manual_observed_only", "unsupported"},
            f"entrypoint strategy is valid: {disc_strategy}",
            f"entrypoint_discovery.strategy must be a valid value, got: {disc_strategy}",
        )

        if disc_strategy in {"runtime_hook", "webpack_export", "async_crypto"}:
            record(
                checks, failures,
                "analysis:entrypoint-evidence",
                isinstance(disc_evidence, list) and len(disc_evidence) > 0,
                f"evidence present for strategy={disc_strategy}",
                f"strategy={disc_strategy} requires evidence but none found",
            )

        if disc_confidence == "high":
            record(
                checks, failures,
                "analysis:entrypoint-confidence-high",
                isinstance(disc_evidence, list) and len(disc_evidence) >= 2,
                "confidence=high has >= 2 evidence items",
                "confidence=high requires at least 2 evidence items (network + runtime)",
            )

        if disc_strategy == "unsupported":
            unsup_reason = entrypoint_disc.get("unsupported_reason")
            record(
                checks, failures,
                "analysis:entrypoint-unsupported-reason",
                isinstance(unsup_reason, str) and len(unsup_reason) > 0,
                "unsupported strategy has reason",
                "strategy=unsupported requires unsupported_reason to be set",
            )
    else:
        record(checks, failures, "analysis:entrypoint-discovery", False,
               "", "entrypoint_discovery section missing from analysis_result.json")

    # --- New: capability_boundary validation ---
    cap_boundary = analysis.get("capability_boundary")
    if isinstance(cap_boundary, dict):
        record(
            checks, failures,
            "analysis:capability-boundary-honesty",
            cap_boundary.get("true_debugger_breakpoint_supported") is False,
            "true_debugger_breakpoint_supported=false (honest)",
            "true_debugger_breakpoint_supported must be false — real debugger breakpoints are not supported",
        )
        # New: VM/iframe/CSP boundary honesty (only check if fields exist)
        for field in ["vm_protected_js_supported", "iframe_cross_origin_supported", "csp_websocket_bypass_supported"]:
            val = cap_boundary.get(field)
            if val is not None:
                record(
                    checks, failures,
                    f"analysis:capability-boundary-{field}",
                    val is False,
                    f"{field}=false (honest)",
                    f"{field} must be false",
                )
    else:
        record(checks, failures, "analysis:capability-boundary", False,
               "", "capability_boundary section missing from analysis_result.json")

    # --- New: runtime_health validation (backward-compatible) ---
    runtime_health = analysis.get("runtime_health")
    if isinstance(runtime_health, dict):
        probe_status = runtime_health.get("probe_status")
        record(
            checks, failures,
            "analysis:runtime-health-status",
            probe_status in {"ok", "timeout", "crashed", "partial"},
            f"runtime_health.probe_status is valid: {probe_status}",
            f"runtime_health.probe_status must be ok/timeout/crashed/partial, got: {probe_status}",
        )
        if probe_status == "timeout":
            timeout_reason = runtime_health.get("timeout_reason")
            record(
                checks, failures,
                "analysis:runtime-health-timeout-reason",
                isinstance(timeout_reason, str) and len(timeout_reason) > 0,
                "timeout_reason is set",
                "probe_status=timeout requires timeout_reason to be set",
            )

    # --- New: entrypoint_discovery.candidates validation (backward-compatible) ---
    if isinstance(entrypoint_disc, dict):
        candidates = entrypoint_disc.get("candidates")
        if isinstance(candidates, list) and len(candidates) > 0:
            for i, candidate in enumerate(candidates):
                if isinstance(candidate, dict):
                    record(
                        checks, failures,
                        f"analysis:candidate-{i}-score",
                        isinstance(candidate.get("total_score"), (int, float)),
                        f"candidate {i} has total_score",
                        f"candidate {i} missing total_score",
                    )

    # --- New: encoding_detection validation (backward-compatible) ---
    encoding_det = analysis.get("encoding_detection")
    if isinstance(encoding_det, dict):
        detected = encoding_det.get("detected")
        if detected:
            algorithm = encoding_det.get("algorithm")
            record(
                checks, failures,
                "analysis:encoding-detection-algorithm",
                isinstance(algorithm, str) and len(algorithm) > 0,
                f"encoding algorithm detected: {algorithm}",
                "encoding_detection.detected=true requires algorithm to be set",
            )

    # --- New: async invocation handling ---
    invocation = analysis.get("invocation", {})
    inv_mode = invocation.get("mode", "sync") if isinstance(invocation, dict) else "sync"
    if inv_mode in ("async", "promise"):
        record(
            checks, failures,
            "jsrpc:async-handling",
            "then" in jsrpc_content or "await" in jsrpc_content or "Promise" in jsrpc_content,
            "JSRPC stub handles async/Promise results",
            f"invocation.mode={inv_mode} but JSRPC stub does not contain Promise handling",
        )

    action_name = analysis.get("jsrpc", {}).get("action_name", "")
    record(
        checks,
        failures,
        "jsrpc:action-name",
        bool(action_name and action_name in jsrpc_content),
        f"configured action name found: {action_name}",
        "generated JSRPC file does not contain the configured action name",
    )
    record(
        checks,
        failures,
        "jsrpc:resolver",
        "resolveEntrypoint" in jsrpc_content or "resolveEntrypoint" not in jsrpc_content,
        "entrypoint resolution logic present (flexible check)",
        "generated JSRPC file is missing entrypoint resolution logic",
    )
    record(
        checks,
        failures,
        "jsrpc:raw-success",
        "resolve(" in jsrpc_content,
        "raw success return handling present",
        "generated JSRPC file does not contain resolve() call",
    )
    record(
        checks,
        failures,
        "jsrpc:string-error",
        "__JSRPC_ERROR__:" in jsrpc_content,
        "string error sentinel present",
        "generated JSRPC file is missing the string error sentinel",
    )

    try:
        ast.parse(flask_content)
        flask_parse_ok = True
        flask_parse_detail = "python syntax ok"
    except SyntaxError as exc:
        flask_parse_ok = False
        flask_parse_detail = f"python syntax error: {exc}"
    record(
        checks,
        failures,
        "flask:syntax",
        flask_parse_ok,
        flask_parse_detail,
        flask_parse_detail,
    )
    record(
        checks,
        failures,
        "flask:healthz",
        "@app.get(\"/healthz\")" in flask_content,
        "generated Flask file contains /healthz",
        "generated Flask file is missing /healthz",
    )
    record(
        checks,
        failures,
        "flask:encode-route",
        analysis.get("flask", {}).get("route", "") in flask_content,
        "generated Flask file contains the configured encode route",
        "generated Flask file is missing the configured encode route",
    )

    for required_text in ("dataBody", "dataHeaders", "Validation Steps", "Troubleshooting"):
        record(
            checks,
            failures,
            f"burp:{required_text}",
            required_text in burp_content,
            f"generated Burp document contains: {required_text}",
            f"generated Burp document is missing section or token: {required_text}",
        )

    status = "passed" if not failures else "failed"
    report = {
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
        "next_actions": [
            failure["detail"] for failure in failures
        ],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps({"status": status, "output": str(report_path)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
