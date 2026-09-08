"""Observational Bandit probe over the private tracked Python snapshot."""

import hashlib
import json
import re

import audit_scanner_common as c


REVIEWED_POLICY = ".ordo/security/bandit-reviewed.json"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate policy key")
        result[key] = value
    return result


def apply_reviewed(findings, source, selected):
    """Accept only the reviewed call bound to the entire scanned file's bytes."""
    try:
        c.report_path(REVIEWED_POLICY, c.ROOT, [REVIEWED_POLICY])
        policy = json.loads((c.ROOT / REVIEWED_POLICY).read_text(encoding="utf-8"),
                            object_pairs_hook=_unique_object)
        if (not isinstance(policy, dict) or set(policy) != {"version", "findings"}
                or type(policy["version"]) is not int or policy["version"] != 1
                or not isinstance(policy["findings"], list) or len(policy["findings"]) != 1):
            raise ValueError("invalid policy")
        entry = policy["findings"][0]
        if (not isinstance(entry, dict)
                or set(entry) != {"id", "code", "path", "line", "source_sha256", "reason"}
                or entry["id"] != "authored-style-safe-loader"
                or entry["code"] != "B506"
                or entry["path"] != "src/ordo/runtime/loading.py"
                or type(entry["line"]) is not int or entry["line"] != 175
                or not isinstance(entry["source_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["source_sha256"])
                or not isinstance(entry["reason"], str) or not entry["reason"].strip()):
            raise ValueError("invalid policy entry")
    except (c.Incomplete, OSError, UnicodeError, ValueError):
        raise c.Incomplete("bandit_reviewed_policy_invalid") from None
    bound = False
    if entry["path"] in selected:
        try:
            name = c.report_path(entry["path"], source, selected)
            bound = hashlib.sha256((source / name).read_bytes()).hexdigest() == entry["source_sha256"]
        except (c.Incomplete, OSError):
            raise c.Incomplete("bandit_reviewed_source_invalid") from None
    unresolved, accepted = [], []
    for finding in findings:
        if bound and all(finding[key] == entry[key] for key in ("code", "path", "line")):
            accepted.append({key: finding[key] for key in ("code", "path", "line")}
                            | {"exception_id": entry["id"]})
        else:
            unresolved.append(finding)
    return unresolved, accepted


def audit():
    tool = c.python_tool("bandit", "bandit")
    with c.snapshot("python") as snap:
        result = c.run(tool + [
            # Above 50 files Bandit otherwise prefixes JSON with Rich progress.
            "--quiet", "--format", "json", "--ignore-nosec",
            "--severity-level", "medium", "--confidence-level", "medium",
            *snap.paths,
        ], cwd=snap.base)
        report = c.json_output(result)
        if (not isinstance(report, dict)
                or not isinstance(report.get("results"), list)
                or not isinstance(report.get("errors"), list)
                or not isinstance(report.get("metrics"), dict)):
            raise c.Incomplete("invalid_report")
        findings = []
        for item in report["results"]:
            if (not isinstance(item, dict)
                    or not isinstance(item.get("test_id"), str)
                    or not re.fullmatch(r"B[0-9]{3}", item["test_id"])
                    or item.get("issue_severity") not in ("MEDIUM", "HIGH")
                    or item.get("issue_confidence") not in ("MEDIUM", "HIGH")
                    or type(item.get("line_number")) is not int
                    or item["line_number"] <= 0):
                raise c.Incomplete("invalid_report")
            findings.append({
                "code": item["test_id"],
                "path": c.report_path(item.get("filename"), snap.source, snap.files),
                "line": item["line_number"],
                "severity": item["issue_severity"],
                "confidence": item["issue_confidence"],
            })
        measured = set()
        for filename, metrics in report["metrics"].items():
            if not isinstance(metrics, dict):
                raise c.Incomplete("invalid_report")
            if filename != "_totals":
                name = c.report_path(filename, snap.source, snap.files)
                if name in measured:
                    raise c.Incomplete("invalid_report")
                measured.add(name)
        incomplete = (bool(report["errors"]) or measured != set(snap.files)
                       or result.returncode not in (0, 1)
                       or (not report["errors"] and bool(findings) != (result.returncode == 1)))
        raw_finding_count = len(findings)
        findings, accepted = apply_reviewed(findings, snap.source, snap.files)
        payload = {
            "status": "incomplete" if incomplete else "findings" if findings else "clean",
            "tool": "bandit", "version": c.PINS["bandit"],
            "coverage": dict(snap.coverage, scan_files=len(snap.files), metric_files=len(measured)),
            "policy": {
                "scope": "Tracked Python files under src/, connectors/, tools/, .ordo/scripts/; tests excluded by snapshot policy",
                "severity": "MEDIUM", "confidence": "MEDIUM", "ignore_nosec": True,
                "configuration": "Private snapshot base; explicit absolute files, no source .bandit configuration",
                "reviewed_exceptions": REVIEWED_POLICY,
                "exception_binding": "Exact code/path/line and SHA-256 of entire snapshot source file; changes require review, never automatic refresh",
            },
            "error_count": len(report["errors"]),
            "finding_count": len(findings),
            "raw_finding_count": raw_finding_count,
            "accepted_count": len(accepted),
            "accepted_findings": accepted[:c.MAX_FINDINGS],
            "accepted_truncated_count": max(0, len(accepted) - c.MAX_FINDINGS),
            "findings": findings[:c.MAX_FINDINGS],
            "truncated_count": max(0, len(findings) - c.MAX_FINDINGS),
        }
        if incomplete:
            payload["code"] = "bandit_scan_incomplete"
        return payload


if __name__ == "__main__":
    raise SystemExit(c.finish(audit))
