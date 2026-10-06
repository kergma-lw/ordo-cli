"""Workflow orchestration models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .json import JSONObject, JSONValue


def normalize_workflow_input_declaration(name: str, declaration: JSONValue) -> tuple[JSONObject, bool, JSONValue | None]:
    """Normalize one authored workflow input declaration.

    Returns the normalized declaration metadata, whether a default exists, and the
    default value when present.
    """

    normalized: JSONObject = {}

    if isinstance(declaration, dict):
        description = declaration.get("description")
        if isinstance(description, str):
            normalized["description"] = description
        hint = declaration.get("hint")
        if isinstance(hint, str):
            normalized["hint"] = hint
        allowed_values = declaration.get("allowed_values")
        if isinstance(allowed_values, list):
            normalized["allowed_values"] = list(allowed_values)

        has_default = "default" in declaration
        if has_default:
            normalized["default"] = declaration.get("default")

        required_raw = declaration.get("required")
        required = False if has_default else True
        if isinstance(required_raw, bool):
            required = required_raw
        normalized["required"] = required
        return normalized, has_default, declaration.get("default")

    normalized["required"] = False
    normalized["default"] = declaration
    return normalized, True, declaration


def workflow_input_has_default(declaration: object) -> bool:
    """Return whether one normalized workflow input declaration has a default."""

    return isinstance(declaration, dict) and "default" in declaration


def workflow_input_required(declaration: object) -> bool:
    """Return whether one workflow input declaration is activation-required."""

    if not isinstance(declaration, dict):
        return True
    required = declaration.get("required")
    if isinstance(required, bool):
        return required
    return not workflow_input_has_default(declaration)

GATE_REGISTER_SPLIT_RECOMMENDATION = (
    "Split this into a standalone gate checkpoint step followed by a separate step that declares 'register'."
)

GATE_REGISTER_CONFLICT_MESSAGE = (
    "Step must not declare both 'gate' and 'register'. "
    + GATE_REGISTER_SPLIT_RECOMMENDATION
)


@dataclass(frozen=True, slots=True)
class OperationRef:
    """Stable reference to a public connector operation."""

    uses: str
    with_: JSONObject = field(default_factory=dict, kw_only=True)

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped contract form."""

        return {"uses": self.uses, "with": dict(self.with_)}


@dataclass(frozen=True, slots=True)
class Guard:
    """Pre-execution check with no intended side effects."""

    operation: OperationRef | None = None
    expr: str | None = None

    def __post_init__(self) -> None:
        has_operation = self.operation is not None
        has_expr = self.expr is not None
        if has_operation == has_expr:
            raise ValueError("Guard must define exactly one of operation or expr")

    @property
    def reference(self) -> str:
        if self.operation is not None:
            return self.operation.uses
        return self.expr or "<unknown-guard>"

    def to_contract(self) -> JSONValue:
        """Return the stable JSON-shaped contract form."""

        if self.operation is not None:
            return self.operation.to_contract()
        return self.expr


@dataclass(frozen=True, slots=True)
class Step:
    """Ordered effectful workflow step."""

    name: str
    operation: OperationRef | None = None
    run: str | None = None
    steps: tuple[Step, ...] | None = None
    for_each: JSONValue | None = None
    run_with: JSONObject = field(default_factory=dict, kw_only=True)
    run_inputs: JSONObject = field(default_factory=dict, kw_only=True)
    run_state_bindings: JSONObject = field(default_factory=dict, kw_only=True)
    run_states: JSONObject = field(default_factory=dict, kw_only=True)
    profile_switch: JSONValue | None = None
    value: JSONValue | None = None
    result: JSONValue | None = None
    publish: JSONValue | None = None
    state_set: JSONObject | None = None
    state_delete: str | None = None
    if_: JSONValue | None = field(default=None, metadata={"contract_name": "if"})
    gate: JSONValue | None = None
    gate_on_fail: JSONValue | None = None
    register: str | None = None
    launcher: str | None = None
    resolved_run_path: str | None = field(default=None, kw_only=True)
    run_origin: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        forms = (
            self.operation is not None,
            self.run is not None or self.steps is not None,
            self.profile_switch is not None,
            self.value is not None,
            self.result is not None,
            self.publish is not None,
            self.state_set is not None,
            self.state_delete is not None,
        )
        if self.run is not None and self.steps is not None:
            raise ValueError("Step must not define both run and steps invocation bodies")
        if self.gate is not None and self.register is not None:
            raise ValueError(GATE_REGISTER_CONFLICT_MESSAGE)
        form_count = sum(forms)
        if form_count == 0 and self.gate is not None:
            return
        if form_count != 1:
            raise ValueError("Step must define exactly one of operation, run, steps, profile_switch, value, result, publish, state_set, or state_delete")

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped contract form."""

        def apply_controls(contract: JSONObject) -> JSONObject:
            if self.if_ is not None:
                contract["if"] = self.if_
            if self.gate is not None:
                gate_value = self.gate
                if self.gate_on_fail is not None and isinstance(gate_value, dict):
                    gate_value = {**gate_value, "on_fail": self.gate_on_fail}
                contract["gate"] = gate_value
            return contract

        if self.operation is not None:
            contract = apply_controls({"name": self.name, **self.operation.to_contract()})
            if self.register is not None:
                contract["register"] = self.register
            if self.launcher is not None:
                contract["launcher"] = self.launcher
            return contract
        if self.run is not None:
            contract = apply_controls({"name": self.name, "run": self.run})
            if self.run_with:
                contract["with"] = dict(self.run_with)
            if self.for_each is not None:
                contract["for_each"] = self.for_each
            if self.register is not None:
                contract["register"] = self.register
            return contract
        if self.steps is not None:
            contract = apply_controls({"name": self.name, "steps": [step.to_contract() for step in self.steps]})
            if self.for_each is not None:
                contract["for_each"] = self.for_each
            if self.register is not None:
                contract["register"] = self.register
            return contract
        if self.profile_switch is not None:
            return apply_controls({"name": self.name, "profile_switch": self.profile_switch})
        if self.value is not None:
            contract = apply_controls({"name": self.name, "value": self.value})
            if self.register is not None:
                contract["register"] = self.register
            return contract
        if self.result is not None:
            return apply_controls({"name": self.name, "result": self.result})
        if self.publish is not None:
            return apply_controls({"name": self.name, "publish": self.publish})
        if self.state_set is not None:
            return apply_controls({"name": self.name, "state_set": dict(self.state_set)})
        if self.state_delete is not None:
            return apply_controls({"name": self.name, "state_delete": self.state_delete})
        return apply_controls({"name": self.name})


@dataclass(frozen=True, slots=True)
class GuardBlock:
    """Ordered workflow block containing only guards."""

    guards: tuple[Guard, ...] = ()

    def to_contract(self) -> JSONObject:
        return {"guards": [guard.to_contract() for guard in self.guards]}


@dataclass(frozen=True, slots=True)
class StepBlock:
    """Ordered workflow block containing only steps."""

    steps: tuple[Step, ...] = ()

    def to_contract(self) -> JSONObject:
        return {"steps": [step.to_contract() for step in self.steps]}


@dataclass(frozen=True, slots=True)
class RunBlock:
    """Ordered workflow block containing one reusable fragment run."""

    run: str
    with_: JSONObject = field(default_factory=dict, kw_only=True)
    if_: JSONValue | None = field(default=None, metadata={"contract_name": "if"})
    resolved_path: str | None = field(default=None, kw_only=True)

    def to_contract(self) -> JSONObject:
        contract: JSONObject = {"run": self.run}
        if self.if_ is not None:
            contract["if"] = self.if_
        if self.with_:
            contract["with"] = dict(self.with_)
        return contract


WorkflowBlock = GuardBlock | StepBlock | RunBlock


@dataclass(frozen=True, slots=True, init=False)
class Workflow:
    """Declarative orchestration model loaded from author-facing data."""

    version: int
    workflow: str
    profile: str | None = None
    inputs: JSONObject = field(default_factory=dict)
    declared_inputs: JSONObject = field(default_factory=dict)
    explicit_input_keys: tuple[str, ...] = ()
    protected_input_keys: tuple[str, ...] = ()
    let_bindings: dict[str, str] = field(default_factory=dict)
    state_needs: JSONObject = field(default_factory=dict)
    state_bindings: JSONObject = field(default_factory=dict)
    states: JSONObject = field(default_factory=dict)
    step_results: JSONObject = field(default_factory=dict)
    connector_contexts: JSONObject = field(default_factory=dict)
    blocks: tuple[WorkflowBlock, ...] = ()
    source_path: str | None = None
    launch_dir: str | None = None
    launch_profile_name: str | None = None
    launch_profile_source: str | None = None
    playbook_owned_pre_run: bool = False

    def __init__(
        self,
        *,
        version: int,
        workflow: str,
        profile: str | None = None,
        inputs: JSONObject | None = None,
        declared_inputs: JSONObject | None = None,
        explicit_input_keys: tuple[str, ...] = (),
        protected_input_keys: tuple[str, ...] = (),
        let_bindings: dict[str, str] | None = None,
        state_needs: JSONObject | None = None,
        state_bindings: JSONObject | None = None,
        states: JSONObject | None = None,
        step_results: JSONObject | None = None,
        connector_contexts: JSONObject | None = None,
        blocks: tuple[WorkflowBlock, ...] = (),
        source_path: str | None = None,
        launch_dir: str | None = None,
        launch_profile_name: str | None = None,
        launch_profile_source: str | None = None,
        playbook_owned_pre_run: bool = False,
        guards: tuple[Guard, ...] | None = None,
        steps: tuple[Step, ...] | None = None,
    ) -> None:
        if blocks and (guards is not None or steps is not None):
            raise ValueError("Workflow must define either blocks or legacy guards/steps, not both")

        normalized_blocks = tuple(blocks)
        if not normalized_blocks and (guards is not None or steps is not None):
            legacy_blocks: list[WorkflowBlock] = []
            if guards is not None:
                legacy_blocks.append(GuardBlock(guards=tuple(guards)))
            if steps is not None:
                legacy_blocks.append(StepBlock(steps=tuple(steps)))
            normalized_blocks = tuple(legacy_blocks)

        object.__setattr__(self, "version", version)
        object.__setattr__(self, "workflow", workflow)
        object.__setattr__(self, "profile", profile)
        runtime_inputs = {} if inputs is None else dict(inputs)
        if declared_inputs is None:
            declared = {}
            for key, value in runtime_inputs.items():
                if not isinstance(key, str):
                    continue
                normalized, _, _ = normalize_workflow_input_declaration(key, value)
                declared[key] = normalized
        else:
            declared = dict(declared_inputs)
        object.__setattr__(self, "inputs", runtime_inputs)
        object.__setattr__(self, "declared_inputs", declared)
        object.__setattr__(self, "explicit_input_keys", tuple(explicit_input_keys))
        object.__setattr__(self, "protected_input_keys", tuple(protected_input_keys))
        object.__setattr__(self, "let_bindings", {} if let_bindings is None else dict(let_bindings))
        object.__setattr__(self, "state_needs", {} if state_needs is None else dict(state_needs))
        object.__setattr__(self, "state_bindings", {} if state_bindings is None else dict(state_bindings))
        object.__setattr__(self, "states", {} if states is None else dict(states))
        object.__setattr__(self, "step_results", {} if step_results is None else dict(step_results))
        object.__setattr__(self, "connector_contexts", {} if connector_contexts is None else dict(connector_contexts))
        object.__setattr__(self, "blocks", normalized_blocks)
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "launch_dir", launch_dir)
        object.__setattr__(self, "launch_profile_name", launch_profile_name)
        object.__setattr__(self, "launch_profile_source", launch_profile_source)
        object.__setattr__(self, "playbook_owned_pre_run", playbook_owned_pre_run)

    @property
    def guards(self) -> tuple[Guard, ...]:
        return tuple(guard for block in self.blocks if isinstance(block, GuardBlock) for guard in block.guards)

    @property
    def steps(self) -> tuple[Step, ...]:
        return tuple(step for block in self.blocks if isinstance(block, StepBlock) for step in block.steps)

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped workflow contract."""

        return {
            "version": self.version,
            "workflow": self.workflow,
            **({"profile": self.profile} if self.profile is not None else {}),
            "inputs": dict(self.declared_inputs),
            "let": dict(self.let_bindings),
            "state_needs": dict(self.state_needs),
            "blocks": [block.to_contract() for block in self.blocks],
        }
