import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import (  # noqa: E402
    CAPABILITIES,
    compare_traces,
    demo_traces,
    dispatch_request,
    render_markdown,
    validate_trace,
)


class FlowDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline, self.candidate = demo_traces()

    def test_demo_report_surfaces_candidate_gaps(self) -> None:
        report = compare_traces(self.baseline, self.candidate)

        self.assertEqual(report["overall"], "gaps_found")
        self.assertEqual(report["score"]["tested_capabilities"], 8)
        self.assertEqual(report["score"]["gap_count"], 4)
        self.assertEqual(
            {gap["capability"] for gap in report["gaps"]},
            {"settings", "history", "recovery", "multi_display"},
        )

    def test_normalization_is_ordered_and_bounded(self) -> None:
        reversed_trace = dict(self.candidate)
        reversed_trace["events"] = list(reversed(self.candidate["events"]))

        normalized = validate_trace(reversed_trace)

        self.assertEqual(
            [event["capability"] for event in normalized["events"]],
            list(CAPABILITIES),
        )
        self.assertEqual(set(normalized), {"schema_version", "app", "run_id", "events"})

    def test_private_fields_are_rejected(self) -> None:
        unsafe = dict(self.candidate)
        unsafe["body"] = "never accept this"

        with self.assertRaisesRegex(ValueError, "private field"):
            validate_trace(unsafe)

    def test_path_like_labels_are_rejected(self) -> None:
        unsafe = dict(self.candidate)
        unsafe["app"] = "demo/private-app"

        with self.assertRaisesRegex(ValueError, "short label"):
            validate_trace(unsafe)

    def test_duplicate_capabilities_are_rejected(self) -> None:
        unsafe = dict(self.candidate)
        unsafe["events"] = list(self.candidate["events"])
        unsafe["events"][-1] = dict(unsafe["events"][0])

        with self.assertRaisesRegex(ValueError, "each capability exactly once"):
            validate_trace(unsafe)

    def test_unverified_events_cannot_claim_timing(self) -> None:
        unsafe = dict(self.candidate)
        unsafe["events"] = [dict(event) for event in self.candidate["events"]]
        unsafe["events"][0]["status"] = "unknown"

        with self.assertRaisesRegex(ValueError, "cannot include a duration"):
            validate_trace(unsafe)

    def test_markdown_is_shareable_without_local_data(self) -> None:
        markdown = render_markdown(compare_traces(self.baseline, self.candidate))

        self.assertIn("# FlowDiff report", markdown)
        self.assertIn("## Capability matrix", markdown)
        self.assertIn("## Privacy contract", markdown)
        self.assertIn("personal identifiers", markdown)
        self.assertNotIn("private-app", markdown)
        self.assertNotIn("http://", markdown)
        self.assertNotIn("https://", markdown)

    def test_mcp_exposes_only_the_two_expected_tools(self) -> None:
        response = dispatch_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )

        self.assertIsNotNone(response)
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertEqual(
            names,
            {"validate_dictation_trace", "compare_dictation_traces"},
        )

    def test_mcp_compare_returns_json_text(self) -> None:
        response = dispatch_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "compare_dictation_traces",
                    "arguments": {
                        "baseline": self.baseline,
                        "candidate": self.candidate,
                    },
                },
            }
        )

        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["apps"]["candidate"], "Candidate")
        self.assertEqual(payload["overall"], "gaps_found")

    def test_mcp_private_field_failure_is_safe(self) -> None:
        unsafe = dict(self.candidate)
        unsafe["transcript"] = "redacted"
        response = dispatch_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "validate_dictation_trace",
                    "arguments": {"trace": unsafe},
                },
            }
        )

        self.assertTrue(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["error_code"], "private_field_rejected")
        self.assertNotIn("redacted", response["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
