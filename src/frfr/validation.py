"""Core validation logic for frfr."""

import collections.abc
import dataclasses
import types

from typing import (
    Any,
    Callable,
    Literal,
    Protocol,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(
        self,
        expected: type,
        actual: object,
        path: str = "",
        message: str | None = None,
    ) -> None:
        self.expected = expected
        self.actual = actual
        self.path = path
        location = f"{path} - " if path else ""
        if message is not None:
            # Custom message provided (e.g., "missing required key")
            full_message = f"{location}{message}"
        else:
            # Auto-generate message from expected/actual
            actual_type = type(actual).__name__
            actual_repr = repr(actual)
            # Handle Union types and other special forms that don't have __name__
            expected_name = getattr(expected, "__name__", None) or str(expected)
            full_message = (
                f"{location}expected {expected_name}, got {actual_type} ({actual_repr})"
            )
        super().__init__(full_message)


class ValidatorProtocol(Protocol):
    """Protocol for validators. Used in handler type signatures."""

    def validate[T](self, target: type[T], data: object) -> T:
        """Validate and coerce data to the given type."""
        ...

    def _validate_at[T](self, target: type[T], data: object, path: str) -> T:
        """Validate at a specific path (internal, for handlers)."""
        ...


# Type alias for handler functions.
# Handlers receive a ValidatorProtocol to enable recursive validation.
# The path parameter tracks location in nested structures for error messages.
type Handler[T] = Callable[[ValidatorProtocol, type[T], object, str], T]


class Validator:
    """Type validator with extensible handlers.

    Handlers receive the validator instance to enable recursive validation
    of nested types (e.g., list[int] needs to validate each element).

    All validators start with built-in handlers for standard types.
    Use `frozen=True` to prevent further registration (used internally
    for the default validator).
    """

    def __init__(self, *, frozen: bool = False) -> None:
        self._handlers: dict[Any, Handler[Any]] = {}
        self._predicate_handlers: list[
            tuple[Callable[[object], bool], Handler[Any]]
        ] = []
        self._frozen = frozen
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in handlers. Called during __init__."""
        # Exact-type handlers (including special forms that work as dict keys)
        self._handlers[Any] = parse_any
        self._handlers[int] = parse_int
        self._handlers[float] = parse_float
        self._handlers[str] = parse_str
        self._handlers[bool] = parse_bool
        self._handlers[type(None)] = parse_none
        self._handlers[list] = parse_list
        self._handlers[tuple] = parse_tuple
        self._handlers[dict] = parse_dict
        self._handlers[set] = parse_set
        self._handlers[frozenset] = parse_frozenset
        # Union/Literal are found via get_origin() fallback
        self._handlers[Union] = parse_union
        self._handlers[types.UnionType] = parse_union
        self._handlers[Literal] = parse_literal
        # Structural handlers matched by predicate (checked in order)
        self._predicate_handlers = [
            (is_typeddict, parse_typed_dict),
            (_is_namedtuple, parse_namedtuple),
            (_is_dataclass_type, parse_dataclass),
        ]

    def register_type_handler[T](self, target: type[T], handler: Handler[T]) -> None:
        """Register a handler for an exact target type.

        Args:
            target: The type to register a handler for.
            handler: A function that takes (validator, target_type, data) and
                     returns a validated/coerced instance of target_type.
                     The validator is passed to enable recursive validation.

        Raises:
            RuntimeError: If the validator is frozen.
        """
        if self._frozen:
            raise RuntimeError("Cannot register on a frozen validator")
        self._handlers[target] = handler

    def register_predicate_handler[T](
        self,
        predicate: Callable[[object], bool],
        handler: Handler[T],
    ) -> None:
        """Register a handler for targets matching a predicate.

        Predicate handlers are checked after exact-type matches but before
        origin-based matches. The most recently registered predicate handler
        is checked first, so user-registered handlers override built-ins.

        Args:
            predicate: A function that takes a type and returns True if this
                       handler should be used for that type.
            handler: A function that takes (validator, target_type, data) and
                     returns a validated/coerced instance of target_type.

        Raises:
            RuntimeError: If the validator is frozen.
        """
        if self._frozen:
            raise RuntimeError("Cannot register on a frozen validator")
        self._predicate_handlers.insert(0, (predicate, handler))

    def validate[T](self, target: type[T], data: object) -> T:
        """Validate and coerce data to the given type.

        Args:
            target: The type to validate against.
            data: The data to validate.

        Returns:
            The validated data, coerced to the target type if needed.

        Raises:
            ValidationError: If the data does not match the expected type.
        """
        return self._validate_at(target, data, path="")

    def _validate_at[T](self, target: type[T], data: object, path: str) -> T:
        """Validate at a specific path (internal, for handlers).

        Args:
            target: The type to validate against.
            data: The data to validate.
            path: The path to this location in the data structure.

        Returns:
            The validated data, coerced to the target type if needed.

        Raises:
            ValidationError: If the data does not match the expected type.
        """
        # 1. Exact type match (int, str, Any, ...)
        handler = self._handlers.get(target)
        if handler is not None:
            return cast(T, handler(self, target, data, path))

        # 2. Predicate handlers (TypedDict, NamedTuple, dataclass, user-defined)
        for predicate, pred_handler in self._predicate_handlers:
            if predicate(target):
                return cast(T, pred_handler(self, target, data, path))

        # 3. Origin-based match (list[int] -> list, Union[int, str] -> Union, ...)
        origin = get_origin(target)
        if origin is not None:
            handler = self._handlers.get(origin)
            if handler is not None:
                return cast(T, handler(self, target, data, path))

        raise ValidationError(target, data, path=path)


def parse_int(
    validator: ValidatorProtocol, target: type[int], data: object, path: str
) -> int:
    """Validate that data is an int (not a bool).

    Exposed for composition in custom handlers.
    """
    # Reject bool explicitly - even though bool is a subclass of int
    if type(data) is bool:
        raise ValidationError(target, data, path=path)

    if type(data) is not int:
        raise ValidationError(target, data, path=path)

    return data


def parse_float(
    validator: ValidatorProtocol, target: type[float], data: object, path: str
) -> float:
    """Validate that data is a float, or coerce from int.

    Exposed for composition in custom handlers.
    """
    # Reject bool explicitly
    if type(data) is bool:
        raise ValidationError(target, data, path=path)

    # Accept float directly
    if type(data) is float:
        return data

    # Coerce int to float (lossless widening)
    if type(data) is int:
        return float(data)

    raise ValidationError(target, data, path=path)


def parse_str(
    validator: ValidatorProtocol, target: type[str], data: object, path: str
) -> str:
    """Validate that data is a str.

    Exposed for composition in custom handlers.
    """
    if type(data) is not str:
        raise ValidationError(target, data, path=path)

    return data


def parse_bool(
    validator: ValidatorProtocol, target: type[bool], data: object, path: str
) -> bool:
    """Validate that data is a bool.

    Exposed for composition in custom handlers.
    """
    if type(data) is not bool:
        raise ValidationError(target, data, path=path)

    return data


def parse_none(
    validator: ValidatorProtocol, target: type[None], data: object, path: str
) -> None:
    """Validate that data is None.

    Exposed for composition in custom handlers.
    """
    if data is not None:
        raise ValidationError(target, data, path=path)

    return None


def parse_list[T](
    validator: ValidatorProtocol, target: type[list[T]], data: object, path: str
) -> list[T]:
    """Validate that data is a list or tuple, optionally validating elements.

    Accepts both list and tuple (coerces tuple to list).
    For `list` (unparameterized): accepts any list/tuple.
    For `list[T]`: validates each element against T.

    Always returns a new list (mutable containers are always copied).

    Exposed for composition in custom handlers.
    """
    if not isinstance(data, (list, tuple)):
        raise ValidationError(target, data, path=path)

    # Check if parameterized (e.g., list[int] vs plain list)
    args = get_args(target)
    if not args:
        # Unparameterized list, return a shallow copy
        return cast(list[T], list(data))

    # Validate each element against the element type
    element_type = args[0]
    return [
        validator._validate_at(element_type, item, f"{path}[{i}]")
        for i, item in enumerate(data)
    ]


def parse_tuple[*Ts](
    validator: ValidatorProtocol, target: type[tuple[*Ts]], data: object, path: str
) -> tuple[*Ts]:
    """Validate that data is a tuple or list, optionally validating elements.

    Accepts both tuple and list (coerces list to tuple).
    For `tuple` (unparameterized): accepts any tuple/list.
    For `tuple[T, ...]`: validates each element against T (homogeneous).
    For `tuple[T1, T2, ...]`: validates each element against its positional type.

    Exposed for composition in custom handlers.
    """
    if not isinstance(data, (list, tuple)):
        raise ValidationError(target, data, path=path)

    args = get_args(target)
    if not args:
        # Unparameterized tuple, just convert
        return cast(tuple[*Ts], tuple(data))

    # Check for homogeneous tuple[T, ...] - indicated by Ellipsis as second arg
    if len(args) == 2 and args[1] is Ellipsis:
        element_type = args[0]
        return cast(
            tuple[*Ts],
            tuple(
                validator._validate_at(element_type, item, f"{path}[{i}]")
                for i, item in enumerate(data)
            ),
        )

    # Fixed-length tuple[T1, T2, ...] - validate length and each element
    if len(data) != len(args):
        raise ValidationError(target, data, path=path)

    return cast(
        tuple[*Ts],
        tuple(
            validator._validate_at(t, item, f"{path}[{i}]")
            for i, (t, item) in enumerate(zip(args, data, strict=True))
        ),
    )


def parse_dict[K, V](
    validator: ValidatorProtocol, target: type[dict[K, V]], data: object, path: str
) -> dict[K, V]:
    """Validate that data is a Mapping or dataclass instance.

    Accepts any Mapping type (dict, OrderedDict, MappingProxyType, etc.) or
    dataclass instance (converted via dataclasses.asdict()).
    For `dict` (unparameterized): accepts any Mapping/dataclass.
    For `dict[K, V]`: validates each key against K and value against V.

    Always returns a new dict (mutable containers are always copied).

    Exposed for composition in custom handlers.
    """
    mapping = _coerce_to_mapping(data)
    if mapping is None:
        raise ValidationError(target, data, path=path)

    args = get_args(target)
    if not args:
        # Unparameterized dict, just copy
        return cast(dict[K, V], dict(mapping))

    # Parameterized dict[K, V] - validate keys and values
    key_type, value_type = args
    result: dict[K, V] = {}
    for k, v in mapping.items():
        # Build path segment: .key for identifiers, [repr(key)] for others
        key_segment = _format_key_path_segment(k)
        key_path_segment = f"{path}{key_segment}" if path else key_segment
        # Keys get [key] suffix to indicate key validation failed
        validated_key = validator._validate_at(key_type, k, f"{key_path_segment}[key]")
        # Values get the key as path segment
        validated_value = validator._validate_at(value_type, v, key_path_segment)
        result[validated_key] = validated_value
    return result


def parse_set[T](
    validator: ValidatorProtocol, target: type[set[T]], data: object, path: str
) -> set[T]:
    """Validate that data is a set or frozenset, optionally validating elements.

    Only accepts set/frozenset as input - no coercion from list/tuple since
    that could lose data (duplicates) and ordering doesn't transfer meaningfully.

    For `set` (unparameterized): accepts any set/frozenset.
    For `set[T]`: validates each element against T.

    Always returns a new set (mutable containers are always copied).

    Exposed for composition in custom handlers.
    """
    if not isinstance(data, (set, frozenset)):
        raise ValidationError(target, data, path=path)

    args = get_args(target)
    if not args:
        # Unparameterized set, just copy
        return cast(set[T], set(data))

    # Validate each element against the element type
    # Sets are unordered, so we can't provide meaningful indices
    element_type = args[0]
    return {validator._validate_at(element_type, item, path) for item in data}


def parse_frozenset[T](
    validator: ValidatorProtocol, target: type[frozenset[T]], data: object, path: str
) -> frozenset[T]:
    """Validate that data is a set or frozenset, optionally validating elements.

    Only accepts set/frozenset as input - same reasoning as set.

    For `frozenset` (unparameterized): accepts any set/frozenset.
    For `frozenset[T]`: validates each element against T.

    Exposed for composition in custom handlers.
    """
    if not isinstance(data, (set, frozenset)):
        raise ValidationError(target, data, path=path)

    args = get_args(target)
    if not args:
        # Unparameterized frozenset, just convert
        return cast(frozenset[T], frozenset(data))

    # Validate each element against the element type
    # Sets are unordered, so we can't provide meaningful indices
    element_type = args[0]
    return frozenset(validator._validate_at(element_type, item, path) for item in data)


def parse_typed_dict[T](
    validator: ValidatorProtocol, target: type[T], data: object, path: str
) -> T:
    """Validate that data matches a TypedDict schema.

    Validates:
    - Data is a Mapping
    - All required keys are present
    - No extra keys are present
    - Each value matches its declared type

    Exposed for composition in custom handlers.
    """
    mapping = _coerce_to_str_mapping(data)
    if mapping is None:
        raise ValidationError(target, data, path=path)

    # Get type hints and required/optional keys
    hints = get_type_hints(target)
    required_keys = getattr(target, "__required_keys__", frozenset())
    optional_keys = getattr(target, "__optional_keys__", frozenset())
    all_keys = required_keys | optional_keys

    # TypedDict keys are always strings
    data_keys: set[str] = set(mapping.keys())

    # Check for missing required keys
    missing = required_keys - data_keys
    if missing:
        missing_key = min(missing)
        key_segment = _format_key_path_segment(missing_key)
        key_path = f"{path}{key_segment}" if path else key_segment
        raise ValidationError(
            target, mapping, path=key_path, message="missing required key"
        )

    # Check for extra keys
    extra = data_keys - all_keys
    if extra:
        extra_key = next(iter(extra))
        key_segment = _format_key_path_segment(extra_key)
        key_path = f"{path}{key_segment}" if path else key_segment
        raise ValidationError(target, mapping, path=key_path, message="unexpected key")

    # Validate each value against its type hint
    result: dict[str, Any] = {}
    for key in data_keys:
        value_type = hints[key]
        key_segment = _format_key_path_segment(key)
        key_path = f"{path}{key_segment}" if path else key_segment
        result[key] = validator._validate_at(value_type, mapping[key], key_path)

    return cast(T, result)


def _is_namedtuple(t: object) -> bool:
    """Return True if t is a NamedTuple class (not an instance)."""
    return isinstance(t, type) and issubclass(t, tuple) and hasattr(t, "_fields")


def _format_key_path_segment(key: object) -> str:
    """Format a dict key as a path segment.

    Identifier-like string keys use dot notation: .foo
    Other keys use bracket notation: ["a.b"], [123], ["my key"]
    """
    if isinstance(key, str) and key.isidentifier():
        return f".{key}"
    return f"[{key!r}]"


def _is_dataclass_type(t: object) -> bool:
    """Return True if t is a dataclass class (not an instance)."""
    return dataclasses.is_dataclass(t) and isinstance(t, type)


def _coerce_to_mapping(
    data: object,
) -> collections.abc.Mapping[Any, object] | None:
    """Coerce NamedTuple/dataclass instances to a Mapping, or return None.

    Accepts any Mapping as-is. Converts NamedTuple via ._asdict() and
    dataclass instances via dataclasses.asdict(). Returns None for anything
    else (signals the caller to raise ValidationError).

    Does not enforce key types — use _coerce_to_str_mapping for schema-based
    handlers that require string keys (TypedDict, dataclass, NamedTuple).
    """
    if _is_namedtuple(type(data)) and not isinstance(data, type):
        return data._asdict()  # type: ignore[union-attr]
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        return dataclasses.asdict(data)
    if isinstance(data, collections.abc.Mapping):
        return data
    return None


def _coerce_to_str_mapping(
    data: object,
) -> collections.abc.Mapping[str, object] | None:
    """Coerce to a Mapping and verify all keys are strings, or return None.

    Wraps _coerce_to_mapping and adds string-key enforcement. Use this for
    schema-based handlers (TypedDict, dataclass, NamedTuple) where field
    names are always strings. Returns None if data is not a Mapping or if
    any key is not a str (signals the caller to raise ValidationError).
    """
    mapping = _coerce_to_mapping(data)
    if mapping is None:
        return None
    if not all(isinstance(k, str) for k in mapping):
        return None
    return cast(collections.abc.Mapping[str, object], mapping)


def parse_namedtuple[T](
    validator: ValidatorProtocol, target: type[T], data: object, path: str
) -> T:
    """Validate that data matches a NamedTuple schema and construct it.

    Accepts two input forms:
    - Mapping (dict, OrderedDict, dataclass, etc.): validated by field name.
      Fields with defaults may be omitted; extra keys are rejected.
    - Sequence (tuple, list, NamedTuple): validated positionally.
      Length must exactly match the number of fields (no defaults applied
      from sequences - all fields must be provided).

    Exposed for composition in custom handlers.
    """
    fields: tuple[str, ...] = target._fields  # type: ignore[union-attr]
    hints = get_type_hints(target)
    defaults: dict[str, object] = {}
    if hasattr(target, "_field_defaults"):
        defaults = target._field_defaults  # type: ignore[union-attr]

    mapping = _coerce_to_str_mapping(data)
    if mapping is not None:
        # Named construction path
        all_keys = frozenset(fields)
        required_keys = frozenset(f for f in fields if f not in defaults)
        data_keys = frozenset(mapping.keys())

        missing = required_keys - data_keys
        if missing:
            missing_key = min(missing)
            field_path = f"{path}.{missing_key}" if path else f".{missing_key}"
            raise ValidationError(
                target, mapping, path=field_path, message="missing required field"
            )

        extra = data_keys - all_keys
        if extra:
            extra_key = next(iter(extra))
            field_path = f"{path}{_format_key_path_segment(extra_key)}" if path else _format_key_path_segment(extra_key)
            raise ValidationError(
                target, mapping, path=field_path, message="unexpected field"
            )

        validated: dict[str, Any] = {}
        for field in fields:
            if field in data_keys:
                field_path = f"{path}.{field}" if path else f".{field}"
                validated[field] = validator._validate_at(
                    hints[field], mapping[field], field_path
                )
            # Fields not in data_keys have defaults; omit them so NamedTuple uses its default

        return target(**validated)

    if isinstance(data, (list, tuple)):
        # Positional construction path - length must match exactly
        if len(data) != len(fields):
            raise ValidationError(target, data, path=path)
        validated_items = [
            validator._validate_at(hints[field], item, f"{path}[{i}]")
            for i, (field, item) in enumerate(zip(fields, data))
        ]
        return target(*validated_items)

    raise ValidationError(target, data, path=path)


def parse_dataclass[T](
    validator: ValidatorProtocol, target: type[T], data: object, path: str
) -> T:
    """Validate that data matches a dataclass schema and construct it.

    Accepts any Mapping or dataclass instance as input. Validates:
    - All required fields (no default) are present
    - No extra keys are present
    - Each value matches its declared type

    Fields with defaults are optional - omitting them lets the dataclass
    use its declared default or default_factory.

    Calls the dataclass constructor so __post_init__ is run.

    Exposed for composition in custom handlers.
    """
    mapping = _coerce_to_mapping(data)
    if mapping is None:
        raise ValidationError(target, data, path=path)

    hints = get_type_hints(target)
    fields = {f.name: f for f in dataclasses.fields(cast(type, target))}

    required_keys = frozenset(
        name
        for name, f in fields.items()
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    )
    all_keys = frozenset(fields.keys())
    data_keys = frozenset(mapping.keys())

    # Check for missing required fields
    missing = required_keys - data_keys
    if missing:
        missing_key = min(missing)
        field_path = f"{path}.{missing_key}" if path else f".{missing_key}"
        raise ValidationError(
            target, mapping, path=field_path, message="missing required field"
        )

    # Check for extra keys
    extra = data_keys - all_keys
    if extra:
        extra_key = next(iter(extra))
        field_path = f"{path}{_format_key_path_segment(extra_key)}" if path else _format_key_path_segment(extra_key)
        raise ValidationError(
            target, mapping, path=field_path, message="unexpected field"
        )

    # Validate and coerce each provided field
    validated: dict[str, Any] = {}
    for key in data_keys:
        key_path = f"{path}.{key}" if path else f".{key}"
        validated[key] = validator._validate_at(hints[key], mapping[key], key_path)

    return target(**validated)


def parse_union(
    validator: ValidatorProtocol, target: type[Any], data: object, path: str
) -> Any:
    """Validate that data matches one of the types in the Union.

    Types are tried in declaration order. The first type that successfully
    validates (including any coercion) wins. This means order matters:
    - Union[float, int] with 1 -> 1.0 (coerced to float)
    - Union[int, float] with 1 -> 1 (int matches first)

    Exposed for composition in custom handlers.
    """
    args = get_args(target)
    if not args:
        # Shouldn't happen for valid Union types, but handle gracefully
        raise ValidationError(target, data, path=path)

    # Try each type in order
    for union_type in args:
        try:
            return validator._validate_at(union_type, data, path)
        except ValidationError:
            continue

    # None matched - raise error
    raise ValidationError(target, data, path=path)


def parse_literal(
    validator: ValidatorProtocol, target: type[Any], data: object, path: str
) -> Any:
    """Validate that data is one of the exact values in a Literal type.

    Uses strict matching: both value and type must match. No coercion.
    - Literal[1] does not accept True (even though True == 1)
    - Literal[True] does not accept 1

    Exposed for composition in custom handlers.
    """
    allowed = get_args(target)
    for val in allowed:
        if type(data) is type(val) and data == val:
            return data
    raise ValidationError(target, data, path=path)


def parse_any(
    validator: ValidatorProtocol, target: type[Any], data: object, path: str
) -> Any:
    """Accept any data without validation.

    Exposed for composition in custom handlers.
    """
    return data


# Private default validator instance (frozen to prevent modification)
_DEFAULT_VALIDATOR = Validator(frozen=True)


def validate[T](target: type[T], data: object) -> T:
    """Validate and coerce data to the given type.

    This is the main entry point for frfr. Uses the default validator
    with built-in handlers for standard types.

    Args:
        target: The type to validate against.
        data: The data to validate.

    Returns:
        The validated data, coerced to the target type if needed.

    Raises:
        ValidationError: If the data does not match the expected type.
    """
    return _DEFAULT_VALIDATOR.validate(target, data)
