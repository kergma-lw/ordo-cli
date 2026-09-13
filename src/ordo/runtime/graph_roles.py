"""Display projections of existing workflows; never execution vertices.

The unit is workflow × declaration-owned logical state × write/delete. Keys and
fields constrain a role's affected region, but do not create more state roles.
"""

from copy import deepcopy


def logical_state(site):
    address = site["address"]
    family = address.get("family")
    if family:
        return {"id": family["id"], "name": family["name"], "identity": "declared"}
    binding = address.get("binding") or address["role"]
    return {"id": f"unresolved:{site['workflow']}:{binding}", "name": binding, "identity": "unresolved"}


def _overlap(deletion, target):
    # Reuse the graph's existing concrete and structural address predicates.
    # No new relation is added to either detailed graph by this display query.
    from .graphing import _relation
    from .graph_structure import structural_relation

    concrete = _relation(deletion, target)
    structural = structural_relation(deletion, target, concrete)
    if concrete is None and structural is None:
        return None
    return {"delete": deletion["id"], "target": target["id"], "concrete": concrete,
            "structural": structural,
            "trusted": structural is not None or (concrete is not None and concrete["address_identity"] == "proven")}


def build_role_view(payload, contour, alternative_layout):
    sites = {site["id"]: site for site in payload["accesses"]
             if site.get("phase", "body") == "body" and site["workflow"] in contour["workflows"]}
    roles, indexed = [], {}
    for change in contour["changes"]:
        for group in change["groups"]:
            for site_id in group["sites"]:
                site = sites[site_id]
                state = logical_state(site)
                kind = "write" if site["kind"] == "set" else "delete"
                key = (change["workflow"], state["id"], kind)
                if key not in indexed:
                    role = {"id": f"R{len(roles) + 1}", "workflow": change["workflow"],
                            "state": state, "kind": kind, "sites": [], "groups": [], "read_sites": []}
                    indexed[key] = role
                    roles.append(role)
                role = indexed[key]
                role["sites"].append(site_id)
                projected = next((g for g in role["groups"] if g["id"] == group["id"]), None)
                if projected is None:
                    projected = {**deepcopy(group), "sites": [], "fields": []}
                    role["groups"].append(projected)
                projected["sites"].append(site_id)
                fields = site["address"]["fields"]
                if fields not in projected["fields"]:
                    projected["fields"].append(list(fields))
    counts = {}
    for role in roles:
        counts[role["workflow"]] = counts.get(role["workflow"], 0) + 1
        role["read_sites"] = [site["id"] for site in sites.values() if site["kind"] == "read"
                              and site["workflow"] == role["workflow"] and logical_state(site)["id"] == role["state"]["id"]]
    for role in roles:
        role["shared_workflow"] = counts[role["workflow"]] > 1

    writes = [role for role in roles if role["kind"] == "write"]
    writer_for_site = {site: role for role in writes for site in role["sites"]}
    reader_anchors = {}
    for user in contour["users"]:
        placement = user["placement"]
        if placement["kind"] in {"unresolved", "alternatives"}:
            continue
        source_sites = {e["from"] for d in user["dependencies"] for source in d["sources"]
                        if source["ref"] == placement["after"]
                        for e in [*source.get("evidence", []), *source.get("structural_evidence", [])]}
        candidates = [role for role in writes if any(g["id"] == placement["after"] for g in role["groups"])
                      and (not source_sites or source_sites.intersection(role["sites"]))]
        if candidates:
            reader_anchors[user["workflow"]] = {"role": candidates[-1]["id"],
                "source_group": placement["after"], "candidate_roles": [role["id"] for role in candidates]}
    blocks = []
    for role in writes:
        # Keep the previous source-group-first ordering within each writer block.
        children = []
        for group in role["groups"]:
            children.extend(user["workflow"] for user in contour["users"]
                            if reader_anchors.get(user["workflow"], {}).get("role") == role["id"]
                            and user["placement"]["after"] == group["id"] and user["workflow"] not in children)
        blocks.append((role, children))
    alternatives = [user for user in contour["users"] if user["placement"]["kind"] == "alternatives"]
    base = alternative_layout(blocks, alternatives, payload["workflows"])
    role_positions = {row["id"]: index for index, (row, _) in enumerate(base) if "id" in row}
    reader_positions = {name: index for index, (row, children) in enumerate(base)
                        for name in (children if "id" in row else [row["workflow"]])}
    unresolved = [user["workflow"] for user in contour["users"] if user["workflow"] not in reader_positions]
    order = {node["workflow"]: index for index, node in enumerate(payload["workflows"])}
    endings, loose = {}, {}
    for role in (role for role in roles if role["kind"] == "delete"):
        matches = []
        for deletion_id in role["sites"]:
            for target in sites.values():
                if target["kind"] in {"read", "set"}:
                    match = _overlap(sites[deletion_id], target)
                    if match is not None:
                        matches.append(match)
        trusted = [match for match in matches if match["trusted"]]
        creator_ids = {writer_for_site[m["target"]]["id"] for m in trusted if m["target"] in writer_for_site}
        read_ids = {m["target"] for m in trusted if sites[m["target"]]["kind"] == "read"}
        related_users = {sites[site]["workflow"] for site in read_ids} - {role["workflow"]}
        local_readers = set()
        for name in related_users:
            reads = {site["id"] for site in sites.values() if site["workflow"] == name and site["kind"] == "read"}
            # A cross-context reader is still evidence, but its anchor in another
            # state's writer block must not drag this termination there.
            if reads and reads <= read_ids:
                local_readers.add(name)
        positions = [role_positions[ref] for ref in creator_ids]
        positions.extend(reader_positions[name] for name in local_readers if name in reader_positions)
        positions.extend(role_positions[writer["id"]] for writer in writes
                         if writer["workflow"] in local_readers and read_ids.intersection(writer["read_sites"]))
        if not positions and read_ids:
            positions.extend(len(base) for name in local_readers if name in unresolved)
        rewrites = [{"delete": m["delete"], "write": m["target"]} for m in trusted
                    if sites[m["target"]]["kind"] == "set"
                    and sites[m["target"]]["workflow"] == role["workflow"]
                    and sites[m["target"]]["order"] > sites[m["delete"]]["order"]]
        role["termination"] = {
            "evidence": matches, "creator_roles": [r["id"] for r in writes if r["id"] in creator_ids],
            "affected_reads": [site for site in sites if site in read_ids],
            "related_users": [name for name in order if name in related_users],
            "cross_context_users": [name for name in order if name in related_users - local_readers],
            "rewrites_after_delete": rewrites,
            "cyclic": any(role["workflow"] in component and any(sites[s]["workflow"] in component for s in read_ids)
                          for component in payload.get("structural_loop_components", payload["possible_loop_components"])),
            "conditional": any(m["structural"] and m["structural"]["requirements"] for m in trusted),
        }
        if positions:
            after = max(positions)
            role["placement"] = {"kind": "terminal", "after_block": after,
                                 "candidate_blocks": sorted(set(positions)),
                                 "multiple_sections": len(set(positions)) > 1,
                                  "basis": "affected_creators_and_local_users"}
            endings.setdefault(after, []).append(role["id"])
        else:
            # No invented end-of-global-list placement when the affected region
            # cannot be identified. Keep a visible authored-position fallback.
            slot = next((i for i, (row, _) in enumerate(base)
                         if order.get(row["workflow"], 0) > order.get(role["workflow"], 0)), len(base))
            uncertain = any(not m["trusted"] for m in matches) or role["state"]["identity"] == "unresolved"
            role["placement"] = {"kind": "unresolved" if uncertain else "isolated", "before_block": slot,
                                 "basis": "no_trusted_related_visible_section"}
            loose.setdefault(slot, []).append(role["id"])
    rows = []
    for index in range(len(base) + 1):
        rows.extend({"role": ref, "children": []} for ref in loose.get(index, []))
        if index < len(base):
            row, children = base[index]
            rows.append({"role": row["id"], "children": children} if "id" in row else
                        {"workflow": row["workflow"], "children": children})
            rows.extend({"role": ref, "children": []} for ref in endings.get(index, []))
        elif unresolved:
            rows.append({"unresolved_readers": unresolved})
        if index == len(base):
            rows.extend({"role": ref, "children": []} for ref in endings.get(index, []))
    forest = _source_forest(payload, contour, roles, sites, rows)
    return {"roles": roles, "rows": rows, "reader_anchors": reader_anchors, "forest": forest,
            "semantics": "Display roles share workflow identity; termination placement is visual, not execution order."}


def _source_forest(payload, contour, roles, sites, rows):
    """Project handoffs onto display roles without changing access/link evidence."""
    from .graphing import _components

    writers = {site: role["id"] for role in roles if role["kind"] == "write" for site in role["sites"]}
    nodes = {role["id"]: {"id": role["id"], "role": role["id"], "workflow": role["workflow"]}
             for role in roles}
    nodes.update({f"W:{user['workflow']}": {"id": f"W:{user['workflow']}", "workflow": user["workflow"]}
                  for user in contour["users"]})
    incoming = {}
    handoffs = []
    for link in [*payload["links"], *payload.get("structural_links", [])]:
        if (link["kind"] != "handoff" or link["from"] not in writers or link["to"] not in sites
                or link["from_workflow"] == link["to_workflow"]):
            continue
        trusted = "relation_category" in link or link.get("address_identity") == "proven"
        incoming.setdefault(link["to"], []).append((writers[link["from"]], trusted))
        if trusted:
            handoffs.append(link)
    # Invalidation is not handoff precedence. Only handoff SCCs constrain nesting.
    components = _components(contour["workflows"], handoffs, directed=True)
    cyclic = {name: set(component) for component in components if len(component) > 1 for name in component}
    role_by_id = {role["id"]: role for role in roles}
    for ref, node in nodes.items():
        reads = [site for site in sites.values() if site["workflow"] == node["workflow"] and site["kind"] == "read"]
        # These are accesses of the shared workflow, not invented executions of
        # each state role. Keep the existing state-local read_sites unchanged.
        sources, unknown, alternatives = set(), [], False
        source_reads = {}
        conditional = set()
        for read in reads:
            candidates = {source for source, trusted in incoming.get(read["id"], []) if trusted}
            sources.update(candidates)
            for source in candidates:
                source_reads.setdefault(source, []).append(read["id"])
            alternatives |= len(candidates) > 1
            if (any(not trusted and source not in candidates for source, trusted in incoming.get(read["id"], []))
                    or not incoming.get(read["id"])):
                # Self reads are intra-operation, not missing external parents.
                if not any(site["workflow"] == node["workflow"] and site["kind"] == "set"
                           and site["address"] == read["address"] for site in sites.values()):
                    unknown.append(read["id"])
            if _conditional_read(read):
                conditional.update(candidates)
        role = role_by_id.get(ref)
        basis = "body_handoffs"
        if role and role["kind"] == "delete" and not sources:
            basis = "affected_creators"
            sources.update(source for source in role["termination"]["creator_roles"]
                           if nodes[source]["workflow"] != node["workflow"])
        node["placement"] = {"parent": None, "sources": [r for r in nodes if r in sources],
                             "conditional_sources": [r for r in nodes if r in conditional],
                             "source_reads": {r: source_reads[r] for r in nodes if r in source_reads},
                             "read_sites": [read["id"] for read in reads], "unknown_reads": unknown,
                             "alternatives": alternatives, "kind": "root", "basis": basis}
        node["placement"]["incomplete"] = any(
            b.get("phase", "body") == "body" and b.get("impact", "structure") == "structure"
            for workflow in payload["workflows"] if workflow["workflow"] == node["workflow"]
            for b in workflow.get("boundaries", [])) or any(
                b.get("workflow") == node["workflow"] and b.get("phase", "body") == "body"
                and b.get("impact", "structure") == "structure" for b in payload.get("boundaries", []))

    def ancestors(ref):
        result = []
        while ref is not None:
            result.append(ref)
            ref = nodes[ref]["placement"]["parent"]
        return result

    # Establish unique anchors first, then resolve chains/common ancestors to a
    # fixed point. No source order can select an arbitrary parent of a join.
    for _ in range(len(nodes) + 1):
        changed = False
        for ref, node in nodes.items():
            placement = node["placement"]
            sources = placement["sources"]
            if not sources:
                continue
            loops = [source for source in sources
                     if nodes[source]["workflow"] in cyclic.get(node["workflow"], set())]
            candidates = [source for source in sources if source not in loops]
            parent, kind = None, "cycle" if loops else "join"
            if candidates and not loops:
                if len(candidates) == 1:
                    parent, kind = candidates[0], "single_source"
                elif not placement["alternatives"]:
                    deepest = [source for source in candidates
                               if set(candidates) <= set(ancestors(source))]
                    if len(deepest) == 1:
                        parent, kind = deepest[0], "chain"
                if parent is None:
                    paths = [ancestors(source) for source in candidates]
                    common = set(paths[0]).intersection(*paths[1:]) - set(candidates)
                    parent = next((source for source in paths[0] if source in common), None)
                    kind = "alternatives" if placement["alternatives"] else "join"
            if parent is not None and ref in ancestors(parent):
                parent, kind = None, "cycle"
            if placement["parent"] != parent:
                placement["parent"] = parent
                changed = True
            placement["kind"] = kind
        if not changed:
            break
    # Preserve the existing affected-section terminal ordering at root level;
    # within each parent, terminal roles follow its other children.
    rank = {}
    for row in rows:
        refs = ([row["role"]] if "role" in row else
                [f"W:{row['workflow']}"] if "workflow" in row else
                [f"W:{name}" for name in row["unresolved_readers"]])
        refs.extend(f"W:{name}" for name in row.get("children", []))
        for ref in refs:
            rank[ref] = len(rank)
    children = {None: [], **{ref: [] for ref in nodes}}
    for ref, node in nodes.items():
        children[node["placement"]["parent"]].append(ref)
    author_order = {node["workflow"]: i for i, node in enumerate(payload["workflows"])}
    for parent, refs in children.items():
        refs.sort(key=lambda ref: (author_order[nodes[ref]["workflow"]], rank.get(ref, len(rank))) if parent is None else
                  (role_by_id.get(ref, {}).get("kind") == "delete", author_order[nodes[ref]["workflow"]],
                   rank.get(ref, len(rank))))
    for ref in reversed(list(children[None])):
        role = role_by_id.get(ref)
        if not role or role["kind"] != "delete":
            continue
        related = set(role["termination"]["creator_roles"])
        local_users = set(role["termination"]["related_users"]) - set(role["termination"]["cross_context_users"])
        related.update(r for r, node in nodes.items() if node["workflow"] in local_users
                       and role_by_id.get(r, {}).get("kind") != "delete")
        roots = {ancestors(r)[-1] for r in related} - {ref}
        positions = [children[None].index(r) for r in roots]
        if positions:
            children[None].remove(ref)
            last = max(children[None].index(r) for r in roots)
            children[None].insert(last + 1, ref)
    for ref, node in nodes.items():
        node["children"] = children[ref]
    forest = {"nodes": list(nodes.values()), "roots": children[None]}
    forest["display_rows"] = _display_references(forest, role_by_id, author_order)
    return forest


def _display_references(forest, roles, author_order):
    """One full occurrence per node, plus bounded source-local reference leaves.

    Display parents are layout choices, never new source-chain evidence. Keep
    them separate from the established parents used by _source_forest.
    """
    nodes = {node["id"]: node for node in forest["nodes"]}
    layout = []
    todo = list(reversed(forest["roots"]))
    while todo:
        ref = todo.pop()
        layout.append(ref)
        todo.extend(reversed(nodes[ref]["children"]))
    rank = {ref: i for i, ref in enumerate(layout)}
    parents = {ref: node["placement"]["parent"] for ref, node in nodes.items()}
    references = []
    distributed = set()

    def would_cycle(ref, parent):
        visited = {ref}
        while parent is not None:
            if parent in visited:
                return True
            visited.add(parent)
            parent = parents[parent]
        return False

    for ref in layout:
        placement = nodes[ref]["placement"]
        # Only distinct, unambiguous data pieces qualify. Alternative writers
        # of one read, missing source evidence, and SCCs keep their honest forest.
        if (placement["kind"] != "join" or placement["alternatives"]
                or placement["unknown_reads"] or placement["incomplete"]
                or placement["basis"] != "body_handoffs" or len(placement["sources"]) < 2):
            continue
        sources = sorted(set(placement["sources"]), key=rank.__getitem__)
        parent = next((source for source in sources if not would_cycle(ref, source)), None)
        if parent is None:
            continue
        parents[ref] = parent
        distributed.add(ref)
        # One leaf per source vertex, not per field, site, or descendant path.
        references.extend({"node": ref, "parent": source, "reference": True,
                           "conditional": source in placement["conditional_sources"],
                           "basis": "distinct_data_source"} for source in sources if source != parent)
    rows = [{"node": ref, "parent": parents[ref], "reference": False,
             "conditional": parents[ref] in nodes[ref]["placement"]["conditional_sources"],
             "basis": "source_layout" if ref in distributed else "forest"} for ref in layout]
    rows.extend(references)
    # Roots keep the established section order. At source branches references
    # share the authored-order tie-break and precede terminal deletion roles.
    rows.sort(key=lambda row: (rank[row["node"]],) if row["parent"] is None else
              (roles.get(row["node"], {}).get("kind") == "delete",
               author_order[nodes[row["node"]]["workflow"]], rank[row["node"]]))
    return rows


def _conditional_read(read):
    """Annotation only: known branch conditions or an exact missing-state catch.

    Unrecognized expressions are not called conditional. This predicate never
    participates in source selection or parent choice.
    """
    if any(c["kind"] in {"if", "short_circuit", "iteration"} for c in read["conditions"]):
        return True
    from .graphing import _parse
    from .local_expression_engine.core import (
        PipelineNode, StateReferenceNode, FilterApplicationNode, ListNode, LiteralNode, render_expression_text,
    )

    node, expression = _parse(read.get("expression") or "")
    if not isinstance(node, PipelineNode) or not isinstance(node.source, StateReferenceNode):
        return False
    address = read["address"]
    if node.source.state_role != address["role"] or list(node.source.fields) != address["fields"]:
        return False
    if render_expression_text(node.source.key_expression, source=expression) != address["key_expression"]:
        return False
    return any(isinstance(stage, FilterApplicationNode) and stage.name == "catch"
               and len(stage.arguments) == 2 and isinstance(stage.arguments[0], ListNode)
               and any(isinstance(item, LiteralNode) and item.value == "runtime.value.state_missing"
                       for item in stage.arguments[0].items) for stage in node.filters)
