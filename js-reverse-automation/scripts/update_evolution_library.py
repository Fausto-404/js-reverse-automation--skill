#!/usr/bin/env python3
"""Safely merge reverse-engineering experience into evolution_matrix.json."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "references" / "evolution_matrix.json"
LOCK_PATH = MATRIX_PATH.with_name(MATRIX_PATH.name + ".lock")
PHASE0_PATH = ROOT / "artifacts" / "phase0_input.json"
ANALYSIS_PATH = ROOT / "analysis_result.json"
VALIDATION_PATH = ROOT / "artifacts" / "validation_report.json"

PASS_STATUSES = {"pass", "passed", "ok", "success", "succeeded"}
FAIL_STATUSES = {"fail", "failed", "error", "validation failed"}
COMMON_SECOND_LEVEL_TLDS = {
    "ac",
    "co",
    "com",
    "edu",
    "gov",
    "net",
    "org",
}
PRIVATE_SUFFIXES = {
    "appspot.com",
    "azurewebsites.net",
    "cloudfront.net",
    "fly.dev",
    "github.io",
    "gitlab.io",
    "herokuapp.com",
    "netlify.app",
    "onrender.com",
    "pages.dev",
    "railway.app",
    "render.com",
    "vercel.app",
    "workers.dev",
}

FEATURE_SPECS = {
    "obfuscation_vmp_type_1": {
        "triggers": ["$super", "callee", "__vmp", " vmp", "vmprotect"],
        "fingerprint_keywords": ["$super", "callee", "__vmp"],
        "successful_patch_strategy": "硬编码路径会失效，必须使用 resolver 策略进行动态导出",
        "ste": {
            "strategic_principle": "硬编码路径会失效，必须使用 resolver 策略进行动态导出",
            "tactical_manual": [
                "先保留未 Patch 的网络请求、调用栈与参数落点证据。",
                "在页面代码、调用栈或 Hook 日志中匹配 $super、callee、__vmp 等指纹。",
                "放弃静态路径提取，改用 resolver 策略在运行时动态导出入口。",
                "回到 analysis_result.json 生成链路，并用 Phase 7/8 校验确认策略仍然有效。",
            ],
            "applicable_scenarios": ["obfuscation", "vmp", "dynamic-resolver", "entrypoint-export"],
        },
    },
    "dynamic_resolver_export": {
        "triggers": ["resolver", "resolver_path", "resolver_name", "dynamic alias"],
        "fingerprint_keywords": ["resolver", "resolver_path", "resolver_name"],
        "successful_patch_strategy": "使用 resolver 策略定位动态导出的运行时入口",
        "ste": {
            "strategic_principle": "入口路径不稳定时，优先沉淀 resolver 而不是沉淀静态对象路径。",
            "tactical_manual": [
                "从网络请求和运行时证据确认目标参数的真实生成点。",
                "识别可重复定位入口的 resolver 条件、对象锚点或模块导出点。",
                "在 JSRPC 注入代码中封装 resolver，并保留失败时的可诊断错误。",
                "用手工 JSRPC 链接和 Flask 代理校验 resolver 在真实页面上下文中可复用。",
            ],
            "applicable_scenarios": ["dynamic-resolver", "entrypoint-export", "obfuscation"],
        },
    },
    "antidebug_debugger_loop": {
        "triggers": ["debugger-loop", "debugger loop", "debugger"],
        "fingerprint_keywords": ["debugger"],
        "successful_patch_strategy": "导航前预注入最小 patch，隔离 debugger 阻断后再提取入口",
    },
    "antidebug_console_detect": {
        "triggers": ["console-detect", "console detect", "console."],
        "fingerprint_keywords": ["console"],
        "successful_patch_strategy": "保留原始发包证据，只对 console 检测点做最小观测 patch",
    },
    "antidebug_timer_check": {
        "triggers": ["timer-check", "timer check", "setinterval", "settimeout", "timing"],
        "fingerprint_keywords": ["setInterval", "setTimeout", "timing"],
        "successful_patch_strategy": "先验证时序检测是否影响发包，再最小化稳定计时差异",
    },
    "antidebug_env_detect": {
        "triggers": ["env-detect", "environment detect", "navigator.webdriver", "headless"],
        "fingerprint_keywords": ["navigator.webdriver", "headless"],
        "successful_patch_strategy": "基于真实浏览器现象验证环境检测，仅 patch 阻断观测的最小字段",
    },
    "antidebug_proxy_guard": {
        "triggers": ["proxy-guard", "proxy guard", "defineproperty", "proxy("],
        "fingerprint_keywords": ["Proxy", "defineProperty"],
        "successful_patch_strategy": "识别代理包装层后从稳定对象或 resolver 重新导出目标入口",
    },
    "antidebug_rule_triggered": {
        "triggers": ["references/antidebug/"],
        "fingerprint_keywords": ["references/antidebug/"],
        "successful_patch_strategy": "按命中的 antidebug 规则执行最小验证与最小 patch",
    },
}


def empty_matrix() -> dict:
    return {"domains": {}, "behavioral_features": {}}


def load_json_object(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


@contextmanager
def locked_matrix() -> object:
    MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def backup_corrupt_matrix(matrix_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = matrix_path.with_suffix(".bak")
    if backup_path.exists():
        backup_path = matrix_path.with_name(f"{matrix_path.stem}.{timestamp}.bak")
    shutil.copy2(matrix_path, backup_path)
    return backup_path


def load_matrix(matrix_path: Path) -> dict:
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    if not matrix_path.exists() or matrix_path.stat().st_size == 0:
        return empty_matrix()

    try:
        matrix_data = load_json_object(matrix_path)
    except json.JSONDecodeError:
        backup_corrupt_matrix(matrix_path)
        return empty_matrix()
    except ValueError:
        backup_corrupt_matrix(matrix_path)
        return empty_matrix()

    if not isinstance(matrix_data.get("domains"), dict):
        matrix_data["domains"] = {}
    if not isinstance(matrix_data.get("behavioral_features"), dict):
        matrix_data["behavioral_features"] = {}
    return matrix_data


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def registered_domain(hostname: str) -> str:
    host = hostname.lower().rstrip(".")
    if not host or host == "localhost":
        return host
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host) or ":" in host:
        return host

    labels = [label for label in host.split(".") if label]
    if len(labels) <= 2:
        return host

    for suffix in PRIVATE_SUFFIXES:
        if host == suffix:
            return host
        if host.endswith(f".{suffix}"):
            prefix = host[: -(len(suffix) + 1)]
            tenant = prefix.split(".")[-1]
            return f"{tenant}.{suffix}"

    if len(labels[-1]) == 2 and labels[-2] in COMMON_SECOND_LEVEL_TLDS and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def artifact_fingerprint(phase0: dict, analysis: dict, validation: dict) -> str:
    payload = {
        "target_url": phase0.get("target_url") or analysis.get("input", {}).get("target_url"),
        "parameters": phase0.get("parameters") or analysis.get("input", {}).get("parameters"),
        "jsrpc": analysis.get("jsrpc", {}),
        "flask": analysis.get("flask", {}),
        "parameters_contract": analysis.get("parameters", {}),
        "validation_status": validation.get("status"),
        "validation_failures": validation.get("failures", []),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def extract_domain(phase0: dict, analysis: dict) -> str:
    target_url = phase0.get("target_url") or analysis.get("input", {}).get("target_url")
    if not isinstance(target_url, str) or not target_url.strip():
        raise ValueError("target_url is missing from phase0_input.json and analysis_result.json")

    parsed = urlparse(target_url.strip())
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise ValueError(f"target_url has no hostname: {target_url}")
    return registered_domain(hostname)


def normalize_status(value: object) -> str:
    return str(value or "").strip().lower()


def validation_passed(validation: dict) -> bool:
    failures = validation.get("failures", [])
    has_failures = isinstance(failures, list) and bool(failures)
    status = normalize_status(validation.get("status"))

    if has_failures or status in FAIL_STATUSES:
        return False
    if status in PASS_STATUSES:
        return True
    raise ValueError("validation_report.status must explicitly indicate Pass or Fail")


def collect_text(*values: object) -> str:
    chunks: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            chunks.append(value)
            continue
        try:
            chunks.append(json.dumps(value, ensure_ascii=False, default=str))
        except TypeError:
            chunks.append(str(value))
    return "\n".join(chunks)


def has_resolver_entrypoint(analysis: dict) -> bool:
    parameters = analysis.get("parameters", {})
    if not isinstance(parameters, dict):
        return False

    for parameter_config in parameters.values():
        if not isinstance(parameter_config, dict):
            continue
        entrypoint = parameter_config.get("entrypoint", {})
        if not isinstance(entrypoint, dict):
            continue
        if entrypoint.get("type") == "resolver":
            return True
        if entrypoint.get("resolver_name") or entrypoint.get("resolver_path"):
            return True
    return False


def identify_behavioral_features(matrix_data: dict, evidence_text: str, analysis: dict) -> set[str]:
    matches: set[str] = set()
    lowered = evidence_text.lower()

    behavioral_features = matrix_data.get("behavioral_features", {})
    if isinstance(behavioral_features, dict):
        for key, feature in behavioral_features.items():
            if not isinstance(feature, dict):
                continue
            keywords = feature.get("fingerprint_keywords", [])
            if not isinstance(keywords, list):
                continue
            for keyword in keywords:
                keyword_text = str(keyword).strip().lower()
                if keyword_text and keyword_text in lowered:
                    matches.add(str(key))
                    break

    for key, spec in FEATURE_SPECS.items():
        triggers = spec.get("triggers", [])
        if any(trigger.lower() in lowered for trigger in triggers):
            matches.add(key)

    if has_resolver_entrypoint(analysis):
        matches.add("dynamic_resolver_export")

    return matches


def unique_list(values: object) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    if not isinstance(values, list):
        return result

    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def append_unique(values: list[str], item: str) -> list[str]:
    if item and item not in values:
        values.append(item)
    return values


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return value or "behavioral_feature"


def feature_spec_for(key: str) -> dict:
    if key in FEATURE_SPECS:
        return FEATURE_SPECS[key]
    return {
        "fingerprint_keywords": [key],
        "successful_patch_strategy": f"沿用历史特征 {key} 的成功 Patch 策略",
    }


def build_notes(phase0: dict, analysis: dict, validation: dict, passed: bool) -> str:
    notes: list[str] = []

    constraints = str(phase0.get("environment_constraints", "")).strip()
    if constraints and constraints.lower() != "none":
        notes.append(constraints)

    phase0_notes = phase0.get("notes", [])
    if isinstance(phase0_notes, list):
        notes.extend(str(item).strip() for item in phase0_notes if str(item).strip())
    elif isinstance(phase0_notes, str) and phase0_notes.strip():
        notes.append(phase0_notes.strip())

    diagnostics = analysis.get("diagnostics", {})
    if isinstance(diagnostics, dict):
        for key in ("warnings", "residual_risks"):
            values = diagnostics.get(key, [])
            if isinstance(values, list):
                notes.extend(str(item).strip() for item in values if str(item).strip())

    warnings = validation.get("warnings", [])
    if isinstance(warnings, list):
        notes.extend(str(item).strip() for item in warnings if str(item).strip())

    failures = validation.get("failures", [])
    if isinstance(failures, list):
        for failure in failures[:3]:
            if isinstance(failure, dict):
                detail = failure.get("detail") or failure.get("check")
                if detail:
                    notes.append(str(detail).strip())
            elif str(failure).strip():
                notes.append(str(failure).strip())

    if not notes:
        notes.append("Validation Passed" if passed else "Validation Failed")

    compact: list[str] = []
    seen: set[str] = set()
    for note in notes:
        cleaned = note.replace("\n", " ").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        compact.append(cleaned)
        if len(compact) >= 5:
            break
    return "；".join(compact)[:500]


def infer_scenarios(key: str, keywords: list[str], analysis: dict) -> list[str]:
    scenarios = [part for part in key.split("_") if part]
    if has_resolver_entrypoint(analysis):
        scenarios.append("dynamic-resolver")
    for keyword in keywords:
        token = slugify(keyword).replace("_", "-")
        if token and token not in scenarios:
            scenarios.append(token)
    return scenarios[:8]


def build_ste(feature_key: str, feature: dict, spec: dict, analysis: dict, passed: bool) -> dict:
    existing_ste = feature.get("ste") if isinstance(feature.get("ste"), dict) else {}
    spec_ste = spec.get("ste") if isinstance(spec.get("ste"), dict) else {}
    strategy = feature.get("successful_patch_strategy") or spec.get("successful_patch_strategy", "")
    keywords = unique_list(feature.get("fingerprint_keywords", []))

    strategic_principle = (
        existing_ste.get("strategic_principle")
        or spec_ste.get("strategic_principle")
        or strategy
        or "优先基于网络请求、运行时证据和校验结果沉淀可复用策略。"
    )
    if not passed and feature.get("failed_attempts"):
        strategic_principle = "历史策略失效时必须停止继承，回到网络请求与运行时证据重新探索。"
        return {
            "strategic_principle": strategic_principle,
            "tactical_manual": [
                "立即停止继承本次失败的 successful_patch_strategy。",
                "清除当前域名的 action/route 常规绑定，重新从 Phase 1 锁定请求。",
                "重新采集源码位置、调用栈和 Hook 日志，生成新的探索分支。",
                "只有 Phase 7/8 重新通过后，才写回新的 successful_patch_strategy。",
            ],
            "applicable_scenarios": infer_scenarios(feature_key, keywords, analysis),
        }

    tactical_manual = unique_list(existing_ste.get("tactical_manual"))
    for step in unique_list(spec_ste.get("tactical_manual")):
        append_unique(tactical_manual, step)
    if not tactical_manual:
        keyword_summary = "、".join(keywords[:5]) if keywords else feature_key
        tactical_manual = [
            "先保留未 Patch 的网络请求、调用栈与参数落点证据。",
            f"在页面代码、调用栈或 Hook 日志中匹配特征指纹：{keyword_summary}。",
            f"执行策略：{strategy or '基于运行时证据重新探索入口'}。",
            "回到 analysis_result.json 生成链路，并用 Phase 7/8 校验确认策略仍然有效。",
        ]

    applicable_scenarios = unique_list(existing_ste.get("applicable_scenarios"))
    for scenario in unique_list(spec_ste.get("applicable_scenarios")):
        append_unique(applicable_scenarios, scenario)
    for scenario in infer_scenarios(feature_key, keywords, analysis):
        append_unique(applicable_scenarios, scenario)

    return {
        "strategic_principle": strategic_principle,
        "tactical_manual": tactical_manual[:8],
        "applicable_scenarios": applicable_scenarios[:12],
    }


def update_domain_memory(
    matrix_data: dict,
    domain: str,
    analysis: dict,
    feature_keys: set[str],
    fingerprint: str,
    notes: str,
    updated_at: str,
    passed: bool,
) -> dict:
    domains = matrix_data["domains"]
    existing = domains.get(domain)
    if not isinstance(existing, dict):
        existing = {}

    failed_binding = {
        "last_action_name": existing.get("last_action_name"),
        "route": existing.get("route"),
        "last_behavioral_features": unique_list(existing.get("last_behavioral_features", [])),
        "duplicate_success": passed and existing.get("last_validation_fingerprint") == fingerprint,
    }

    if passed:
        action_name = analysis.get("jsrpc", {}).get("action_name")
        route = analysis.get("flask", {}).get("route")
        if isinstance(action_name, str) and action_name:
            existing["last_action_name"] = action_name
        if isinstance(route, str) and route:
            existing["route"] = route
        existing["last_behavioral_features"] = sorted(feature_keys)
        existing["last_validation_fingerprint"] = fingerprint
        existing["updated_at"] = updated_at
        existing["notes"] = notes
        domains[domain] = existing
        return failed_binding

    if domain in domains:
        existing.pop("last_action_name", None)
        existing.pop("route", None)
        existing["last_validation_fingerprint"] = fingerprint
        existing["updated_at"] = updated_at
        existing["notes"] = f"{notes}；Validation Failed，已清除历史 action/route 绑定"
        domains[domain] = existing
        return failed_binding

    return {}


def update_behavioral_memory(
    matrix_data: dict,
    feature_keys: set[str],
    updated_at: str,
    passed: bool,
    failed_binding: dict,
    analysis: dict,
) -> None:
    behavioral_features = matrix_data["behavioral_features"]

    for raw_key in sorted(feature_keys):
        key = raw_key if raw_key in behavioral_features else slugify(raw_key)
        spec = feature_spec_for(raw_key)
        feature = behavioral_features.get(key)
        if not isinstance(feature, dict):
            feature = {}

        keywords = unique_list(feature.get("fingerprint_keywords", []))
        for keyword in spec.get("fingerprint_keywords", []):
            append_unique(keywords, str(keyword))
        feature["fingerprint_keywords"] = keywords

        strategy = feature.get("successful_patch_strategy")
        if not isinstance(strategy, str) or not strategy.strip():
            strategy = str(spec.get("successful_patch_strategy", "")).strip()

        count_success = not failed_binding.get("duplicate_success")

        if passed:
            if strategy:
                feature["successful_patch_strategy"] = strategy
            if count_success:
                success_count = feature.get("success_count", 0)
                if not isinstance(success_count, int):
                    success_count = 0
                feature["success_count"] = success_count + 1
        else:
            failed_attempts = unique_list(feature.get("failed_attempts", []))
            if strategy:
                append_unique(failed_attempts, strategy)
            failed_action = failed_binding.get("last_action_name")
            if failed_action:
                append_unique(failed_attempts, f"历史 Action 失效: {failed_action}")
            feature["failed_attempts"] = failed_attempts
            if strategy and feature.get("successful_patch_strategy") == strategy:
                feature.pop("successful_patch_strategy", None)

        feature["ste"] = build_ste(key, feature, spec, analysis, passed)
        feature["updated_at"] = updated_at
        behavioral_features[key] = feature


def update_matrix() -> None:
    phase0 = load_json_object(PHASE0_PATH)
    analysis = load_json_object(ANALYSIS_PATH)
    validation = load_json_object(VALIDATION_PATH)

    domain = extract_domain(phase0, analysis)
    passed = validation_passed(validation)
    fingerprint = artifact_fingerprint(phase0, analysis, validation)
    updated_at = current_date()
    notes = build_notes(phase0, analysis, validation, passed)
    evidence_text = collect_text(
        phase0,
        analysis.get("trace", {}),
        analysis.get("parameters", {}),
        analysis.get("diagnostics", {}),
        validation,
    )

    with locked_matrix():
        matrix_data = load_matrix(MATRIX_PATH)
        feature_keys = identify_behavioral_features(matrix_data, evidence_text, analysis)
        failed_binding = update_domain_memory(
            matrix_data=matrix_data,
            domain=domain,
            analysis=analysis,
            feature_keys=feature_keys,
            fingerprint=fingerprint,
            notes=notes,
            updated_at=updated_at,
            passed=passed,
        )
        if not passed:
            feature_keys.update(failed_binding.get("last_behavioral_features", []))
        update_behavioral_memory(
            matrix_data=matrix_data,
            feature_keys=feature_keys,
            updated_at=updated_at,
            passed=passed,
            failed_binding=failed_binding,
            analysis=analysis,
        )
        atomic_write_json(MATRIX_PATH, matrix_data)

    print("Evolution matrix updated successfully and safely.")


def main() -> int:
    try:
        update_matrix()
    except Exception as exc:
        print(f"Evolution matrix update failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
