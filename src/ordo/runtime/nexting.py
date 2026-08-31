"""Recommendation logic for no-argument playbook-level next mode."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import RuntimeResult, RuntimeStatus


@dataclass(frozen=True, slots=True)
class NextCandidate:
    """Rankable next-workflow candidate built from activation and runtime evidence."""

    workflow: str
    description: str | None = None
    workflow_category: str | None = None
    when: str | None = None
    working_directory: str | None = None
    candidate_class: str = "weak_match"
    score: int = 0
    allowed: bool = False
    reason_category: str | None = None
    matched_guard_count: int = 0
    relevant_guard_count: int = 0
    evaluated_guard_count: int = 0
    full_evaluability: bool = False
    blockers: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    ranking_factors: tuple[dict[str, object], ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_contract(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "description": self.description,
            "category": self.workflow_category,
            "when": self.when,
            "working_directory": self.working_directory,
            "candidate_class": self.candidate_class,
            "score": self.score,
            "allowed": self.allowed,
            "reason_category": self.reason_category,
            "matched_guard_count": self.matched_guard_count,
            "relevant_guard_count": self.relevant_guard_count,
            "evaluated_guard_count": self.evaluated_guard_count,
            "full_evaluability": self.full_evaluability,
            "blockers": list(self.blockers),
            "missing_inputs": list(self.missing_inputs),
            "ranking_factors": [dict(item) for item in self.ranking_factors],
            "diagnostics": [diagnostic.to_contract() for diagnostic in self.diagnostics],
        }


def build_next_candidate(
    *,
    workflow: str,
    description: str | None,
    workflow_category: str | None,
    when: str | None,
    working_directory: str | None,
    runtime_result: RuntimeResult | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
) -> NextCandidate:
    """Build one candidate from either runtime evaluation or activation diagnostics."""

    if runtime_result is None:
        return _candidate_from_diagnostics(
            workflow=workflow,
            description=description,
            workflow_category=workflow_category,
            when=when,
            working_directory=working_directory,
            diagnostics=diagnostics,
        )
    return _candidate_from_runtime_result(
        workflow=workflow,
        description=description,
        workflow_category=workflow_category,
        when=when,
        working_directory=working_directory,
        result=runtime_result,
    )


def rank_next_candidates(
    candidates: list[NextCandidate],
    *,
    requested_profile: str | None,
    input_override_keys: list[str],
    playbook_path: str,
) -> dict[str, object]:
    """Build the public next-mode payload from ranked candidates."""

    ordered = sorted(
        candidates,
        key=lambda item: (
            -item.score,
            0 if item.candidate_class == "ready_now" else 1,
            item.workflow,
        ),
    )
    best = ordered[0] if ordered else None
    alternatives = ordered[1:4] if len(ordered) > 1 else []
    strength = "none"
    uncertainty: dict[str, object] | None = None
    if best is not None:
        strength = _recommendation_strength(best, alternatives)
        if best.candidate_class != "ready_now":
            uncertainty = {
                "kind": "no_ready_now_candidate",
                "message": "No workflow is runnable now; returning the strongest near-term candidate from current evidence.",
            }
        elif alternatives and abs(best.score - alternatives[0].score) < 40:
            uncertainty = {
                "kind": "competitive_candidates",
                "message": "Multiple workflows are materially close; review nearby alternatives before choosing automatically.",
            }
    else:
        uncertainty = {
            "kind": "no_candidates",
            "message": "No visible workflow candidate could be analyzed from the current playbook context.",
        }

    return {
        "mode": "next",
        "status": "ok",
        "playbook": playbook_path,
        "profile": requested_profile,
        "scope": "playbook",
        "current_context": {
            "requested_profile": requested_profile,
            "input_override_keys": list(input_override_keys),
        },
        "ready_now_available": best is not None and best.candidate_class == "ready_now",
        "recommendation_strength": strength,
        "best_candidate": None if best is None else best.to_contract(),
        "alternatives": [item.to_contract() for item in alternatives],
        "candidates": [item.to_contract() for item in ordered],
        "uncertainty": uncertainty,
    }


def _candidate_from_runtime_result(
    *,
    workflow: str,
    description: str | None,
    workflow_category: str | None,
    when: str | None,
    working_directory: str | None,
    result: RuntimeResult,
) -> NextCandidate:
    explanation = result.outputs.get("explanation") if isinstance(result.outputs.get("explanation"), dict) else {}
    allowed = bool(explanation.get("allowed", result.outputs.get("can_execute", False)))
    reason_category = explanation.get("category") if isinstance(explanation.get("category"), str) else None
    blockers = tuple(item for item in explanation.get("blockers", []) if isinstance(item, str))
    matched_guard_count, relevant_guard_count, evaluated_guard_count = _guard_counts(result)
    missing_inputs = _missing_inputs_from_diagnostics(result.diagnostics)
    analysis_complete = bool(result.outputs.get("analysis_complete", True))
    full_evaluability = analysis_complete and evaluated_guard_count >= relevant_guard_count and not missing_inputs
    candidate_class = _classify_runtime_candidate(
        result=result,
        allowed=allowed,
        reason_category=reason_category,
        blockers=blockers,
        matched_guard_count=matched_guard_count,
        relevant_guard_count=relevant_guard_count,
        missing_inputs=missing_inputs,
    )
    score, ranking_factors = _score_candidate(
        candidate_class=candidate_class,
        matched_guard_count=matched_guard_count,
        relevant_guard_count=relevant_guard_count,
        full_evaluability=full_evaluability,
        blockers=blockers,
        missing_inputs=missing_inputs,
        reason_category=reason_category,
    )
    return NextCandidate(
        workflow=workflow,
        description=description,
        workflow_category=workflow_category,
        when=when,
        working_directory=working_directory,
        candidate_class=candidate_class,
        score=score,
        allowed=allowed,
        reason_category=reason_category,
        matched_guard_count=matched_guard_count,
        relevant_guard_count=relevant_guard_count,
        evaluated_guard_count=evaluated_guard_count,
        full_evaluability=full_evaluability,
        blockers=blockers,
        missing_inputs=missing_inputs,
        ranking_factors=tuple(ranking_factors),
        diagnostics=result.diagnostics,
    )


def _candidate_from_diagnostics(
    *,
    workflow: str,
    description: str | None,
    workflow_category: str | None,
    when: str | None,
    working_directory: str | None,
    diagnostics: tuple[Diagnostic, ...],
) -> NextCandidate:
    missing_inputs = _missing_inputs_from_diagnostics(diagnostics)
    if missing_inputs:
        candidate_class = "awaiting_input"
        reason_category = "missing_input"
    else:
        candidate_class = "not_evaluable_now"
        reason_category = _diagnostic_reason_category(diagnostics)
    score, ranking_factors = _score_candidate(
        candidate_class=candidate_class,
        matched_guard_count=0,
        relevant_guard_count=0,
        full_evaluability=False,
        blockers=tuple(diagnostic.code for diagnostic in diagnostics),
        missing_inputs=missing_inputs,
        reason_category=reason_category,
    )
    return NextCandidate(
        workflow=workflow,
        description=description,
        workflow_category=workflow_category,
        when=when,
        working_directory=working_directory,
        candidate_class=candidate_class,
        score=score,
        allowed=False,
        reason_category=reason_category,
        matched_guard_count=0,
        relevant_guard_count=0,
        evaluated_guard_count=0,
        full_evaluability=False,
        blockers=tuple(diagnostic.code for diagnostic in diagnostics),
        missing_inputs=missing_inputs,
        ranking_factors=tuple(ranking_factors),
        diagnostics=diagnostics,
    )


def _classify_runtime_candidate(
    *,
    result: RuntimeResult,
    allowed: bool,
    reason_category: str | None,
    blockers: tuple[str, ...],
    matched_guard_count: int,
    relevant_guard_count: int,
    missing_inputs: tuple[str, ...],
) -> str:
    if allowed and result.status is RuntimeStatus.OK:
        return "ready_now"
    if missing_inputs:
        return "awaiting_input"
    if result.status in {RuntimeStatus.VALIDATION_ERROR, RuntimeStatus.RESOLUTION_ERROR}:
        return "not_evaluable_now"
    if reason_category in {"workflow_profile", "bootstrap", "preflight_step", "incomplete", "validation", "resolution"}:
        return "not_evaluable_now"
    if relevant_guard_count > 0 and blockers:
        if matched_guard_count == 0:
            return "weak_match"
        if matched_guard_count * 2 < relevant_guard_count:
            return "weak_match"
    return "near_ready"


def _score_candidate(
    *,
    candidate_class: str,
    matched_guard_count: int,
    relevant_guard_count: int,
    full_evaluability: bool,
    blockers: tuple[str, ...],
    missing_inputs: tuple[str, ...],
    reason_category: str | None,
) -> tuple[int, list[dict[str, object]]]:
    base_scores = {
        "ready_now": 1000,
        "near_ready": 700,
        "awaiting_input": 450,
        "not_evaluable_now": 300,
        "weak_match": 100,
    }
    class_messages = {
        "ready_now": "workflow is runnable now",
        "near_ready": "workflow is structurally close to runnable now",
        "awaiting_input": "workflow is relevant but still needs caller input",
        "not_evaluable_now": "workflow could not be established safely enough from current evidence",
        "weak_match": "current context does not strongly match this workflow's guards",
    }
    score = base_scores[candidate_class]
    ratio_points = 0 if relevant_guard_count <= 0 else int((matched_guard_count / relevant_guard_count) * 100)
    factors: list[dict[str, object]] = [
        {
            "factor": "candidate_class",
            "effect": "bonus",
            "value": base_scores[candidate_class],
            "why": class_messages[candidate_class],
        }
    ]
    if matched_guard_count:
        guard_points = matched_guard_count * 20
        score += guard_points
        factors.append(
            {
                "factor": "matched_guard_count",
                "effect": "bonus",
                "value": guard_points,
                "why": f"{matched_guard_count} guard(s) already match the current context",
            }
        )
    if ratio_points:
        score += ratio_points
        factors.append(
            {
                "factor": "matched_guard_ratio",
                "effect": "bonus",
                "value": ratio_points,
                "why": f"{matched_guard_count} of {relevant_guard_count} relevant guard(s) currently match",
            }
        )
    if full_evaluability:
        score += 40
        factors.append(
            {
                "factor": "full_evaluability",
                "effect": "bonus",
                "value": 40,
                "why": "runtime could evaluate the workflow from current read-only evidence without major unknowns",
            }
        )
    if blockers:
        penalty = len(blockers) * 60
        score -= penalty
        factors.append(
            {
                "factor": "blockers",
                "effect": "penalty",
                "value": penalty,
                "why": f"{len(blockers)} blocker(s) still prevent immediate execution",
            }
        )
    if missing_inputs:
        penalty = len(missing_inputs) * 80
        score -= penalty
        factors.append(
            {
                "factor": "missing_inputs",
                "effect": "penalty",
                "value": penalty,
                "why": f"missing required input(s): {', '.join(missing_inputs)}",
            }
        )
    if candidate_class == "not_evaluable_now":
        score -= 50
        factors.append(
            {
                "factor": "non_evaluable_state",
                "effect": "penalty",
                "value": 50,
                "why": "runtime could not establish enough read-only evidence for a stronger recommendation",
            }
        )
    if reason_category in {"workflow_profile", "validation", "resolution"}:
        score -= 40
        factors.append(
            {
                "factor": "contract_issue",
                "effect": "penalty",
                "value": 40,
                "why": f"workflow is currently held back by {reason_category.replace('_', ' ')} issues",
            }
        )
    return score, factors


def _guard_counts(result: RuntimeResult) -> tuple[int, int, int]:
    decision = result.preflight_decision
    if decision is not None:
        relevant = [item for item in decision.guard_nodes if item.relevant]
        matched = [item for item in relevant if item.status == "passed"]
        evaluated = [item for item in relevant if item.evaluated]
        return len(matched), len(relevant), len(evaluated)
    relevant_guard_count = result.outputs.get("relevant_guard_count")
    evaluated_guard_count = result.outputs.get("evaluated_relevant_guard_count")
    guard_coverage = [item for item in result.outputs.get("guard_coverage", []) if isinstance(item, dict)]
    matched_guard_count = len([item for item in guard_coverage if item.get("status") == "passed"])
    return (
        matched_guard_count,
        relevant_guard_count if isinstance(relevant_guard_count, int) else len(guard_coverage),
        evaluated_guard_count if isinstance(evaluated_guard_count, int) else len([item for item in guard_coverage if item.get("evaluated")]),
    )


def _missing_inputs_from_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    names: list[str] = []
    for diagnostic in diagnostics:
        if diagnostic.code != "playbook.workflow.input_missing":
            continue
        value = diagnostic.details.get("input")
        if isinstance(value, str) and value not in names:
            names.append(value)
    return tuple(names)


def _diagnostic_reason_category(diagnostics: tuple[Diagnostic, ...]) -> str:
    if any(item.code == "playbook.profile.missing" for item in diagnostics):
        return "workflow_profile"
    if any(item.code == "playbook.workflow.input_unknown" for item in diagnostics):
        return "input_unknown"
    if diagnostics:
        first = diagnostics[0].code
        if first.startswith("playbook.workflow.working_directory"):
            return "working_directory"
        if first.startswith("playbook.workflow"):
            return "activation"
        if first.startswith("playbook.profile"):
            return "workflow_profile"
    return "activation"


def _recommendation_strength(best: NextCandidate, alternatives: list[NextCandidate]) -> str:
    if best.candidate_class != "ready_now":
        return "weak"
    if not alternatives:
        return "strong"
    if abs(best.score - alternatives[0].score) < 40:
        return "competitive"
    return "strong"
