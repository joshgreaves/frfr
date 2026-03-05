"""Private utility functions used across frfr modules."""

import collections.abc
import dataclasses
import enum
import functools
import typing
from typing import Any, cast


@functools.cache
def get_type_hints(target: type) -> dict[str, Any]:
    """Return type hints for a type, cached permanently per type.

    get_type_hints() is expensive: it resolves forward references by inspecting
    the module's globals and walks the MRO. Profiling shows it accounts for ~53%
    of total validation time when called on every TypedDict/dataclass/NamedTuple
    validation. Since a type's hints never change at runtime, caching is safe and
    effectively makes this free after the first call per type.
    """
    return typing.get_type_hints(target)


@functools.cache
def format_key_path_segment(key: object) -> str:
    """Format a dict key as a path segment.

    Identifier-like string keys use dot notation: .foo
    Other keys use bracket notation: ["a.b"], [123], ["my key"]
    """
    if isinstance(key, str) and key.isidentifier():
        return f".{key}"
    return f"[{key!r}]"


def is_namedtuple(t: object) -> bool:
    """Return True if t is a NamedTuple class (not an instance)."""
    return isinstance(t, type) and issubclass(t, tuple) and hasattr(t, "_fields")


def is_dataclass_type(t: object) -> bool:
    """Return True if t is a dataclass class (not an instance)."""
    return dataclasses.is_dataclass(t) and isinstance(t, type)


def is_newtype(t: object) -> bool:
    """Return True if t is a NewType (callable with __supertype__, not a plain class)."""
    return callable(t) and not isinstance(t, type) and hasattr(t, "__supertype__")


def is_enum_type(t: object) -> bool:
    """Return True if t is an Enum class (not an instance)."""
    return isinstance(t, type) and issubclass(t, enum.Enum)


def coerce_to_mapping(
    data: object,
) -> collections.abc.Mapping[Any, object] | None:
    """Coerce NamedTuple/dataclass instances to a Mapping, or return None.

    Accepts any Mapping as-is. Converts NamedTuple via ._asdict() and
    dataclass instances via dataclasses.asdict(). Returns None for anything
    else (signals the caller to raise ValidationError).

    Does not enforce key types — use _coerce_to_str_mapping for schema-based
    handlers that require string keys (TypedDict, dataclass, NamedTuple).
    """
    if is_namedtuple(type(data)) and not isinstance(data, type):
        return data._asdict()  # type: ignore[union-attr]
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        return dataclasses.asdict(data)
    if isinstance(data, collections.abc.Mapping):
        return data
    return None


def coerce_to_str_mapping(
    data: object,
) -> collections.abc.Mapping[str, object] | None:
    """Coerce to a Mapping and verify all keys are strings, or return None.

    Wraps _coerce_to_mapping and adds string-key enforcement. Use this for
    schema-based handlers (TypedDict, dataclass, NamedTuple) where field
    names are always strings. Returns None if data is not a Mapping or if
    any key is not a str (signals the caller to raise ValidationError).
    """
    if type(data) is dict:
        return (
            cast(collections.abc.Mapping[str, object], data)
            if all(isinstance(k, str) for k in data)
            else None
        )
    mapping = coerce_to_mapping(data)
    if mapping is None:
        return None
    if not all(isinstance(k, str) for k in mapping):
        return None
    return cast(collections.abc.Mapping[str, object], mapping)
