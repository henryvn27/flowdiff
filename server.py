#!/usr/bin/env python3
"""A privacy-safe parity report for dictation UX traces.

FlowDiff deliberately accepts a tiny, redacted event contract instead of
recordings, screenshots, transcripts, URLs, or local paths. It stores nothing,
uses no network, and exposes two deterministic MCP tools:

* validate_dictation_trace
* compare_dictation_traces
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from typing import Any


SERVER_NAME = "flowdiff"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"
SCHEMA_VERSION = "1"

CAPABILITY_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("activation", "Activation"),
    ("recording_feedback", "Recording feedback"),
    ("insertion", "Insertion"),
    ("settings", "Settings"),
    ("history", "History"),
    ("privacy", "Privacy"),
    ("recovery", "Recovery"),
    ("multi_display", "Multi-display"),
)
CAPABILITIES = tuple(name for name, _ in CAPABILITY_DEFINITIONS)
CAPABILITY_LABELS = dict(CAPABILITY_DEFINITIONS)

ALLOWED_STATUSES = frozenset({"pass", "partial", "fail", "skipped", "unknown"})
STATUS_WEIGHT = {
    "pass": 1.0,
    "partial": 0.5,
    "fail": 0.0,
    "skipped": None,
    "unknown": None,
}
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}$")
SAFE_CODE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,39}$")

EVIDENCE_CODES: dict[str, frozenset[str]] = {
    "activation": frozenset(
        {"shortcut_fired", "bar_opened", "permission_prompt", "activation_blocked"}
    ),
    "recording_feedback": frozenset(
        {"recording_indicator", "timer_visible", "waveform_visible", "feedback_missing"}
    ),
    "insertion": frozenset(
        {"target_focused", "text_inserted", "insertion_blocked", "paste_confirmed"}
    ),
    "settings": frozenset(
        {"settings_opened", "shortcut_configured", "settings_missing", "setting_persisted"}
    ),
    "history": frozenset(
        {"history_visible", "history_empty", "history_unavailable", "history_searchable"}
    ),
    "privacy": frozenset(
        {"local_only_copy", "retention_visible", "privacy_unknown", "export_disabled"}
    ),
    "recovery": frozenset(
        {"restart_recovered", "error_recovered", "stuck_state", "recovery_missing"}
    ),
    "multi_display": frozenset(
        {"display_switch_ok", "display_switch_lag", "display_not_tested", "bar_repositioned"}
    ),
}

CAPABILITY_GAP_HINTS = {
    "activation": "The candidate activation path is not fully proven.",
    "recording_feedback": "The candidate does not provide a complete recording feedback signal.",
    "insertion": "The candidate insertion path needs another check.",
    "settings": "The candidate settings flow is incomplete or unverified.",
    "history": "The candidate history flow is incomplete or unverified.",
    "privacy": "The candidate privacy evidence is incomplete or unverified.",
    "recovery": "The candidate recovery path needs another check.",
    "multi_display": "The candidate multi-display behavior is incomplete or unverified.",
}

FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "body",
        "clipboard",
        "content",
        "email",
        "handle",
        "image",
        "identifier",
        "message",
        "path",
        "password",
        "raw",
        "screenshot",
        "secret",
        "text",
        "token",
        "transcript",
        "url",
    }
)


class FlowDiffError(ValueError):
    """A safe, user-facing validation or dispatch failure."""

    def __init__(self, code: str, public_message: str):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FlowDiffError("invalid_object", f"{context} must be an object.")
    if any(not isinstance(key, str) for key in value):
        raise FlowDiffError("invalid_keys", f"{context} keys must be strings.")
    return value


def _check_keys(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    unknown = set(value) - expected
    for key in unknown:
        if key.casefold() in FORBIDDEN_FIELD_NAMES:
            raise FlowDiffError(
                "private_field_rejected",
                f"{context} contains a private field that FlowDiff will not accept.",
            )
    if unknown:
        raise FlowDiffError(
            "unknown_field",
            f"{context} contains an unsupported field.",
        )


def _safe_label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SAFE_LABEL.fullmatch(value.strip()):
        raise FlowDiffError(
            "invalid_label",
            f"{field} must be a short label without paths, URLs, or identifiers.",
        )
    return value.strip()


def _safe_code(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SAFE_CODE.fullmatch(value):
        raise FlowDiffError(
            "invalid_evidence_code",
            f"{field} must be a short lowercase evidence code.",
        )
    return value


def _safe_duration(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 600_000:
        raise FlowDiffError(
            "invalid_duration",
            f"{field} must be an integer from 0 to 600000, or null.",
        )
    return value


def _validate_event(event: Any, index: int) -> dict[str, Any]:
    item = _require_mapping(event, f"events[{index}]")
    _check_keys(
        item,
        {"capability", "status", "duration_ms", "evidence_codes"},
        f"events[{index}]",
    )

    capability = item.get("capability")
    if capability not in CAPABILITIES:
        raise FlowDiffError(
            "invalid_capability",
            f"events[{index}].capability is not supported.",
        )

    status = item.get("status")
    if status not in ALLOWED_STATUSES:
        raise FlowDiffError(
            "invalid_status",
            f"events[{index}].status is not supported.",
        )

    duration_ms = _safe_duration(item.get("duration_ms"), f"events[{index}].duration_ms")
    evidence_codes = item.get("evidence_codes")
    if not isinstance(evidence_codes, list) or len(evidence_codes) > 8:
        raise FlowDiffError(
            "invalid_evidence_codes",
            f"events[{index}].evidence_codes must be a list of at most 8 codes.",
        )

    normalized_codes: list[str] = []
    for code_index, code in enumerate(evidence_codes):
        normalized = _safe_code(code, f"events[{index}].evidence_codes[{code_index}]")
        if normalized not in EVIDENCE_CODES[capability]:
            raise FlowDiffError(
                "evidence_capability_mismatch",
                f"events[{index}] contains an evidence code for another capability.",
            )
        if normalized not in normalized_codes:
            normalized_codes.append(normalized)

    if status in {"skipped", "unknown"} and duration_ms is not None:
        raise FlowDiffError(
            "unverified_duration",
            f"events[{index}] cannot include a duration when status is {status}.",
        )

    return {
        "capability": capability,
        "status": status,
        "duration_ms": duration_ms,
        "evidence_codes": sorted(normalized_codes),
    }


def validate_trace(trace: Any) -> dict[str, Any]:
    """Validate and normalize a redacted trace without retaining extra fields."""

    item = _require_mapping(trace, "trace")
    _check_keys(item, {"schema_version", "app", "run_id", "events"}, "trace")

    if item.get("schema_version") != SCHEMA_VERSION:
        raise FlowDiffError(
            "unsupported_schema",
            f"trace.schema_version must be {SCHEMA_VERSION}.",
        )
    app = _safe_label(item.get("app"), "trace.app")
    run_id = _safe_label(item.get("run_id"), "trace.run_id")

    events = item.get("events")
    if not isinstance(events, list) or len(events) != len(CAPABILITIES):
        raise FlowDiffError(
            "incomplete_trace",
            f"trace.events must contain exactly {len(CAPABILITIES)} capability events.",
        )

    normalized_events = [_validate_event(event, index) for index, event in enumerate(events)]
    seen = [event["capability"] for event in normalized_events]
    if len(set(seen)) != len(seen):
        raise FlowDiffError(
            "duplicate_capability",
            "trace.events must contain each capability exactly once.",
        )
    if set(seen) != set(CAPABILITIES):
        raise FlowDiffError(
            "incomplete_capabilities",
            "trace.events must cover every FlowDiff capability.",
        )

    by_capability = {event["capability"]: event for event in normalized_events}
    ordered_events = [by_capability[capability] for capability in CAPABILITIES]
    return {
        "schema_version": SCHEMA_VERSION,
        "app": app,
        "run_id": run_id,
        "events": ordered_events,
    }


def _weight(status: str) -> float | None:
    return STATUS_WEIGHT[status]


def _classify(baseline_status: str, candidate_status: str) -> str:
    baseline_weight = _weight(baseline_status)
    candidate_weight = _weight(candidate_status)
    if baseline_weight is None or candidate_weight is None:
        return "unverified"
    if baseline_weight < 1 and candidate_weight < 1:
        return "both_gap"
    if baseline_status == candidate_status:
        return "match"
    if candidate_weight > baseline_weight:
        return "candidate_ahead"
    return "candidate_gap"


def _percentage(total: float, count: int) -> float | None:
    if count == 0:
        return None
    return round(total / count * 100, 1)


def compare_traces(baseline: Any, candidate: Any) -> dict[str, Any]:
    """Compare two redacted traces and return only normalized metadata."""

    baseline_trace = validate_trace(baseline)
    candidate_trace = validate_trace(candidate)
    baseline_events = {
        event["capability"]: event for event in baseline_trace["events"]
    }
    candidate_events = {
        event["capability"]: event for event in candidate_trace["events"]
    }

    matrix: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    baseline_total = 0.0
    candidate_total = 0.0
    baseline_count = 0
    candidate_count = 0
    comparable_count = 0
    match_count = 0

    for capability in CAPABILITIES:
        base = baseline_events[capability]
        cand = candidate_events[capability]
        base_weight = _weight(base["status"])
        cand_weight = _weight(cand["status"])
        if base_weight is not None:
            baseline_total += base_weight
            baseline_count += 1
        if cand_weight is not None:
            candidate_total += cand_weight
            candidate_count += 1

        result = _classify(base["status"], cand["status"])
        if base_weight is not None and cand_weight is not None:
            comparable_count += 1
            if result == "match":
                match_count += 1

        duration_delta = None
        if base["duration_ms"] is not None and cand["duration_ms"] is not None:
            duration_delta = cand["duration_ms"] - base["duration_ms"]

        row = {
            "capability": capability,
            "label": CAPABILITY_LABELS[capability],
            "baseline": {
                "status": base["status"],
                "duration_ms": base["duration_ms"],
                "evidence_codes": base["evidence_codes"],
            },
            "candidate": {
                "status": cand["status"],
                "duration_ms": cand["duration_ms"],
                "evidence_codes": cand["evidence_codes"],
            },
            "result": result,
            "duration_delta_ms": duration_delta,
        }
        matrix.append(row)

        if cand_weight is None or cand_weight < 1:
            if cand_weight is None:
                severity = "unverified"
            elif cand_weight == 0:
                severity = "high"
            else:
                severity = "medium"
            gaps.append(
                {
                    "capability": capability,
                    "label": CAPABILITY_LABELS[capability],
                    "severity": severity,
                    "candidate_status": cand["status"],
                    "message": CAPABILITY_GAP_HINTS[capability],
                }
            )

    parity_percent = _percentage(match_count, comparable_count)
    candidate_percent = _percentage(candidate_total, candidate_count)
    baseline_percent = _percentage(baseline_total, baseline_count)
    if candidate_count == 0:
        overall = "unverified"
    elif gaps:
        overall = "gaps_found"
    else:
        overall = "aligned"

    return {
        "schema_version": SCHEMA_VERSION,
        "apps": {
            "baseline": baseline_trace["app"],
            "candidate": candidate_trace["app"],
        },
        "runs": {
            "baseline": baseline_trace["run_id"],
            "candidate": candidate_trace["run_id"],
        },
        "overall": overall,
        "score": {
            "baseline_percent": baseline_percent,
            "candidate_percent": candidate_percent,
            "parity_percent": parity_percent,
            "tested_capabilities": candidate_count,
            "gap_count": len(gaps),
        },
        "matrix": matrix,
        "gaps": gaps,
        "redaction": {
            "input": "sanitized capability events only",
            "storage": "none",
            "output": "no dictated text, screenshots, paths, URLs, or identifiers",
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the normalized comparison as a shareable Markdown report."""

    score = report["score"]
    baseline_percent = (
        "—" if score["baseline_percent"] is None else f'{score["baseline_percent"]:.1f}%'
    )
    candidate_percent = (
        "—" if score["candidate_percent"] is None else f'{score["candidate_percent"]:.1f}%'
    )
    parity_percent = (
        "—" if score["parity_percent"] is None else f'{score["parity_percent"]:.1f}%'
    )
    apps = report["apps"]
    lines = [
        "# FlowDiff report",
        "",
        f'**{apps["candidate"]}** compared with **{apps["baseline"]}** · '
        f'{report["overall"].replace("_", " ")}',
        "",
        f'| Candidate score | Baseline score | Parity | Gaps |',
        f'| ---: | ---: | ---: | ---: |',
        f'| {candidate_percent} | {baseline_percent} | {parity_percent} | '
        f'{score["gap_count"]} |',
        "",
        "## Capability matrix",
        "",
        "| Capability | Baseline | Candidate | Result | Δ ms |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for row in report["matrix"]:
        delta = "—" if row["duration_delta_ms"] is None else str(row["duration_delta_ms"])
        lines.append(
            f'| {row["label"]} | {row["baseline"]["status"]} | '
            f'{row["candidate"]["status"]} | {row["result"]} | {delta} |'
        )

    lines.extend(["", "## Gaps", ""])
    if report["gaps"]:
        for gap in report["gaps"]:
            lines.append(
                f'- **{gap["label"]}** · {gap["severity"]} — {gap["message"]}'
            )
    else:
        lines.append("No candidate gaps were found in the supplied trace.")

    lines.extend(
        [
            "",
            "## Privacy contract",
            "",
            "This report is derived from sanitized capability labels and bounded "
            "evidence codes. FlowDiff stores nothing and never accepts dictated "
            "text, screenshots, paths, URLs, or identifiers.",
        ]
    )
    return "\n".join(lines) + "\n"


def demo_traces() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return synthetic traces for the README and smoke tests."""

    def event(
        capability: str,
        status: str,
        duration_ms: int | None,
        evidence_codes: list[str],
    ) -> dict[str, Any]:
        return {
            "capability": capability,
            "status": status,
            "duration_ms": duration_ms,
            "evidence_codes": evidence_codes,
        }

    baseline = {
        "schema_version": "1",
        "app": "Baseline",
        "run_id": "demo-baseline",
        "events": [
            event("activation", "pass", 180, ["shortcut_fired", "bar_opened"]),
            event("recording_feedback", "pass", 240, ["recording_indicator", "timer_visible"]),
            event("insertion", "pass", 420, ["target_focused", "text_inserted"]),
            event("settings", "pass", 310, ["settings_opened", "shortcut_configured"]),
            event("history", "pass", 390, ["history_visible", "history_searchable"]),
            event("privacy", "pass", 160, ["local_only_copy", "retention_visible"]),
            event("recovery", "pass", 520, ["restart_recovered", "error_recovered"]),
            event("multi_display", "pass", 280, ["display_switch_ok", "bar_repositioned"]),
        ],
    }
    candidate = {
        "schema_version": "1",
        "app": "Candidate",
        "run_id": "demo-candidate",
        "events": [
            event("activation", "pass", 150, ["shortcut_fired", "bar_opened"]),
            event("recording_feedback", "pass", 220, ["recording_indicator"]),
            event("insertion", "pass", 360, ["target_focused", "text_inserted"]),
            event("settings", "partial", 460, ["settings_opened"]),
            event("history", "fail", 0, ["history_unavailable"]),
            event("privacy", "pass", 140, ["local_only_copy"]),
            event("recovery", "partial", 680, ["stuck_state"]),
            event("multi_display", "fail", 0, ["display_switch_lag"]),
        ],
    }
    return baseline, candidate


TOOLS = [
    {
        "name": "validate_dictation_trace",
        "description": (
            "Validate one sanitized dictation UX trace. Accepts only bounded "
            "capability statuses and evidence codes; rejects private content."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "trace": {
                    "type": "object",
                    "description": "A FlowDiff schema v1 redacted trace.",
                }
            },
            "required": ["trace"],
        },
    },
    {
        "name": "compare_dictation_traces",
        "description": (
            "Compare two sanitized dictation UX traces and return a parity "
            "matrix, bounded timing deltas, and actionable gaps."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "baseline": {
                    "type": "object",
                    "description": "The normalized baseline trace.",
                },
                "candidate": {
                    "type": "object",
                    "description": "The normalized candidate trace.",
                },
            },
            "required": ["baseline", "candidate"],
        },
    },
]


def _text_result(payload: Mapping[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            }
        ],
        "isError": is_error,
    }


def dispatch_request(request: Mapping[str, Any]) -> dict[str, Any] | None:
    """Dispatch one JSON-RPC request for tests and the stdio server."""

    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found."},
        }

    params = _require_mapping(request.get("params", {}), "params")
    name = params.get("name")
    arguments = params.get("arguments", {})
    try:
        if name == "validate_dictation_trace":
            args = _require_mapping(arguments, "arguments")
            _check_keys(args, {"trace"}, "arguments")
            payload = {
                "valid": True,
                "trace": validate_trace(args.get("trace")),
                "redaction": "private content is rejected and never returned",
            }
        elif name == "compare_dictation_traces":
            args = _require_mapping(arguments, "arguments")
            _check_keys(args, {"baseline", "candidate"}, "arguments")
            payload = compare_traces(args.get("baseline"), args.get("candidate"))
        else:
            raise FlowDiffError("unknown_tool", "The requested FlowDiff tool does not exist.")
    except FlowDiffError as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": _text_result(
                {"error_code": exc.code, "error": exc.public_message},
                is_error=True,
            ),
        }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": _text_result(payload),
    }


def run_stdio() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, Mapping):
                raise FlowDiffError("invalid_request", "JSON-RPC requests must be objects.")
            response = dispatch_request(request)
        except (json.JSONDecodeError, FlowDiffError) as exc:
            if isinstance(exc, FlowDiffError):
                error_message = exc.public_message
                error_code = -32600
            else:
                error_message = "Request was not valid JSON."
                error_code = -32700
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": error_code, "message": error_message},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FlowDiff redacted dictation UX parity tools.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Print a synthetic comparison report instead of starting MCP stdio.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format for --demo.",
    )
    args = parser.parse_args(argv)
    if not args.demo:
        run_stdio()
        return 0

    baseline, candidate = demo_traces()
    report = compare_traces(baseline, candidate)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
