import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSRA = ROOT / "js-reverse-automation"


class AdversarialToolTests(unittest.TestCase):
    def test_v22_probe_contract_preserves_composition_and_safe_raw(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            adversarial = folder / "adversarial.js"
            runtime = folder / "runtime.js"
            for script, output in (
                ("emit_adversarial_runtime_probe.py", adversarial),
                ("emit_runtime_hook_probe.py", runtime),
            ):
                result = subprocess.run(
                    [sys.executable, str(JSRA / "scripts" / script), "--output", str(output), "--capture-raw"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                checked = subprocess.run(["node", "--check", str(output)], capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                content = output.read_text(encoding="utf-8")
                self.assertIn('const VERSION = "2.2.0"', content)
                self.assertIn("function getHookRegistry", content)
                self.assertIn("__JSRA_HOOK_REGISTRY__", content)
            self.assertIn("function safeClone", runtime.read_text(encoding="utf-8"))

    def test_probe_emits_valid_javascript(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "probe.js"
            command = [
                sys.executable,
                str(JSRA / "scripts/emit_adversarial_runtime_probe.py"),
                "--output",
                str(output),
                "--mode",
                "observe",
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            checked = subprocess.run(["node", "--check", str(output)], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_integrity_sampling_is_bounded_and_configurable(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "adversarial.js"
            result = subprocess.run(
                [
                    sys.executable,
                    str(JSRA / "scripts" / "emit_adversarial_runtime_probe.py"),
                    "--output", str(output),
                    "--integrity-event-budget", "32",
                    "--integrity-sample-every", "8",
                    "--integrity-burst", "4",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = output.read_text(encoding="utf-8")
            self.assertIn('integrityEventBudget": 32', content)
            self.assertIn("sampleEvery", content)
            self.assertIn("suppressedByPath", content)

    def test_flatten_events_accepts_adversarial_state(self):
        sys.path.insert(0, str(JSRA / "scripts"))
        from common import flatten_events

        self.assertEqual(
            [event["event_id"] for event in flatten_events({
                "events": [{"event_id": "top", "type": "x"}],
                "state": {"events": [{"event_id": "adv", "type": "integrity.x"}]},
            })],
            ["top", "adv"],
        )

    def test_graph_correlates_crypto_to_request_across_trace_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            probe = folder / "probe.json"
            output = folder / "graph.json"
            value = "sha256:" + "a" * 64
            probe.write_text(json.dumps({"events": [
                {"event_id": "crypto", "trace_id": "t1", "type": "crypto.cryptojs",
                 "output_fingerprint": value, "timestamp": 1},
                {"event_id": "field", "trace_id": "t2", "type": "network.field",
                 "input_fingerprint": value, "timestamp": 2},
            ]}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(JSRA / "scripts" / "build_evidence_graph.py"),
                 "--probe", str(probe), "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            graph = json.loads(output.read_text(encoding="utf-8"))
            flows = [edge for edge in graph["edges"] if edge["type"] == "fingerprint_flow"]
            self.assertEqual(len(flows), 1)
            self.assertFalse(flows[0]["same_trace"])

    def test_candidate_lookup_prefers_verified_artifact_in_standard_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            analysis = folder / "analysis_result.json"
            artifacts = folder / "artifacts"
            artifacts.mkdir()
            (artifacts / "encryption_candidates.json").write_text("{}", encoding="utf-8")
            verified = artifacts / "encryption_candidates.verified.json"
            verified.write_text("{}", encoding="utf-8")
            sys.path.insert(0, str(JSRA / "scripts"))
            from emit_jsrpc_stub import find_candidate_file

            self.assertEqual(find_candidate_file(analysis), verified)

    def test_jsrpc_stub_contains_network_delivery_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            analysis = folder / "analysis.json"
            candidates = folder / "candidates.json"
            output = folder / "jsrpc.js"
            analysis.write_text(json.dumps({
                "parameters": {
                    "password": {
                        "entrypoint": {"type": "global", "path": "sendDataAes"},
                        "runtime": {"bind_this_mode": "none"},
                        "capture": {"route": "encrypt/aes.php", "suppress_page_success": True},
                        "jsra_transform": {
                            "candidate_path": "sendDataAes",
                            "safe_to_invoke": True,
                            "arguments": [{"source": "constant", "value": "encrypt/aes.php"}],
                        },
                    }
                },
                "jsrpc": {"action_name": "jsra_challenge", "group": "jsra"},
            }), encoding="utf-8")
            candidates.write_text(json.dumps({"candidates": [{
                "path": "sendDataAes", "source": "runtime", "type": "function",
                "verified": True, "verification": [{"matched": True}],
            }]}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(JSRA / "scripts" / "emit_jsrpc_stub.py"),
                 "--analysis", str(analysis), "--candidates", str(candidates),
                 "--output", str(output)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = output.read_text(encoding="utf-8")
            self.assertIn("invokeWithNetworkCapture", content)
            self.assertIn("matchesRoute", content)
            self.assertIn("bindInputFields", content)
            self.assertIn("requestBody", content)
            self.assertIn("suppress_page_success", content)
            self.assertEqual(subprocess.run(["node", "--check", str(output)]).returncode, 0)

    def test_validator_rejects_quarantined_jsrpc_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            output = folder / "jsrpc_inject.js"
            output.write_text(
                'const EVIDENCE_ERRORS = {"password":"candidate is not verified"};',
                encoding="utf-8",
            )
            sys.path.insert(0, str(JSRA / "scripts"))
            from validate_artifacts import check_jsrpc_evidence_gate

            result = check_jsrpc_evidence_gate(output)
            self.assertFalse(result["ok"])
            self.assertIn("password", result["errors"][0])

    def test_source_instrumentor_rewrites_selected_reads_only(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "input.js"
            output = folder / "output.js"
            report = folder / "report.json"
            source.write_text(
                "const a = navigator.webdriver; const b = document.cookie; "
                "const c = document.getElementById(\"username\").value; "
                "const d = document['getElementById'](\"username\")['value']; "
                "const s = 'navigator.webdriver'; navigator.webdriver = false;\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "node",
                    str(JSRA / "scripts/source_instrumentor.js"),
                    "--input",
                    str(source),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--objects",
                    "navigator,document",
                    "--properties",
                    "webdriver,cookie,value",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["rewrite_count"], 4)
            content = output.read_text(encoding="utf-8")
            self.assertEqual(content.count("__JSRA_TAP_GET__"), 5)

    def test_adversarial_diff_is_inconclusive_without_new_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            baseline = folder / "baseline.json"
            patched = folder / "patched.json"
            output = folder / "diff.json"
            payload = {"state": {"events": []}}
            baseline.write_text(json.dumps(payload), encoding="utf-8")
            patched.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(JSRA / "scripts/adversarial_diff.py"),
                    "--baseline",
                    str(baseline),
                    "--patched",
                    str(patched),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["verdict"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
