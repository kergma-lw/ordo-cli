"""Parametric graph relations, deliberately separate from storage identity.

Families are declaration-owned. A matching spelling is neither a shared input
value nor evidence that two independent store declarations are one family.
"""


def structural_relation(left, right, concrete=None):
    a, b = left["address"], right["address"]
    family_a, family_b = a.get("family"), b.get("family")
    if not family_a or not family_b or family_a["id"] != family_b["id"]:
        return None
    x, y = a["fields"], b["fields"]
    if x[:len(y)] != y and y[:len(x)] != x:
        return None
    sa, sb = a["selector"], b["selector"]
    if sa["kind"] == sb["kind"] == "fixed" and sa["value"] != sb["value"]:
        return None
    # Closed authored domains can be disjoint. Profile-provided values instead
    # describe concrete instances of the profile parameter in this projection.
    da = sa.get("closed_domain")
    db = sb.get("closed_domain")
    if da is not None and db is not None and not set(da).intersection(db):
        return None
    different_files = a["store"] is not None and b["store"] is not None and a["store"] != b["store"]
    if different_files and family_a["instance_kind"] == family_b["instance_kind"] == "fixed":
        return None
    requirements = []
    fixed_equal = sa["kind"] == sb["kind"] == "fixed"
    correspondence = "fixed_equal" if fixed_equal else (
        "shared_origin_parameter" if sa["origin"] == sb["origin"] else "independent_parameters")
    if not fixed_equal:
        requirements.append({"predicate": "selector_equal", "left": left["id"], "right": right["id"]})
    if a["store"] is None or b["store"] is None or different_files:
        requirements.append({"predicate": "same_family_instance", "family": family_a["id"],
                             "left": left["id"], "right": right["id"]})
    relation = "exact" if x == y else "ancestor" if y[:len(x)] == x else "descendant"
    if relation != "exact" and left["kind"] == "set":
        requirements.append({"predicate": "read_shape_available", "read": right["id"], "fields": list(y)})
    return {
        "relation_category": "state_family_parametric" if requirements else "state_family_fixed",
        "family": family_a["id"], "selector_correspondence": correspondence,
        "requirements": requirements, "field_relation": relation,
        "empty_parent_prune": left["kind"] == "delete" and relation == "descendant",
        "concrete_address_identity": concrete["address_identity"] if concrete else "disjoint",
        "execution": "possible",
    }
