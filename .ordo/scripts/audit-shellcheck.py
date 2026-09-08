"""Observational ShellCheck probe; never execute the selected shell sources."""

import re

import audit_scanner_common as c


def audit():
    tool = c.native_tool("shellcheck")
    with c.snapshot("shell") as snap:
        # --norc does not disable inline external-sources overrides. Reject the
        # setting conservatively, including false, instead of rewriting sources.
        directive = rb"(?m)^[ \t]*#[ \t]*shellcheck[ \t]+[^\r\n]*\bexternal-sources[ \t]*="
        for name in snap.files:
            if re.search(directive, (snap.source / name).read_bytes()):
                raise c.Incomplete("unsupported_external_source_directive")
        result = c.run([tool, "--norc", "--format=json1", "--", *snap.paths], cwd=snap.base)
        report = c.json_output(result)
        if not isinstance(report, dict) or not isinstance(report.get("comments"), list):
            raise c.Incomplete("invalid_report")
        findings = []
        for item in report["comments"]:
            if (not isinstance(item, dict)
                    or type(item.get("code")) is not int or item["code"] <= 0
                    or type(item.get("line")) is not int or item["line"] <= 0
                    or item.get("level") not in ("error", "warning", "info", "style")):
                raise c.Incomplete("invalid_report")
            findings.append({
                "code": "SC" + str(item["code"]),
                "path": c.report_path(item.get("file"), snap.source, snap.files),
                "line": item["line"], "level": item["level"],
            })
        incomplete = result.returncode not in (0, 1) or bool(findings) != (result.returncode == 1)
        payload = {
            "status": "incomplete" if incomplete else "findings" if findings else "clean",
            "tool": "shellcheck", "version": c.PINS["shellcheck"],
            "coverage": dict(snap.coverage, scan_files=len(snap.files)),
            "policy": {
                "scope": "Tracked .sh/.bash files and recognized sh/bash shebang files selected by snapshot",
                "configuration": "--norc; SHELLCHECK_OPTS removed by common environment",
                "sources": "Only supplied files; external sourcing not enabled; inline external-sources assignments rejected",
                "limitations": [
                    "Inline shellcheck disable directives still apply",
                    "Sourced files outside the selected scope are not followed by default",
                    "Syntax findings do not establish complete semantic analysis",
                ],
            },
            "finding_count": len(findings), "findings": findings[:c.MAX_FINDINGS],
            "truncated_count": max(0, len(findings) - c.MAX_FINDINGS),
        }
        if incomplete:
            payload["code"] = "shellcheck_scan_incomplete"
        return payload


if __name__ == "__main__":
    raise SystemExit(c.finish(audit))
