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
    return {"roles": roles, "rows": rows, "reader_anchors": reader_anchors,
            "semantics": "Display roles share workflow identity; termination placement is visual, not execution order."}
