"""Four local review cues, not a full security audit or vulnerability proofs.

The trusted infrastructure config is read directly from ROOT, even if untracked;
it is not a scan input. Only the common tracked Python snapshot is scanned.
"""

import hashlib
import stat
import sys

import yaml

import audit_scanner_common as c


RULE_IDS = {
    "ordo-shell-execution", "ordo-dynamic-execution",
    "ordo-pickle-deserialization", "ordo-shell-text",
}
RULE_COUNT = 4


def read_rules():
    path = c.ROOT / ".ordo/security/semgrep.yml"
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise c.Incomplete("invalid_local_rules")
        raw = path.read_bytes()
        config = yaml.safe_load(raw)
        if not isinstance(config, dict) or set(config) != {"rules"}:
            raise c.Incomplete("invalid_local_rules")
        rules = config["rules"]
        if not isinstance(rules, list) or len(rules) != RULE_COUNT:
            raise c.Incomplete("invalid_local_rules")
        ids = []
        for rule in rules:
            if not isinstance(rule, dict) or set(rule) != {
                "id", "message", "languages", "severity", "pattern-either",
            }:
                raise c.Incomplete("invalid_local_rules")
            if (
                not isinstance(rule["id"], str)
                or rule["languages"] != ["python"]
                or rule["severity"] not in ("WARNING", "ERROR")
                or not isinstance(rule["message"], str) or not rule["message"]
                or "$" in rule["message"]
                or not isinstance(rule["pattern-either"], list)
                or not rule["pattern-either"]
            ):
                raise c.Incomplete("invalid_local_rules")
            for pattern in rule["pattern-either"]:
                if (
                    not isinstance(pattern, dict) or set(pattern) != {"pattern"}
                    or not isinstance(pattern["pattern"], str) or not pattern["pattern"]
                ):
                    raise c.Incomplete("invalid_local_rules")
            ids.append(rule["id"])
        if set(ids) != RULE_IDS:
            raise c.Incomplete("invalid_local_rules")
        return raw
    except (OSError, ValueError, yaml.YAMLError):
        raise c.Incomplete("invalid_local_rules") from None


def parse_report(result, snap):
    report = c.json_output(result)
    if (
        not isinstance(report, dict)
        or not isinstance(report.get("results"), list)
        or not isinstance(report.get("errors"), list)
        or not isinstance(report.get("skipped_rules"), list)
        or not isinstance(report.get("paths"), dict)
        or not isinstance(report["paths"].get("scanned"), list)
    ):
        raise c.Incomplete("invalid_report")
    findings = []
    for item in report["results"]:
        if not isinstance(item, dict):
            raise c.Incomplete("invalid_report")
        rule = item.get("check_id")
        start, extra = item.get("start"), item.get("extra")
        if (
            not isinstance(rule, str) or rule not in RULE_IDS
            or not isinstance(start, dict) or type(start.get("line")) is not int
            or start["line"] <= 0 or not isinstance(extra, dict)
            or extra.get("severity") not in ("INFO", "WARNING", "ERROR")
        ):
            raise c.Incomplete("invalid_report")
        findings.append({
            "RuleID": rule,
            "File": c.report_path(item.get("path"), snap.source, snap.files),
            "Line": start["line"], "Severity": extra["severity"],
        })
    scanned = {
        c.report_path(path, snap.source, snap.files)
        for path in report["paths"]["scanned"]
    }
    incomplete = (
        result.returncode not in (0, 1)
        or bool(report["errors"]) or bool(report["skipped_rules"])
        or scanned != set(snap.files)
        or ("version" in report and report["version"] != c.PINS["semgrep"])
        or (result.returncode == 0 and bool(findings))
        or (result.returncode == 1 and not findings)
    )
    payload = {
        "status": "incomplete" if incomplete else "findings" if findings else "clean",
        "findings": findings[:c.MAX_FINDINGS], "finding_count": len(findings),
        "truncated": len(findings) > c.MAX_FINDINGS,
        "scanned_count": len(scanned),
    }
    if incomplete:
        payload["code"] = "scan_incomplete"
    return payload


def audit():
    payload = {
        "tool": "semgrep", "expected_version": c.PINS["semgrep"],
        "rule_count": RULE_COUNT,
        "coverage": {
            "local_rules_only": True, "history": False, "untracked": False,
            "excluded_tests": True,
            "roots": ["src/", "connectors/", "tools/", ".ordo/scripts/"],
        },
        "limitations": "Review cues only; not proofs or a full security audit.",
        "network_policy": "Local config, metrics off, version checks disabled; not a network sandbox.",
    }
    try:
        raw = read_rules()
        payload["rules_sha256"] = hashlib.sha256(raw).hexdigest()
        tool = c.python_tool("semgrep", "semgrep")
        with c.snapshot("python") as snap:
            payload["coverage"].update(snap.coverage)
            config = snap.base / "semgrep.yml"
            config.write_bytes(raw)
            result = c.run(tool + [
                "scan", "--oss-only", "--config", str(config),
                "--metrics", "off", "--disable-version-check", "--disable-nosem",
                "--strict", "--no-git-ignore", "--error", "--json",
                "--no-rewrite-rule-ids", "--max-target-bytes", "0",
                *snap.paths,
            ], cwd=snap.base, env=c.safe_env())
            payload.update(parse_report(result, snap))
    except c.Incomplete as error:
        payload.update(status="incomplete", code=error.code)
        if error.details:
            payload["details"] = error.details
    return payload


if __name__ == "__main__":
    sys.exit(c.finish(audit))
