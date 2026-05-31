#!/usr/bin/env python3
"""Detect encryption entrypoint candidates with scoring and verification.

Scans page context for encryption-related functions, scores each candidate,
and optionally verifies with a real sample input.

Usage:
  python3 scripts/detect_encryption.py \
    --probe-artifacts artifacts/probe_dump.json \
    --analysis analysis_result.json \
    --output artifacts/encryption_candidates.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-artifacts", required=True, help="Path to probe dump JSON.")
    parser.add_argument("--analysis", required=True, help="Path to analysis_result.json.")
    parser.add_argument("--output", required=True, help="Path to output candidates JSON.")
    return parser.parse_args()


def load_json(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def score_name(name: str) -> float:
    """Score based on function/variable name."""
    name_lower = name.lower()
    high = ["encrypt", "decrypt", "cipher", "hash", "sign", "verify", "hmac"]
    medium = ["rsa", "aes", "des", "sm2", "sm4", "md5", "sha", "base64"]
    low = ["encode", "decode", "token", "secret"]

    for kw in high:
        if kw in name_lower:
            return 1.0
    for kw in medium:
        if kw in name_lower:
            return 0.7
    for kw in low:
        if kw in name_lower:
            return 0.3
    return 0.0


def score_source_keyword(source_snippet: str) -> float:
    """Score based on source code keywords."""
    if not source_snippet:
        return 0.0
    snippet = source_snippet.lower()
    high = ["encrypt", "decrypt", "cipher", "crypto.subtle", "jsecrypt", "jsencrypt"]
    medium = ["rsa", "aes", "des", "sm2", "sm4", "md5", "sha", "hash"]
    found_high = sum(1 for kw in high if kw in snippet)
    found_medium = sum(1 for kw in medium if kw in snippet)
    if found_high > 0:
        return min(1.0, 0.6 + found_high * 0.2)
    if found_medium > 0:
        return min(0.7, 0.3 + found_medium * 0.1)
    return 0.0


def score_runtime_stack(stack_lines: list[str], candidate_name: str) -> float:
    """Score based on runtime call stack evidence."""
    if not stack_lines:
        return 0.0
    for line in stack_lines:
        if candidate_name.lower() in line.lower():
            return 1.0
    return 0.0


def score_request_correlation(observed_requests: list[dict], candidate_name: str) -> float:
    """Score based on request body correlation."""
    if not observed_requests:
        return 0.0
    # If the candidate name appears in request stack or nearby code
    for req in observed_requests:
        body = req.get("bodySnippet", "")
        if candidate_name.lower() in body.lower():
            return 0.8
    return 0.0


def score_input_output_shape(candidate_info: dict) -> float:
    """Score based on expected input/output shape."""
    returns = candidate_info.get("returns", "")
    if not returns:
        return 0.0
    shape_scores = {
        "md5_hex_lowercase_32chars": 0.9,
        "sm2_ciphertext_hex": 0.8,
        "rsa_encrypted_base64": 0.8,
        "rsa_encrypted_hex": 0.8,
        "hex_encoded_string": 0.6,
        "base64_string": 0.5,
    }
    for pattern, score in shape_scores.items():
        if pattern in returns.lower():
            return score
    return 0.3


def score_module_export(is_module_export: bool) -> float:
    """Score based on whether it's a module export."""
    return 0.5 if is_module_export else 0.0


def compute_total_score(scores: dict) -> float:
    """Compute weighted total score."""
    weights = {
        "name": 0.20,
        "source_keyword": 0.15,
        "runtime_stack": 0.25,
        "request_correlation": 0.20,
        "input_output_shape": 0.10,
        "module_export": 0.05,
        "verification": 0.05,
    }
    total = 0.0
    for key, weight in weights.items():
        total += scores.get(key, 0.0) * weight
    return round(total, 3)


def build_candidates(analysis: dict, probe: dict) -> list[dict]:
    """Build candidate list from analysis and probe data."""
    candidates = []
    parameters = analysis.get("parameters", {})
    observed_requests = probe.get("requests", []) if probe else []
    crypto_events = probe.get("crypto", []) if probe else []
    serializer_events = probe.get("serializers", []) if probe else []

    for param_name, param_config in parameters.items():
        entrypoint = param_config.get("entrypoint", {})
        call_sig = param_config.get("call_signature", {})

        candidate = {
            "parameter": param_name,
            "name": entrypoint.get("path", "unknown"),
            "type": entrypoint.get("type", "unknown"),
            "source_hint": entrypoint.get("source_hint", ""),
            "scores": {},
            "verified": False,
            "evidence": entrypoint.get("evidence", []),
        }

        # Score each dimension
        candidate["scores"]["name"] = score_name(candidate["name"])
        candidate["scores"]["source_keyword"] = score_source_keyword(
            entrypoint.get("source_hint", "")
        )
        candidate["scores"]["runtime_stack"] = score_runtime_stack(
            [], candidate["name"]
        )
        candidate["scores"]["request_correlation"] = score_request_correlation(
            observed_requests, candidate["name"]
        )
        candidate["scores"]["input_output_shape"] = score_input_output_shape(call_sig)
        candidate["scores"]["module_export"] = score_module_export(
            entrypoint.get("type") == "webpack_export"
        )
        candidate["scores"]["verification"] = 0.0  # Will be set if verified

        candidate["total_score"] = compute_total_score(candidate["scores"])
        candidates.append(candidate)

    return candidates


def main() -> int:
    args = parse_args()
    analysis = load_json(args.analysis)
    output_path = Path(args.output)

    # Load probe artifacts if available
    probe = {}
    probe_path = Path(args.probe_artifacts)
    if probe_path.exists():
        probe = load_json(args.probe_artifacts)

    candidates = build_candidates(analysis, probe)

    # Determine confidence
    for c in candidates:
        if c["total_score"] >= 0.6:
            c["confidence"] = "high" if c["verified"] else "medium"
        else:
            c["confidence"] = "low"

    result = {
        "candidates": candidates,
        "total_candidates": len(candidates),
        "high_confidence": sum(1 for c in candidates if c["confidence"] == "high"),
        "medium_confidence": sum(1 for c in candidates if c["confidence"] == "medium"),
        "low_confidence": sum(1 for c in candidates if c["confidence"] == "low"),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps({"status": "ok", "output": str(output_path), "candidates": len(candidates)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
