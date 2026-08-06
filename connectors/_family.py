"""Family-local connector assembly helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from importlib import import_module
from pkgutil import iter_modules, walk_packages
from types import ModuleType
from typing import TYPE_CHECKING

from ordo.model.connector import Connector, ConnectorBootstrap, OperationContract
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Workflow

if TYPE_CHECKING:
    from ordo.plugin_sdk import PublishedBootstrap, PublishedOperation
    from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation

ProbeHandler = Callable[["ResolvedOperation | ResolvedExpressionProbe", Workflow], OperationResult]
ActionHandler = Callable[["ResolvedOperation", Workflow], OperationResult]
BootstrapHandler = Callable[[], OperationResult]


@dataclass(frozen=True, slots=True)
class AssembledFamily:
    connector: Connector
    probe_handlers: dict[str, ProbeHandler]
    action_handlers: dict[str, ActionHandler]
    bootstrap_handler: BootstrapHandler | None


def assemble_family(*, package_name: str, namespace: str, bootstrap: ConnectorBootstrap) -> AssembledFamily:
    probe_handlers: dict[str, ProbeHandler] = {}
    action_handlers: dict[str, ActionHandler] = {}
    operations: list[OperationContract] = []
    bootstrap_handler = _load_bootstrap_handler(package_name, namespace=namespace)

    for operation in _load_operations(package_name=f"{package_name}.probes", kind="probe"):
        operations.append(operation.contract)
        if operation.handler is not None:
            probe_handlers[operation.contract.name] = operation.handler

    for operation in _load_operations(package_name=f"{package_name}.actions", kind="action"):
        operations.append(operation.contract)
        if operation.handler is not None:
            action_handlers[operation.contract.name] = operation.handler

    operations.sort(key=lambda contract: contract.name)

    return AssembledFamily(
        connector=Connector(
            namespace=namespace,
            bootstrap=bootstrap,
            operations=tuple(operations),
        ),
        probe_handlers=probe_handlers,
        action_handlers=action_handlers,
        bootstrap_handler=bootstrap_handler,
    )


def discover_family_modules() -> tuple[ModuleType, ...]:
    package = import_module("connectors")
    modules: list[tuple[int, str, ModuleType]] = []

    for module_info in iter_modules(package.__path__, f"{package.__name__}."):
        if not module_info.ispkg:
            continue
        short_name = module_info.name.rsplit(".", 1)[-1]
        if short_name.startswith("_"):
            continue

        module = import_module(module_info.name)
        if not hasattr(module, "get_connector"):
            continue

        modules.append((int(getattr(module, "ORDER", 1000)), short_name, module))

    modules.sort(key=lambda item: (item[0], item[1]))
    return tuple(module for _order, _short_name, module in modules)


@dataclass(frozen=True, slots=True)
class _LoadedOperation:
    contract: OperationContract
    handler: ProbeHandler | ActionHandler | None


def _load_operations(*, package_name: str, kind: str) -> Iterator[_LoadedOperation]:
    try:
        package = import_module(package_name)
    except ModuleNotFoundError:
        return

    for module_name in walk_packages(package.__path__, f"{package.__name__}."):
        module = import_module(module_name.name)
        published = _load_published_operation(module)
        if published is None:
            continue
        if published.kind != kind:
            message = f"Operation module '{module.__name__}' declared kind '{published.kind}', expected '{kind}'"
            raise ValueError(message)
        yield _LoadedOperation(
            contract=_contract_from_published(published, package_name=package_name),
            handler=_adapt_published_handler(published=published, package_name=package_name),
        )


def _load_published_operation(module: ModuleType) -> "PublishedOperation | None":
    from ordo.plugin_sdk import PublishedOperation

    info = getattr(module, "info", None)
    if info is None:
        return None
    published = info()
    if not isinstance(published, PublishedOperation):
        message = f"Operation module '{module.__name__}' returned unsupported publication type '{type(published).__name__}'"
        raise TypeError(message)
    return published


def _load_published_bootstrap(module: ModuleType) -> "PublishedBootstrap | None":
    from ordo.plugin_sdk import PublishedBootstrap

    info = getattr(module, "info", None)
    if info is None:
        return None
    published = info()
    if not isinstance(published, PublishedBootstrap):
        return None
    return published


def _contract_from_published(published: "PublishedOperation", *, package_name: str) -> OperationContract:
    family_package = package_name.rsplit(".", 1)[0]
    namespace = family_package.rsplit(".", 1)[-1]
    reference = f"{namespace}.{published.name}"
    return OperationContract(
        name=published.name,
        kind=published.kind,
        summary=published.summary or f"{published.kind.capitalize()} operation '{reference}'",
        inputs=dict(published.inputs),
        prerequisites=published.prerequisites,
        effects=published.effects,
        outputs=dict(published.outputs),
        failure_modes=published.failure_modes,
        tags=published.tags or (namespace, published.kind),
        examples=published.examples or ({"reference": reference, "inputs": dict(published.inputs)},),
        maturity=published.maturity,
        deprecated=published.deprecated,
        replaced_by=published.replaced_by,
        invalidates_observations=published.invalidates_observations,
        preflight_observations=published.preflight_observations,
    )


def _load_bootstrap_handler(package_name: str, *, namespace: str, raw_connector_input: dict[str, object] | None = None) -> BootstrapHandler | None:
    from ordo.plugin_sdk import BootstrapContext, MappedBootstrapError, PublishedBootstrap, adapt_bootstrap, bootstrap_ok

    bootstrap_module = import_module(f"{package_name}.bootstrap")
    published = _load_published_bootstrap(bootstrap_module)
    if published is None or published.handler is None:
        return None

    def evaluate() -> OperationResult:
        try:
            return adapt_bootstrap(published.handler(BootstrapContext(namespace=namespace, family_input={} if raw_connector_input is None else raw_connector_input)))
        except MappedBootstrapError as exc:
            return adapt_bootstrap(exc.outcome)

    return evaluate


def _evaluate_bootstrap(*, package_name: str, namespace: str, raw_connector_input: dict[str, object] | None = None) -> OperationResult:
    from ordo.plugin_sdk import adapt_bootstrap, bootstrap_ok

    bootstrap_module = import_module(f"{package_name}.bootstrap")
    bootstrap_contract = getattr(bootstrap_module, "BOOTSTRAP")
    published = _load_published_bootstrap(bootstrap_module)
    if published is None or published.handler is None:
        return adapt_bootstrap(
            bootstrap_ok(
                summary="Bootstrap metadata available",
                context={field: None for field in bootstrap_contract.context_fields},
            )
        )
    handler = _load_bootstrap_handler(package_name, namespace=namespace, raw_connector_input=raw_connector_input)
    if handler is None:
        return adapt_bootstrap(
            bootstrap_ok(
                summary="Bootstrap metadata available",
                context={field: None for field in bootstrap_contract.context_fields},
            )
        )
    return handler()


def _adapt_published_handler(*, published: "PublishedOperation", package_name: str) -> ProbeHandler | ActionHandler:
    from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, _bootstrap_from_runtime_result, adapt_outcome

    family_package = package_name.rsplit(".", 1)[0]
    namespace = family_package.rsplit(".", 1)[-1]

    def handler(resolved: "ResolvedOperation | ResolvedExpressionProbe", workflow: Workflow) -> OperationResult:
        def caller(name: str, inputs: dict[str, object] | None):
            from ordo.plugin_sdk import _outcome_from_runtime_result
            from ordo.runtime.resolution import ResolvedOperation

            full_name = name if "." in name else f"{namespace}.{name}"
            if inputs not in (None, {}):
                raise MappedOutcomeError(
                    OperationOutcome(
                        status="execution_error",
                        summary=f"Explicit operation dependency '{full_name}' does not yet support local input overrides",
                    )
                )

            family_module = import_module(family_package)
            connector = family_module.get_connector()
            short_name = full_name.rsplit(".", 1)[-1]
            operation = next((candidate for candidate in connector.operations if candidate.name == short_name), None)
            if operation is None:
                raise MappedOutcomeError(
                    OperationOutcome(
                        status="execution_error",
                        summary=f"Explicit operation dependency '{full_name}' could not be resolved",
                    )
                )

            dependency_handler = (
                family_module.get_probe_handler(short_name)
                if operation.kind == "probe"
                else family_module.get_action_handler(short_name)
            )
            if dependency_handler is None:
                raise MappedOutcomeError(
                    OperationOutcome(
                        status="execution_error",
                        summary=f"Explicit operation dependency '{full_name}' does not have a concrete handler",
                    )
                )

            dependency_resolved = ResolvedOperation(
                reference=full_name,
                connector_namespace=namespace,
                operation=operation,
                source=getattr(resolved, "source", "public"),
                declared_with={},
            )
            return _outcome_from_runtime_result(dependency_handler(dependency_resolved, workflow))

        raw_connector_input = workflow.connector_contexts.get(namespace)
        normalized_raw_connector_input = dict(raw_connector_input) if isinstance(raw_connector_input, dict) else None
        bootstrap_result = _evaluate_bootstrap(
            package_name=family_package,
            namespace=namespace,
            raw_connector_input=normalized_raw_connector_input,
        )
        if bootstrap_result.status != "ok":
            return _attach_bootstrap_metadata(
                bootstrap_result,
                namespace=namespace,
                bootstrap_status=bootstrap_result.status,
                bootstrap_context=bootstrap_result.outputs,
            )

        ctx = OperationContext(
            resolved=resolved,
            workflow=workflow,
            bootstrap=_bootstrap_from_runtime_result(bootstrap_result),
            caller=caller,
        )
        try:
            return _attach_bootstrap_metadata(
                adapt_outcome(published.handler(ctx)),
                namespace=namespace,
                bootstrap_status=bootstrap_result.status,
                bootstrap_context=bootstrap_result.outputs,
            )
        except MappedOutcomeError as exc:
            return _attach_bootstrap_metadata(
                adapt_outcome(exc.outcome),
                namespace=namespace,
                bootstrap_status=bootstrap_result.status,
                bootstrap_context=bootstrap_result.outputs,
            )

    return handler


def _attach_bootstrap_metadata(
    result: OperationResult,
    *,
    namespace: str,
    bootstrap_status: str,
    bootstrap_context: dict[str, object],
) -> OperationResult:
    raw = dict(result.raw)
    raw["bootstrap"] = {
        "namespace": namespace,
        "status": bootstrap_status,
        "context": dict(bootstrap_context),
    }
    return OperationResult(
        status=result.status,
        summary=result.summary,
        outputs=dict(result.outputs),
        diagnostics=result.diagnostics,
        raw=raw,
    )
