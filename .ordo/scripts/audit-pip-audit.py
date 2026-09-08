"""Consent-gated PyPI audit of the installed runtime closure, without resolution."""

from __future__ import annotations

import importlib.metadata
import re
import sys
import tomllib

import audit_scanner_common as c


def safe_name(value, canonicalize_name):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value.lower()):
        raise c.Incomplete("invalid_package_name")
    return canonicalize_name(value)


def safe_version(value, Version):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]*", value):
        raise c.Incomplete("invalid_package_version")
    try:
        return str(Version(value))
    except Exception:
        raise c.Incomplete("invalid_package_version") from None


def runtime_closure(Requirement, canonicalize_name, Version):
    try:
        with (c.ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        if "dependencies" in project.get("dynamic", []):
            raise c.Incomplete("dynamic_runtime_dependencies")
        pending = [(raw, {""}) for raw in project.get("dependencies", [])]
        if not isinstance(project.get("dependencies", []), list):
            raise c.Incomplete("invalid_runtime_requirements")
        installed = {}
        expanded = {}
        while pending:
            raw, contexts = pending.pop()
            if not isinstance(raw, str):
                raise c.Incomplete("invalid_runtime_requirements")
            req = Requirement(raw)
            if req.marker and not any(req.marker.evaluate({"extra": extra}) for extra in contexts):
                continue
            if req.url:
                raise c.Incomplete("runtime_direct_url")
            name = safe_name(req.name, canonicalize_name)
            if name not in installed:
                dist = importlib.metadata.distribution(name)
                metadata = dist.metadata
                names = metadata.get_all("Name") or []
                versions = metadata.get_all("Version") or []
                if len(names) != 1 or len(versions) != 1:
                    raise c.Incomplete("ambiguous_runtime_metadata")
                if safe_name(names[0], canonicalize_name) != name:
                    raise c.Incomplete("runtime_name_mismatch")
                version = safe_version(versions[0], Version)
                if safe_version(dist.version, Version) != version:
                    raise c.Incomplete("runtime_version_mismatch")
                # PEP 610 includes editable/local installs as well as remote URLs.
                if dist.read_text("direct_url.json") is not None:
                    raise c.Incomplete("runtime_direct_url")
                # Legacy egg installs cannot reliably disclose editable provenance.
                if not dist.read_text("WHEEL"):
                    raise c.Incomplete("unsupported_runtime_install")
                requires = dist.requires
                if requires is not None and not isinstance(requires, list):
                    raise c.Incomplete("invalid_runtime_metadata")
                provided = {safe_name(extra, canonicalize_name) for extra in metadata.get_all("Provides-Extra") or []}
                installed[name] = (version, requires or [], provided)
            version, requires, provided = installed[name]
            if not req.specifier.contains(Version(version), prereleases=True):
                raise c.Incomplete("runtime_constraint_mismatch")
            extras = {safe_name(extra, canonicalize_name) for extra in req.extras}
            if not extras <= provided:
                raise c.Incomplete("unsupported_runtime_extra")
            contexts = expanded.get(name, set()) | extras | {""}
            if contexts != expanded.get(name):
                expanded[name] = contexts
                # Revisit outgoing edges when another path requests more extras.
                pending.extend((dependency, contexts) for dependency in requires)
        if not installed:
            raise c.Incomplete("empty_runtime_scope")
        return {name: installed[name][0] for name in sorted(installed)}
    except c.Incomplete:
        raise
    except importlib.metadata.PackageNotFoundError:
        raise c.Incomplete("runtime_distribution_missing") from None
    except Exception:
        raise c.Incomplete("invalid_runtime_metadata") from None


def report(result, packages, canonicalize_name, Version):
    # v2.10.1 pip_audit/_format/json.py: object envelope, not the old array.
    data = c.json_output(result)
    if not isinstance(data, dict) or not isinstance(data.get("dependencies"), list):
        raise c.Incomplete("invalid_report")
    incomplete = set(data) != {"dependencies", "fixes"} or data.get("fixes") != []
    seen = set()
    findings = []
    total = 0
    for dependency in data["dependencies"]:
        try:
            if not isinstance(dependency, dict):
                raise c.Incomplete("invalid_report")
            if "skip_reason" in dependency or "skipped_reason" in dependency:
                raise c.Incomplete("invalid_report")
            name = safe_name(dependency.get("name"), canonicalize_name)
            version = safe_version(dependency.get("version"), Version)
            if name not in packages or Version(version) != Version(packages[name]) or name in seen:
                raise c.Incomplete("invalid_report")
            seen.add(name)
            vulns = dependency.get("vulns")
            if not isinstance(vulns, list):
                raise c.Incomplete("invalid_report")
            for vuln in vulns:
                try:
                    if not isinstance(vuln, dict):
                        raise c.Incomplete("invalid_report")
                    identifier = vuln.get("id")
                    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", identifier):
                        raise c.Incomplete("invalid_report")
                    fixes = vuln.get("fix_versions")
                    if not isinstance(fixes, list):
                        raise c.Incomplete("invalid_report")
                    fixes = [safe_version(value, Version) for value in fixes]
                    total += 1
                    if len(findings) < c.MAX_FINDINGS:
                        findings.append({"name": name, "version": packages[name], "id": identifier, "fix_versions": fixes})
                except c.Incomplete:
                    incomplete = True
        except c.Incomplete:
            incomplete = True
    incomplete |= seen != set(packages)
    if result.returncode not in (0, 1):
        code = "scanner_failed"
    elif incomplete:
        code = "incomplete_report"
    elif result.returncode != (1 if total else 0):
        code = "scanner_exit_mismatch"
    else:
        code = None
    payload = {"status": "incomplete" if code else "findings" if total else "clean", "findings": findings, "findings_total": total}
    if code:
        payload["code"] = code
    return payload


def audit(allow_network=False):
    payload = {
        "tool": "pip-audit", "version": c.PINS["pip-audit"],
        "coverage": {"runtimeOnly": True, "source": "installed-runtime-closure", "build": False, "test": False, "audit_tools": False},
        "network_service": "pypi", "runtimepackages_count": 0, "runtimepackages": [],
    }
    try:
        if type(allow_network) is not bool:
            raise c.Incomplete("invalid_network_permission")
        if not allow_network:
            raise c.Incomplete("network_not_authorized")
        command = c.python_tool("pip-audit", "pip_audit")
        # packaging is supplied by the pinned tool, never installed by this adapter.
        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name
        from packaging.version import Version

        packages = runtime_closure(Requirement, canonicalize_name, Version)
        payload["runtimepackages_count"] = len(packages)
        payload["runtimepackages"] = [{"name": name, "version": version} for name, version in packages.items()]
        with c._temporary() as base:
            requirement = base / "runtime-requirements.txt"
            requirement.write_text("".join(f"{name}=={version}\n" for name, version in packages.items()), encoding="ascii")
            requirement.chmod(0o600)
            result = c.run(command + [
                "--requirement", str(requirement), "--no-deps", "--disable-pip",
                "--format", "json", "--progress-spinner", "off", "--strict",
                "--vulnerability-service", "pypi",
            ], cwd=base, timeout=300)
        payload.update(report(result, packages, canonicalize_name, Version))
    except c.Incomplete as error:
        payload.update(status="incomplete", code=error.code)
        if error.details:
            payload["details"] = error.details
    except Exception:
        payload.update(status="incomplete", code="unexpected_error")
    return payload


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args:
        allow_network = False
    elif len(args) == 1 and args[0].lower() in ("true", "false"):
        allow_network = args[0].lower() == "true"
    else:
        return c.finish(lambda: {"status": "incomplete", "code": "invalid_network_permission"})
    return c.finish(lambda: audit(allow_network))


if __name__ == "__main__":
    raise SystemExit(main())
