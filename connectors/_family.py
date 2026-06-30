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
    from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation

ProbeHandler = Callable[["ResolvedOperation | ResolvedExpressionProbe", Workflow], OperationResult]
ActionHandler = Callable[["ResolvedOperation", Workflow], OperationResult]


@dataclass(frozen=True, slots=True)
class AssembledFamily:
    connector: Connector
    probe_handlers: dict[str, ProbeHandler]
    action_handlers: dict[str, ActionHandler]


def assemble_family(*, package_name: str, namespace: str, bootstrap: ConnectorBootstrap) -> AssembledFamily:
    probe_handlers: dict[str, ProbeHandler] = {}
    action_handlers: dict[str, ActionHandler] = {}
    operations: list[tuple[int, str, OperationContract]] = []

    for operation in _load_operations(package_name=f"{package_name}.probes", kind="probe"):
        operations.append((operation.order, operation.contract.name, operation.contract))
        if operation.handler is not None:
            probe_handlers[operation.contract.name] = operation.handler

    for operation in _load_operations(package_name=f"{package_name}.actions", kind="action"):
        operations.append((operation.order, operation.contract.name, operation.contract))
        if operation.handler is not None:
            action_handlers[operation.contract.name] = operation.handler

    operations.sort(key=lambda item: (item[0], item[1]))

    return AssembledFamily(
        connector=Connector(
            namespace=namespace,
            bootstrap=bootstrap,
            operations=tuple(contract for _order, _name, contract in operations),
        ),
        probe_handlers=probe_handlers,
        action_handlers=action_handlers,
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
    order: int
    handler: ProbeHandler | ActionHandler | None


def _load_operations(*, package_name: str, kind: str) -> Iterator[_LoadedOperation]:
    try:
        package = import_module(package_name)
    except ModuleNotFoundError:
        return

    for module_name in walk_packages(package.__path__, f"{package.__name__}."):
        module = import_module(module_name.name)
        contract = getattr(module, "OPERATION", None)
        if contract is None:
            continue
        if contract.kind != kind:
            message = f"Operation module '{module.__name__}' declared kind '{contract.kind}', expected '{kind}'"
            raise ValueError(message)

        handler_name = "evaluate" if kind == "probe" else "execute"
        yield _LoadedOperation(
            contract=contract,
            order=int(getattr(module, "ORDER", 1000)),
            handler=getattr(module, handler_name, None),
        )
