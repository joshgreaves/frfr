"""Compile functions for named-field types: TypedDict, dataclass, NamedTuple."""

import collections.abc
import dataclasses
from typing import Any, Callable, cast

import frfr.types
import frfr.utils


def compile_typed_dict(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for TypedDict types."""
    target_type = cast(type, target)
    hints = frfr.utils.get_type_hints(target_type)
    required_keys: frozenset[str] = getattr(
        target_type, "__required_keys__", frozenset()
    )
    optional_keys: frozenset[str] = getattr(
        target_type, "__optional_keys__", frozenset()
    )
    all_keys = required_keys | optional_keys
    field_fns = {key: get_compiled(vtype) for key, vtype in hints.items()}
    # Precompute path segments for known keys (avoids isinstance+isidentifier per key)
    key_segments = {key: frfr.utils.format_key_path_segment(key) for key in all_keys}

    def _typed_dict(data: object, path: str) -> Any:
        if type(data) is dict:
            mapping: collections.abc.Mapping[str, object] = cast(
                collections.abc.Mapping[str, object], data
            )
        else:
            _mapping = frfr.utils.coerce_to_str_mapping(data)
            if _mapping is None:
                raise frfr.types.ValidationError(target_type, data, path=path)
            mapping = _mapping

        data_keys: set[str] = set(mapping.keys())

        missing = required_keys - data_keys
        if missing:
            missing_key = min(missing)
            key_segment = key_segments[missing_key]
            key_path = f"{path}{key_segment}" if path else key_segment
            raise frfr.types.ValidationError(
                target_type, mapping, path=key_path, message="missing required key"
            )

        extra = data_keys - all_keys
        if extra:
            extra_key = min(extra)
            key_segment = frfr.utils.format_key_path_segment(extra_key)
            key_path = f"{path}{key_segment}" if path else key_segment
            raise frfr.types.ValidationError(
                target_type, mapping, path=key_path, message="unexpected key"
            )

        result: dict[str, Any] = {}
        for key in data_keys:
            key_segment = key_segments[key]
            key_path = f"{path}{key_segment}" if path else key_segment
            result[key] = field_fns[key](mapping[key], key_path)
        return result

    return _typed_dict


def compile_namedtuple(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for NamedTuple types."""
    target_type = cast(type, target)
    fields: tuple[str, ...] = target_type._fields  # type: ignore[union-attr]
    hints = frfr.utils.get_type_hints(target_type)
    defaults: dict[str, object] = getattr(target_type, "_field_defaults", {})
    all_keys = frozenset(fields)
    required_keys = frozenset(f for f in fields if f not in defaults)
    field_fns = {field: get_compiled(hints.get(field, Any)) for field in fields}
    # Precompute path segments for known fields (always valid identifiers)
    field_segments = {field: f".{field}" for field in fields}

    def _namedtuple(data: object, path: str) -> Any:
        if type(data) is dict:
            mapping: collections.abc.Mapping[str, object] | None = cast(
                collections.abc.Mapping[str, object], data
            )
        else:
            mapping = frfr.utils.coerce_to_str_mapping(data)

        if mapping is not None:
            data_keys = frozenset(mapping.keys())

            missing = required_keys - data_keys
            if missing:
                missing_key = min(missing)
                seg = field_segments[missing_key]
                field_path = f"{path}{seg}" if path else seg
                raise frfr.types.ValidationError(
                    target_type,
                    mapping,
                    path=field_path,
                    message="missing required field",
                )

            extra = data_keys - all_keys
            if extra:
                extra_key = min(extra)
                seg = frfr.utils.format_key_path_segment(extra_key)
                field_path = f"{path}{seg}" if path else seg
                raise frfr.types.ValidationError(
                    target_type,
                    mapping,
                    path=field_path,
                    message="unexpected field",
                )

            validated: dict[str, Any] = {}
            for field in fields:
                if field in data_keys:
                    seg = field_segments[field]
                    field_path = f"{path}{seg}" if path else seg
                    validated[field] = field_fns[field](mapping[field], field_path)
            return target_type(**validated)

        if isinstance(data, (list, tuple)):
            if len(data) != len(fields):
                raise frfr.types.ValidationError(target_type, data, path=path)
            return target_type(
                *(
                    field_fns[field](item, f"{path}[{i}]")
                    for i, (field, item) in enumerate(zip(fields, data))
                )
            )

        raise frfr.types.ValidationError(target_type, data, path=path)

    return _namedtuple


def compile_dataclass(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for dataclass types."""
    target_type = cast(type, target)
    hints = frfr.utils.get_type_hints(target_type)
    dc_fields = {f.name: f for f in dataclasses.fields(target_type) if f.init}
    required_keys = frozenset(
        name
        for name, f in dc_fields.items()
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    )
    all_keys = frozenset(dc_fields.keys())
    field_fns = {
        key: get_compiled(vtype) for key, vtype in hints.items() if key in dc_fields
    }
    # Precompute path segments for known fields (always valid identifiers)
    field_segments = {key: f".{key}" for key in all_keys}

    def _dataclass(data: object, path: str) -> Any:
        if type(data) is dict:
            mapping: collections.abc.Mapping[Any, object] = data
        else:
            _mapping = frfr.utils.coerce_to_mapping(data)
            if _mapping is None:
                raise frfr.types.ValidationError(target_type, data, path=path)
            mapping = _mapping

        data_keys = frozenset(mapping.keys())

        missing = required_keys - data_keys
        if missing:
            missing_key = min(missing)
            seg = field_segments[missing_key]
            field_path = f"{path}{seg}" if path else seg
            raise frfr.types.ValidationError(
                target_type,
                mapping,
                path=field_path,
                message="missing required field",
            )

        extra = data_keys - all_keys
        if extra:
            extra_key = min(extra)
            seg = frfr.utils.format_key_path_segment(extra_key)
            field_path = f"{path}{seg}" if path else seg
            raise frfr.types.ValidationError(
                target_type, mapping, path=field_path, message="unexpected field"
            )

        validated: dict[str, Any] = {}
        for key in data_keys:
            seg = field_segments[key]
            key_path = f"{path}{seg}" if path else seg
            validated[key] = field_fns[key](mapping[key], key_path)
        return target_type(**validated)

    return _dataclass
