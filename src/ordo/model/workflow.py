"""Workflow orchestration models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .json import JSONObject, JSONValue


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
    run_with: JSONObject = field(default_factory=dict, kw_only=True)
    value: JSONValue | None = None
    state_set: JSONObject | None = None
    state_delete: str | None = None
    if_: str | None = field(default=None, metadata={"contract_name": "if"})
    register: str | None = None
    launcher: str | None = None
    resolved_run_path: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        forms = (
            self.operation is not None,
            self.run is not None,
            self.value is not None,
            self.state_set is not None,
            self.state_delete is not None,
        )
        if sum(forms) != 1:
            raise ValueError("Step must define exactly one of operation, run, value, state_set, or state_delete")

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped contract form."""

        if self.operation is not None:
            contract = {"name": self.name, **self.operation.to_contract()}
            if self.if_ is not None:
                contract["if"] = self.if_
            if self.register is not None:
                contract["register"] = self.register
            if self.launcher is not None:
                contract["launcher"] = self.launcher
            return contract
        if self.run is not None:
            contract = {"name": self.name, "run": self.run}
            if self.if_ is not None:
                contract["if"] = self.if_
            if self.run_with:
                contract["with"] = dict(self.run_with)
            return contract
        if self.value is not None:
            contract = {"name": self.name, "value": self.value}
            if self.if_ is not None:
                contract["if"] = self.if_
            if self.register is not None:
                contract["register"] = self.register
            return contract
        if self.state_set is not None:
            contract = {"name": self.name, "state_set": dict(self.state_set)}
            if self.if_ is not None:
                contract["if"] = self.if_
            return contract
        contract = {"name": self.name, "state_delete": self.state_delete}
        if self.if_ is not None:
            contract["if"] = self.if_
        return contract


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
    if_: str | None = field(default=None, metadata={"contract_name": "if"})
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
    inputs: JSONObject = field(default_factory=dict)
    declared_inputs: JSONObject = field(default_factory=dict)
    state_needs: JSONObject = field(default_factory=dict)
    state_bindings: JSONObject = field(default_factory=dict)
    states: JSONObject = field(default_factory=dict)
    step_results: JSONObject = field(default_factory=dict)
    blocks: tuple[WorkflowBlock, ...] = ()
    source_path: str | None = None
    launch_dir: str | None = None

    def __init__(
        self,
        *,
        version: int,
        workflow: str,
        inputs: JSONObject | None = None,
        declared_inputs: JSONObject | None = None,
        state_needs: JSONObject | None = None,
        state_bindings: JSONObject | None = None,
        states: JSONObject | None = None,
        step_results: JSONObject | None = None,
        blocks: tuple[WorkflowBlock, ...] = (),
        source_path: str | None = None,
        launch_dir: str | None = None,
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
        runtime_inputs = {} if inputs is None else dict(inputs)
        declared = {key: {} for key in runtime_inputs} if declared_inputs is None else dict(declared_inputs)
        object.__setattr__(self, "inputs", runtime_inputs)
        object.__setattr__(self, "declared_inputs", declared)
        object.__setattr__(self, "state_needs", {} if state_needs is None else dict(state_needs))
        object.__setattr__(self, "state_bindings", {} if state_bindings is None else dict(state_bindings))
        object.__setattr__(self, "states", {} if states is None else dict(states))
        object.__setattr__(self, "step_results", {} if step_results is None else dict(step_results))
        object.__setattr__(self, "blocks", normalized_blocks)
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "launch_dir", launch_dir)

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
            "inputs": dict(self.declared_inputs),
            "state_needs": dict(self.state_needs),
            "blocks": [block.to_contract() for block in self.blocks],
        }
