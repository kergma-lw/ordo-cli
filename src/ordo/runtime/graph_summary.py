"""Presentation-only aggregation of the static graph's existing access sites.

No workflow loading, expression evaluation, address matching or cycle inference
belongs here. Site IDs keep every summary item traceable to the detailed graph.
"""

from copy import deepcopy
import json

from .graph_roles import build_role_view


def _context_key(site, parameter_families=()):
    address = site["address"]
    family = address.get("family")
    if family and family["id"] in parameter_families:
        selector = address["selector"]
        return ("state-family", family["id"], selector["kind"], selector.get("value"))
    if address["store_identity"] == address["key_identity"] == "proven":
        return (address["store"], address["key"])
    if address["store_identity"] == "proven" and address.get("key_candidates"):
        # Group the *set* of possible addresses, not their selected runtime value.
        # Coverage remains unresolved and every occurrence retains its evidence.
        return ("possible-address-domain", address["store"], tuple(sorted(address["key_candidates"])))
    # An unresolved expression is not evidence of equal values, even when its
    # spelling repeats. Do not silently merge symbolic occurrences into a store.
    return ("unresolved", site["id"])


def _place_context_users(contour, by_workflow, handoffs, incomplete_workflows):
    """Account for every read using existing links, never picking a newest writer.

    Alternatives are per-read candidate sets, not an enumerated or proven set of
    executable paths. Exact address coverage does not establish value availability.
    """
    sources = {}
    for change in contour["changes"]:
        for group in change["groups"]:
            if group["kind"] == "change":
                sources[group["id"]] = group
    writer_sources = {site: ref for ref, group in sources.items() for site in group["sites"]}
    read_contexts = {site: context["id"] for context in contour["contexts"]
                     for read in context["reads"] for site in read["sites"]}
    for user in contour["users"]:
        dependencies = []
        for read in by_workflow[user["workflow"]]:
            context = read_contexts[read["id"]]
            dependency = next((d for d in dependencies if d["context"] == context
                               and d["fields"] == read["address"]["fields"]
                               and d.get("address_signature") == read["address"]), None)
            if dependency is None:
                dependency = {"context": context, "fields": list(read["address"]["fields"]),
                              "address_signature": deepcopy(read["address"]),
                              "reads": [], "sources": []}
                dependencies.append(dependency)
            # Keep conditions and the containing expression, including catch
            # fallbacks. Optionality is not inferred by reparsing those expressions.
            dependency["reads"].append({"site": read["id"], "conditions": deepcopy(read["conditions"]),
                                        "expression": read.get("expression")})
            for link in handoffs.get(read["id"], []):
                ref = writer_sources.get(link["from"])
                if ref is None:
                    continue
                candidate = next((s for s in dependency["sources"] if s["ref"] == ref), None)
                if candidate is None:
                    candidate = {"ref": ref, "coverage": "possible", "evidence": [],
                                 "conditions": deepcopy(sources[ref]["conditions"])}
                    dependency["sources"].append(candidate)
                if "relation_category" in link:
                    candidate.setdefault("structural_evidence", []).append(deepcopy(link))
                    if candidate["coverage"] != "address_only":
                        candidate["coverage"] = "parametric"
                else:
                    candidate["evidence"].append({key: link[key] for key in
                        ("from", "to", "address_identity", "field_relation", "execution")})
                    if link["address_identity"] == "proven" and link["field_relation"] == "exact":
                        candidate["coverage"] = "address_only"
        refs = [ref for ref in sources if any(s["ref"] == ref for d in dependencies for s in d["sources"])]
        unresolved = [index for index, d in enumerate(dependencies)
                      if not any(s["coverage"] in {"address_only", "parametric"} for s in d["sources"])]
        alternatives = any(len(d["sources"]) > 1 for d in dependencies)
        complete_sources = set(refs)
        for dependency in dependencies:
            complete_sources.intersection_update(s["ref"] for s in dependency["sources"]
                                                  if s["coverage"] in {"address_only", "parametric"})
        incomplete = user["workflow"] in incomplete_workflows
        if unresolved or incomplete:
            kind = "unresolved"
        elif alternatives:
            kind = "alternatives" if complete_sources else "join_with_alternatives"
        elif len(refs) == 1:
            kind = "single_source"
        else:
            kind = "join"
        user["dependencies"] = dependencies
        user["placement"] = {
            "kind": kind, "sources": refs,
            # Alternatives do not justify any one parent. Joins retain their
            # existing last-displayed-reference layout, not execution precedence.
            "after": refs[-1] if refs and kind != "alternatives" else None,
            "unresolved_dependencies": unresolved, "incomplete_reader": incomplete,
            "has_alternatives": alternatives,
            "conditional_sources": [ref for ref in refs if any(
                c["kind"] in {"if", "iteration", "short_circuit"} for c in sources[ref]["conditions"])],
            "coverage": "all_read_sites", "phase": "body", "availability": "symbolic",
            "parametric": any(s["coverage"] == "parametric" for d in dependencies for s in d["sources"]),
        }


def summarize_static_graph(payload: dict[str, object]) -> dict[str, object]:
    """Derive context usage and ordered mutation groups without changing relations."""
    contours = []
    # Playbook loading supplies authored entry order. Keep it explicit rather
    # than using alphabetically sorted component membership as a display order.
    workflow_order = [node["workflow"] for node in payload["workflows"]]
    by_workflow = {name: [] for name in workflow_order}
    bootstrap = [site for site in payload["accesses"] if site.get("phase") == "bootstrap"]
    bootstrap_names = {site["workflow"] for site in bootstrap}
    bootstrap_boundaries = [dict(boundary, workflow=node["workflow"]) for node in payload["workflows"]
                            for boundary in node["boundaries"] if boundary.get("phase") == "bootstrap"]
    bootstrap_boundaries.extend(b for b in payload["boundaries"] if b.get("phase") == "bootstrap")
    bootstrap_names.update(b["workflow"] for b in bootstrap_boundaries if "workflow" in b)
    for site in payload["accesses"]:
        if site.get("phase", "body") == "body":
            by_workflow[site["workflow"]].append(site)
    body_ids = {site["id"] for sites in by_workflow.values() for site in sites}
    handoffs = {}
    for link in payload["links"]:
        if link["kind"] == "handoff" and link["from"] in body_ids and link["to"] in body_ids:
            handoffs.setdefault(link["to"], []).append(link)
    for link in payload.get("structural_links", []):
        if link["kind"] == "handoff" and link["from"] in body_ids and link["to"] in body_ids:
            handoffs.setdefault(link["to"], []).append(link)
    def structural(boundary):
        return boundary.get("impact", "structure") == "structure" and boundary.get("phase", "body") == "body"
    incomplete_workflows = {node["workflow"] for node in payload["workflows"] if any(structural(b) for b in node["boundaries"])}
    incomplete_workflows.update(b["workflow"] for b in payload["boundaries"] if "workflow" in b and structural(b))
    inactive = []
    for members in payload.get("structural_components", payload.get("business_components", payload["components"])):
        if not any(by_workflow[name] for name in members):
            inactive.extend(name for name in members if name not in bootstrap_names)
            continue
        contexts, context_ids, users, changes = [], {}, [], []
        parameter_families = {site["address"]["family"]["id"] for name in members for site in by_workflow[name]
                              if site["address"].get("family") and site["address"].get("selector", {}).get("kind") == "parameter"
                              and (site["address"]["key_identity"] != "proven" or site["address"]["store_identity"] != "proven")}
        parameter_families.update(link["family"] for link in payload.get("structural_links", [])
                                  if link["from_workflow"] in members and link["to_workflow"] in members
                                  and link["from"] in body_ids and link["to"] in body_ids
                                  and any(r["predicate"] == "same_family_instance" for r in link["requirements"]))

        def context_for(site):
            key = _context_key(site, parameter_families)
            if key not in context_ids:
                context_ids[key] = len(contexts)
                address = deepcopy(site["address"])
                address.pop("fields")
                contexts.append({"id": f"C{len(contexts) + 1}", "address": address, "reads": [],
                                 "parameter_family": address.get("family", {}).get("id") in parameter_families})
            return contexts[context_ids[key]]

        # This supplies the authored-order tie-break within a category and keeps
        # existing cross-category behavior. Category is never a dependency or a
        # grouping/sorting key. Source placement is applied separately below.
        for name in workflow_order:
            sites = by_workflow[name]
            if name not in members or not sites:
                continue
            reads = []
            for site in sites:
                context = context_for(site)
                if site["kind"] != "read":
                    continue
                fields = site["address"]["fields"]
                existing = next((r for r in context["reads"] if r["fields"] == fields), None)
                if existing is None:
                    existing = {"fields": list(fields), "sites": [], "workflows": []}
                    context["reads"].append(existing)
                existing["sites"].append(site["id"])
                if name not in existing["workflows"]:
                    existing["workflows"].append(name)
                if context["id"] not in reads:
                    reads.append(context["id"])
            if all(site["kind"] == "read" for site in sites):
                users.append({"workflow": name, "contexts": reads})
                continue
            groups = []
            previous = None
            for site in sites:
                if site["kind"] == "read":
                    previous = None
                    continue
                context = context_for(site)
                signature = (site["kind"], context["id"], site["conditions"])
                if previous != signature:
                    groups.append({"kind": "change" if site["kind"] == "set" else "removal",
                                   "context": context["id"], "conditions": deepcopy(site["conditions"]),
                                   "fields": [], "sites": []})
                group = groups[-1]
                group["sites"].append(site["id"])
                field = site["address"]["fields"]
                if field not in group["fields"]:
                    group["fields"].append(list(field))
                previous = signature
            changes.append({"workflow": name, "reads": reads, "groups": groups})
        for number, group in enumerate((g for change in changes for g in change["groups"]), 1):
            group["id"] = f"S{number}"
        contour = {"workflows": list(members), "contexts": contexts, "changes": changes, "users": users}
        _place_context_users(contour, by_workflow, handoffs, incomplete_workflows)
        contour["role_view"] = build_role_view(payload, contour, _standalone_alternatives)
        contours.append(contour)
    result = {"placement_version": 1, "contours": contours, "without_state_access": inactive}
    if bootstrap or bootstrap_boundaries:
        result["bootstrap"] = {"accesses": [site["id"] for site in bootstrap],
            "workflows": [name for name in workflow_order if name in bootstrap_names],
            "only_workflows": [name for name in workflow_order if name in bootstrap_names and not by_workflow[name]],
            "boundaries": bootstrap_boundaries}
    return result


def _context_labels(summary, contour):
    """Prefer logical bindings; qualify only collisions, without filesystem IO."""
    stores = {}
    for item in summary["contours"]:
        for context in item["contexts"]:
            address = context["address"]
            name = address["binding"] or address["role"]
            stores.setdefault(name, set()).add(address["store"])
    labels = {}
    for context in contour["contexts"]:
        address = context["address"]
        name = address["binding"] or address["role"]
        store = address["store"]
        if context.get("parameter_family"):
            selector = address["selector"]
            key = "parameter" if selector["kind"] == "parameter" else json.dumps(selector["value"])
            labels[context["id"]] = f"{address['family']['name']}[{key}]"
            continue
        if len(stores[name]) > 1:
            if store is None:
                name += " (store unresolved)"
            else:
                parts = store.split("/")
                for length in range(1, len(parts) + 1):
                    suffix = "/".join(parts[-length:])
                    if all(other is None or other == store or not other.endswith("/" + suffix)
                           for other in stores[name]):
                        break
                name += f" ({suffix})"
        key = json.dumps(address["key"]) if address["key_identity"] == "proven" else (
            f"{len(address['key_candidates'])} possible keys" if address.get("key_candidates") else "unknown key")
        label = f"{name}[{key}]"
        if address["store_identity"] != "proven" or address["key_identity"] != "proven":
            label += " (unresolved)"
            if label in labels.values():
                label += f" (distinct occurrence {sum(value.startswith(label) for value in labels.values()) + 1})"
        labels[context["id"]] = label
    return labels


def _tree_branches(names):
    return [("└── " if index == len(names) - 1 else "├── ") + name
            for index, name in enumerate(names)]


def _mutation_suffix(change, contexts):
    """Compact effect inventory, not creation, readiness or coverage proof."""
    effects = {}
    for group in change["groups"]:
        conditional = any(
            condition["kind"] in {"if", "iteration", "short_circuit"}
            or (condition["kind"] == "conditional_gate" and condition.get("if") is not None)
            for condition in group["conditions"]
        )
        for fields in group["fields"]:
            key = (group["context"], group["kind"], tuple(fields))
            if key not in effects:
                effects[key] = {"conditional": conditional, "conditions": group["conditions"]}
            else:
                # Never infer unconditional coverage from complementary branches
                # or writes admitted under different guards/gates.
                effects[key]["conditional"] |= conditional or effects[key]["conditions"] != group["conditions"]
    labels = []
    for (context, kind, fields), evidence in effects.items():
        target = ".".join(fields) if fields else "context"
        if len(contexts) > 1 or fields == ("context",):
            target = contexts[context] + ("." + ".".join(fields) if fields else "")
        labels.append(("+" if kind == "change" else "−") + target + ("?" if evidence["conditional"] else ""))
    return " (" + ", ".join(labels) + ")" if labels else ""


def _standalone_alternatives(blocks, users, workflow_nodes):
    """Insert free rows without moving or splitting existing anchored blocks."""
    order = {node["workflow"]: index for index, node in enumerate(workflow_nodes)}
    categories = {node["workflow"]: node.get("category") for node in workflow_nodes}
    rows = [(change, children) for change, children in blocks]
    for user in users:
        name = user["workflow"]
        position = order.get(name, len(order))
        category = categories.get(name)
        fallback = next((i for i, (row, _) in enumerate(rows)
                         if order.get(row["workflow"], len(order)) > position), len(rows))
        lower, upper = 0, len(rows)
        if category is not None:
            for index, (row, children) in enumerate(rows):
                members = [row["workflow"], *children]
                peers = [member for member in members if categories.get(member) == category]
                if any(order.get(member, len(order)) < position for member in peers):
                    lower = max(lower, index + 1)
                if any(order.get(member, len(order)) > position for member in peers):
                    upper = min(upper, index)
        # Category order may conflict inside an indivisible source/reader block.
        # Preserve that anchor and use authored root-row order in that case.
        slot = min(max(fallback, lower), upper) if lower <= upper else fallback
        # Even when anchored category constraints conflict, free rows themselves
        # can retain their authored same-category order.
        slot = max([slot, *(i + 1 for i, (row, _) in enumerate(rows)
                           if "groups" not in row and categories.get(row["workflow"]) == category)])
        rows.insert(slot, ({"workflow": name}, []))
    return rows


def render_graph_summary(payload: dict[str, object]) -> str:
    summary = payload.get("summary")
    if (not summary or summary.get("placement_version") != 1
            or any("display_rows" not in c.get("role_view", {}).get("forest", {}) for c in summary["contours"])):
        summary = summarize_static_graph(payload)
    lines = ["Shared context: writers → readers, not execution order.",
             "+ write, − delete, ? conditional."]
    if any(role["shared_workflow"] for contour in summary["contours"]
           for role in contour["role_view"]["roles"]):
        lines.append("↔ another role of the same workflow.")
    if any(row["reference"] for contour in summary["contours"]
           for row in contour["role_view"]["forest"]["display_rows"]):
        lines.append("↔ (reference) the same operation, shown again.")
    for index, contour in enumerate(summary["contours"], 1):
        if lines:
            lines.append("")
        contexts = _context_labels(summary, contour)
        if len(summary["contours"]) > 1:
            lines.extend([f"Contour {index}", ""])
        view = contour["role_view"]
        roles = {role["id"]: role for role in view["roles"]}
        if "forest" in view:
            nodes = {node["id"]: node for node in view["forest"]["nodes"]}

            def label(ref, row):
                node = nodes[ref]
                role = roles.get(node.get("role"))
                placement = node["placement"]
                text = node["workflow"]
                if row["reference"]:
                    text += (f" ↔ {role['state']['name']}/{role['kind']}" if role and role["shared_workflow"]
                             else " ↔") + " (reference)"
                    if row["parent"] in placement["conditional_sources"]:
                        text += " [conditional use]"
                    return text
                if role:
                    text += _mutation_suffix(role, contexts)
                    if role["shared_workflow"]:
                        text += f" ↔ {role['state']['name']}/{role['kind']}"
                    if role.get("placement", {}).get("kind") == "unresolved" and not placement["sources"]:
                        text += " [placement unresolved]"
                elif placement["kind"] == "alternatives" and placement["parent"] is None:
                    text += " (data use; alternative sources)"
                notes = []
                sources = placement["sources"]
                parent = row["parent"]
                def source_label(source):
                    result = nodes[source]["workflow"]
                    source_role = roles[source]
                    if source_role["shared_workflow"]:
                        result += f"/{source_role['state']['name']}/write"
                    return result + ("?" if source in placement["conditional_sources"] else "")
                extras = [source for source in sources if source != parent]
                if extras:
                    notes.append(("also reads from: " if parent in sources else "read sources: ")
                                 + ", ".join(source_label(source) for source in extras))
                if parent in placement["conditional_sources"]:
                    notes.append("reads from: " + source_label(parent))
                if placement["kind"] == "cycle":
                    notes.append("data-use cycle")
                if placement["unknown_reads"] or placement["incomplete"]:
                    notes.append("other sources unknown" if sources else "sources unknown")
                return text + (" [" + "; ".join(notes) + "]" if notes else "")

            # References are leaves, even when their target has descendants.
            # Only the canonical occurrence owns the target's subtree.
            display_children = {None: [], **{ref: [] for ref in nodes}}
            for row in view["forest"]["display_rows"]:
                display_children[row["parent"]].append(row)
            stack = [(row, "", "") for row in reversed(display_children[None])]
            visited = set()
            while stack:
                row, prefix, branch = stack.pop()
                ref = row["node"]
                if ref in visited and not row["reference"]:
                    row = {**row, "reference": True}
                lines.append(prefix + branch + label(ref, row))
                if row["reference"]:
                    continue
                visited.add(ref)
                child_prefix = prefix + ("    " if branch == "└── " else "│   " if branch else "")
                children = display_children[ref]
                stack.extend((child, child_prefix, "└── " if i == len(children) - 1 else "├── ")
                             for i, child in reversed(list(enumerate(children))))
            continue
        for row in view["rows"]:
            if "unresolved_readers" in row:
                lines.append("Unresolved placement")
                lines.extend(_tree_branches(row["unresolved_readers"]))
                continue
            role = roles.get(row.get("role"))
            if role is None:
                lines.append(row["workflow"] + " (data use; alternative sources)")
            else:
                indicator = f" ↔ {role['state']['name']}/{role['kind']}" if role["shared_workflow"] else ""
                if role.get("placement", {}).get("kind") == "unresolved":
                    indicator += " [placement unresolved]"
                lines.append(role["workflow"] + _mutation_suffix(role, contexts) + indicator)
            lines.extend(_tree_branches(row["children"]))
    if not summary["contours"]:
        lines.extend(["", "No state-linked workflows."])
    if summary.get("bootstrap"):
        lines.extend(["", "Bootstrap dependencies: --json."])
    if any(user["placement"].get("parametric") for contour in summary["contours"] for user in contour["users"]):
        lines.extend(["", "Parametric links require matching selectors, state instances and read shapes."])
    lines.extend(["", "Details: --json.", "Full list: ordo-playbook workflows list"])
    return "\n".join(lines)
