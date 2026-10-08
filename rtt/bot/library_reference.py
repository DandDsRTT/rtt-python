from __future__ import annotations

import enum
import importlib
import inspect
import pkgutil
from types import ModuleType

import rtt.library

_PACKAGE = "rtt.library"


def _annotation(value: object) -> str:
    if value is inspect.Parameter.empty:
        return ""
    return value if isinstance(value, str) else inspect.formatannotation(value)


def _parameter(parameter: inspect.Parameter) -> str:
    text = parameter.name
    if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
        text = "*" + text
    elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
        text = "**" + text
    annotation = _annotation(parameter.annotation)
    if annotation:
        text += f": {annotation}"
    if parameter.default is not inspect.Parameter.empty:
        text += f" = {parameter.default!r}"
    return text


def _signature(function: object) -> str:
    signature = inspect.signature(function)
    parameters = ", ".join(_parameter(p) for p in signature.parameters.values())
    returns = _annotation(signature.return_annotation)
    return f"({parameters})" + (f" -> {returns}" if returns else "")


def _owned(module: ModuleType, predicate) -> list[tuple[str, object]]:
    return [
        (name, obj)
        for name, obj in vars(module).items()
        if not name.startswith("_") and predicate(obj) and obj.__module__ == module.__name__
    ]


def _class_lines(name: str, cls: type) -> list[str]:
    if issubclass(cls, enum.Enum):
        return [f"class {name}(Enum): " + ", ".join(member.name for member in cls)]
    fields = [f"{field}: {_annotation(kind)}" for field, kind in cls.__annotations__.items()]
    return [f"class {name}: " + ", ".join(fields)]


def _module_lines(module: ModuleType) -> list[str]:
    lines = [f"## {module.__name__}"]
    for name, cls in _owned(module, inspect.isclass):
        lines.extend(_class_lines(name, cls))
    lines.extend(f"{name}{_signature(fn)}" for name, fn in _owned(module, inspect.isfunction))
    return lines


def library_reference() -> str:
    names = sorted(info.name for info in pkgutil.iter_modules(rtt.library.__path__))
    modules = [importlib.import_module(f"{_PACKAGE}.{name}") for name in names]
    return "\n".join("\n".join(_module_lines(module)) + "\n" for module in modules)
