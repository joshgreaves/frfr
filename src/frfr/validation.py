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

    def __init__(self, expected: type, actual: object, path: str = "") -> None:
        self.expected = expected
        self.actual = actual
        self.path = path
        actual_type = type(actual).__name__
        actual_repr = repr(actual)
        location = f"{path} - " if path else ""
        # Handle Union types and other special forms that don't have __name__
        expected_name = getattr(expected, "__name__", None) or str(expected)
        message = (
            f"{location}expected {expected_name}, got {actual_type} ({actual_repr})"
        )
        super().__init__(message)


class ValidatorProtocol(Protocol):
    """Protocol for validators. Used in handler type signatures."""

    def validate[T](self, target: type[T], data: object) -> T:
        """Validate and coerce data to the given type."""
        ...


# Type alias for handler functions.
# Handlers receive a ValidatorProtocol to enable recursive validation.
type Handler[T] = Callable[[ValidatorProtocol, type[T], object], T]


class CompiledValidator[T](Protocol):
    """Protocol for compiled validators that skip runtime introspection."""

    def __call__(self, data: object) -> T: ...


# Type alias for compiler functions that produce CompiledValidators.
type HandlerCompiler[T] = Callable[["Validator", type[T]], CompiledValidator[T]]


# ---------------------------------------------------------------------------
# Compiled validator dataclasses - capture pre-computed type info
# ---------------------------------------------------------------------------


class _CompilingSentinel:
    """Sentinel marking a type currently being compiled (for recursion detection)."""

    __slots__ = ()


_COMPILING = _CompilingSentinel()


@dataclasses.dataclass(slots=True)
class RecursiveValidator:
    """Mutable wrapper for recursive type compilation.

    Only used when a type actually references itself (e.g., Node with
    children: list["Node"]). For non-recursive types, we cache the
    validator directly without this wrapper for better performance.
    """

    inner: CompiledValidator[Any] | None = None

    def __call__(self, data: object) -> Any:
        assert self.inner is not None
        return self.inner(data)


@dataclasses.dataclass(frozen=True, slots=True)
class _HandlerWrapper:
    """Wraps a legacy Handler to implement CompiledValidator interface.

    Used as fallback when a user has registered a custom handler but no compiler.
    """

    handler: Handler[Any]
    validator: "Validator"
    target: type

    def __call__(self, data: object) -> Any:
        return self.handler(self.validator, self.target, data)


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
        # Compiler registry for compiled validators
        self._compilers: dict[Any, HandlerCompiler[Any]] = {}
        self._predicate_compilers: list[
            tuple[Callable[[object], bool], HandlerCompiler[Any]]
        ] = []
        # Cache for compiled validators (keyed by target type id for identity)
        # Using id() as key because some types are equal but need different
        # validation (e.g., int | float == float | int, but args order differs)
        self._compiled_cache: dict[int, CompiledValidator[Any]] = {}
        self._frozen = frozen
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in handlers and compilers. Called during __init__."""
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

        # Compiled validators - skip runtime introspection on repeat calls
        self._compilers[Any] = compile_any
        self._compilers[int] = compile_int
        self._compilers[float] = compile_float
        self._compilers[str] = compile_str
        self._compilers[bool] = compile_bool
        self._compilers[type(None)] = compile_none
        self._compilers[list] = compile_list
        self._compilers[tuple] = compile_tuple
        self._compilers[dict] = compile_dict
        self._compilers[set] = compile_set
        self._compilers[frozenset] = compile_frozenset
        self._compilers[Union] = compile_union
        self._compilers[types.UnionType] = compile_union
        self._compilers[Literal] = compile_literal
        self._predicate_compilers = [
            (is_typeddict, compile_typed_dict),
            (_is_namedtuple, compile_namedtuple),
            (_is_dataclass_type, compile_dataclass),
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
        self._compiled_cache.clear()

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
        self._compiled_cache.clear()

    def _compile[T](self, target: type[T]) -> CompiledValidator[T]:
        """Get or create a compiled validator for the target type.

        Compiled validators skip runtime introspection (get_type_hints, get_args,
        dataclasses.fields) by pre-computing all type information on first use.

        For recursive types (where compilation encounters the same type again),
        uses a RecursiveValidator wrapper. For non-recursive types (the common
        case), caches the validator directly without wrapper overhead.
        """
        target_id = id(target)
        cached = self._compiled_cache.get(target_id)

        if cached is None:
            # First time seeing this type - mark as compiling and build
            self._compiled_cache[target_id] = _COMPILING  # type: ignore[assignment]
            compiled = self._build_compiled_validator(target)

            # Check if recursion occurred (cache entry changed to RecursiveValidator)
            current = self._compiled_cache.get(target_id)
            if isinstance(current, RecursiveValidator):
                # Recursion detected - fill in the wrapper
                current.inner = compiled
                return cast(CompiledValidator[T], current)
            else:
                # No recursion - cache the validator directly
                self._compiled_cache[target_id] = compiled
                return cast(CompiledValidator[T], compiled)

        if cached is _COMPILING:
            # Recursion detected! Create wrapper and cache it
            wrapper: RecursiveValidator = RecursiveValidator()
            self._compiled_cache[target_id] = wrapper
            return cast(CompiledValidator[T], wrapper)

        # Already compiled - return cached validator
        return cast(CompiledValidator[T], cached)

    def _build_compiled_validator[T](self, target: type[T]) -> CompiledValidator[T]:
        """Build a compiled validator without caching.

        Follows the same resolution order as the legacy validate():
        1. Exact type match
        2. Predicate match
        3. Origin-based match
        """
        # 1. Exact type match (int, str, Any, ...)
        compiler = self._compilers.get(target)
        if compiler is not None:
            return cast(CompiledValidator[T], compiler(self, target))

        # 2. Predicate compilers (TypedDict, NamedTuple, dataclass, user-defined)
        for predicate, pred_compiler in self._predicate_compilers:
            if predicate(target):
                return cast(CompiledValidator[T], pred_compiler(self, target))

        # 3. Origin-based match (list[int] -> list, Union[int, str] -> Union, ...)
        origin = get_origin(target)
        if origin is not None:
            compiler = self._compilers.get(origin)
            if compiler is not None:
                return cast(CompiledValidator[T], compiler(self, target))

        # Fallback to handler-based validation (for user-registered handlers)
        handler = self._handlers.get(target)
        if handler is not None:
            return cast(CompiledValidator[T], _HandlerWrapper(handler, self, target))

        for predicate, pred_handler in self._predicate_handlers:
            if predicate(target):
                return cast(
                    CompiledValidator[T], _HandlerWrapper(pred_handler, self, target)
                )

        if origin is not None:
            handler = self._handlers.get(origin)
            if handler is not None:
                return cast(
                    CompiledValidator[T], _HandlerWrapper(handler, self, target)
                )

        raise ValidationError(target, None)

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
        # Inline cache lookup for performance (avoids method call overhead)
        cached = self._compiled_cache.get(id(target))
        if cached is not None and cached is not _COMPILING:
            return cached(data)
        return self._compile(target)(data)


def parse_int(validator: ValidatorProtocol, target: type[int], data: object) -> int:
    """Validate that data is an int (not a bool).

    Exposed for composition in custom handlers.
    """
    # Reject bool explicitly - even though bool is a subclass of int
    if type(data) is bool:
        raise ValidationError(target, data)

    if type(data) is not int:
        raise ValidationError(target, data)

    return data


def parse_float(
    validator: ValidatorProtocol, target: type[float], data: object
) -> float:
    """Validate that data is a float, or coerce from int.

    Exposed for composition in custom handlers.
    """
    # Reject bool explicitly
    if type(data) is bool:
        raise ValidationError(target, data)

    # Accept float directly
    if type(data) is float:
        return data

    # Coerce int to float (lossless widening)
    if type(data) is int:
        return float(data)

    raise ValidationError(target, data)


def parse_str(validator: ValidatorProtocol, target: type[str], data: object) -> str:
    """Validate that data is a str.

    Exposed for composition in custom handlers.
    """
    if type(data) is not str:
        raise ValidationError(target, data)

    return data


def parse_bool(validator: ValidatorProtocol, target: type[bool], data: object) -> bool:
    """Validate that data is a bool.

    Exposed for composition in custom handlers.
    """
    if type(data) is not bool:
        raise ValidationError(target, data)

    return data


def parse_none(validator: ValidatorProtocol, target: type[None], data: object) -> None:
    """Validate that data is None.

    Exposed for composition in custom handlers.
    """
    if data is not None:
        raise ValidationError(target, data)

    return None


def parse_list[T](
    validator: ValidatorProtocol, target: type[list[T]], data: object
) -> list[T]:
    """Validate that data is a list or tuple, optionally validating elements.

    Accepts both list and tuple (coerces tuple to list).
    For `list` (unparameterized): accepts any list/tuple.
    For `list[T]`: validates each element against T.

    Always returns a new list (mutable containers are always copied).

    Exposed for composition in custom handlers.
    """
    if not isinstance(data, (list, tuple)):
        raise ValidationError(target, data)

    # Check if parameterized (e.g., list[int] vs plain list)
    args = get_args(target)
    if not args:
        # Unparameterized list, return a shallow copy
        return cast(list[T], list(data))

    # Validate each element against the element type
    element_type = args[0]
    return [validator.validate(element_type, item) for item in data]


def parse_tuple[*Ts](
    validator: ValidatorProtocol, target: type[tuple[*Ts]], data: object
) -> tuple[*Ts]:
    """Validate that data is a tuple or list, optionally validating elements.

    Accepts both tuple and list (coerces list to tuple).
    For `tuple` (unparameterized): accepts any tuple/list.
    For `tuple[T, ...]`: validates each element against T (homogeneous).
    For `tuple[T1, T2, ...]`: validates each element against its positional type.

    Exposed for composition in custom handlers.
    """
    if not isinstance(data, (list, tuple)):
        raise ValidationError(target, data)

    args = get_args(target)
    if not args:
        # Unparameterized tuple, just convert
        return cast(tuple[*Ts], tuple(data))

    # Check for homogeneous tuple[T, ...] - indicated by Ellipsis as second arg
    if len(args) == 2 and args[1] is Ellipsis:
        element_type = args[0]
        return cast(
            tuple[*Ts], tuple(validator.validate(element_type, item) for item in data)
        )

    # Fixed-length tuple[T1, T2, ...] - validate length and each element
    if len(data) != len(args):
        raise ValidationError(target, data)

    return cast(
        tuple[*Ts],
        tuple(validator.validate(t, item) for t, item in zip(args, data, strict=True)),
    )


def parse_dict[K, V](
    validator: ValidatorProtocol, target: type[dict[K, V]], data: object
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
        raise ValidationError(target, data)

    args = get_args(target)
    if not args:
        # Unparameterized dict, just copy
        return cast(dict[K, V], dict(mapping))

    # Parameterized dict[K, V] - validate keys and values
    key_type, value_type = args
    return {
        validator.validate(key_type, k): validator.validate(value_type, v)
        for k, v in mapping.items()
    }


def parse_set[T](
    validator: ValidatorProtocol, target: type[set[T]], data: object
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
        raise ValidationError(target, data)

    args = get_args(target)
    if not args:
        # Unparameterized set, just copy
        return cast(set[T], set(data))

    # Validate each element against the element type
    element_type = args[0]
    return {validator.validate(element_type, item) for item in data}


def parse_frozenset[T](
    validator: ValidatorProtocol, target: type[frozenset[T]], data: object
) -> frozenset[T]:
    """Validate that data is a set or frozenset, optionally validating elements.

    Only accepts set/frozenset as input - same reasoning as set.

    For `frozenset` (unparameterized): accepts any set/frozenset.
    For `frozenset[T]`: validates each element against T.

    Exposed for composition in custom handlers.
    """
    if not isinstance(data, (set, frozenset)):
        raise ValidationError(target, data)

    args = get_args(target)
    if not args:
        # Unparameterized frozenset, just convert
        return cast(frozenset[T], frozenset(data))

    # Validate each element against the element type
    element_type = args[0]
    return frozenset(validator.validate(element_type, item) for item in data)


def parse_typed_dict[T](
    validator: ValidatorProtocol, target: type[T], data: object
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
        raise ValidationError(target, data)

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
        missing_key = next(iter(missing))
        raise ValidationError(target, mapping, path=f"missing key: {missing_key}")

    # Check for extra keys
    extra = data_keys - all_keys
    if extra:
        extra_key = next(iter(extra))
        raise ValidationError(target, mapping, path=f"unexpected key: {extra_key}")

    # Validate each value against its type hint
    result: dict[str, Any] = {}
    for key in data_keys:
        value_type = hints[key]
        result[key] = validator.validate(value_type, mapping[key])

    return cast(T, result)


def _is_namedtuple(t: object) -> bool:
    """Return True if t is a NamedTuple class (not an instance)."""
    return isinstance(t, type) and issubclass(t, tuple) and hasattr(t, "_fields")


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
    # Fast path: dict is the most common input type
    if type(data) is dict:
        return data
    # Other Mapping types (OrderedDict, MappingProxyType, etc.)
    if isinstance(data, collections.abc.Mapping):
        return data
    # NamedTuple instances have _asdict method
    if _is_namedtuple(type(data)) and not isinstance(data, type):
        return data._asdict()  # type: ignore[union-attr]
    # Dataclass instances
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        return dataclasses.asdict(data)
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
    # Fast path: dict with string keys (most common case)
    if type(data) is dict:
        for k in data:
            if type(k) is not str:
                return None
        return data
    mapping = _coerce_to_mapping(data)
    if mapping is None:
        return None
    if not all(isinstance(k, str) for k in mapping):
        return None
    return cast(collections.abc.Mapping[str, object], mapping)


def parse_namedtuple[T](
    validator: ValidatorProtocol, target: type[T], data: object
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
            missing_key = next(iter(missing))
            raise ValidationError(target, mapping, path=f"missing field: {missing_key}")

        extra = data_keys - all_keys
        if extra:
            extra_key = next(iter(extra))
            raise ValidationError(target, mapping, path=f"unexpected key: {extra_key}")

        validated: dict[str, Any] = {}
        for field in fields:
            if field in data_keys:
                validated[field] = validator.validate(hints[field], mapping[field])
            # Fields not in data_keys have defaults; omit them so NamedTuple uses its default

        return target(**validated)

    if isinstance(data, (list, tuple)):
        # Positional construction path - length must match exactly
        if len(data) != len(fields):
            raise ValidationError(target, data)
        validated_items = [
            validator.validate(hints[field], item) for field, item in zip(fields, data)
        ]
        return target(*validated_items)

    raise ValidationError(target, data)


def parse_dataclass[T](
    validator: ValidatorProtocol, target: type[T], data: object
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
        raise ValidationError(target, data)

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
        missing_key = next(iter(missing))
        raise ValidationError(target, mapping, path=f"missing field: {missing_key}")

    # Check for extra keys
    extra = data_keys - all_keys
    if extra:
        extra_key = next(iter(extra))
        raise ValidationError(target, mapping, path=f"unexpected key: {extra_key}")

    # Validate and coerce each provided field
    validated: dict[str, Any] = {}
    for key in data_keys:
        validated[key] = validator.validate(hints[key], mapping[key])

    return target(**validated)


def parse_union(validator: ValidatorProtocol, target: type[Any], data: object) -> Any:
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
        raise ValidationError(target, data)

    # Try each type in order
    for union_type in args:
        try:
            return validator.validate(union_type, data)
        except ValidationError:
            continue

    # None matched - raise error
    raise ValidationError(target, data)


def parse_literal(validator: ValidatorProtocol, target: type[Any], data: object) -> Any:
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
    raise ValidationError(target, data)


def parse_any(validator: ValidatorProtocol, target: type[Any], data: object) -> Any:
    """Accept any data without validation.

    Exposed for composition in custom handlers.
    """
    return data


# ---------------------------------------------------------------------------
# Compiler functions - return closures for maximum performance
# ---------------------------------------------------------------------------


def compile_int(validator: Validator, target: type[int]) -> CompiledValidator[int]:
    """Compile a validator for int."""

    def validate_int(data: object) -> int:
        if type(data) is bool:
            raise ValidationError(target, data)
        if type(data) is not int:
            raise ValidationError(target, data)
        return data  # type: ignore[return-value]

    return validate_int


def compile_float(
    validator: Validator, target: type[float]
) -> CompiledValidator[float]:
    """Compile a validator for float."""

    def validate_float(data: object) -> float:
        if type(data) is bool:
            raise ValidationError(target, data)
        if type(data) is float:
            return data  # type: ignore[return-value]
        if type(data) is int:
            return float(data)  # type: ignore[arg-type]
        raise ValidationError(target, data)

    return validate_float


def compile_str(validator: Validator, target: type[str]) -> CompiledValidator[str]:
    """Compile a validator for str."""

    def validate_str(data: object) -> str:
        if type(data) is not str:
            raise ValidationError(target, data)
        return data  # type: ignore[return-value]

    return validate_str


def compile_bool(validator: Validator, target: type[bool]) -> CompiledValidator[bool]:
    """Compile a validator for bool."""

    def validate_bool(data: object) -> bool:
        if type(data) is not bool:
            raise ValidationError(target, data)
        return data  # type: ignore[return-value]

    return validate_bool


def compile_none(validator: Validator, target: type[None]) -> CompiledValidator[None]:
    """Compile a validator for None."""

    def validate_none(data: object) -> None:
        if data is not None:
            raise ValidationError(target, data)
        return None

    return validate_none


def compile_any(validator: Validator, target: type[Any]) -> CompiledValidator[Any]:
    """Compile a validator for Any."""

    def validate_any(data: object) -> Any:
        return data

    return validate_any


def compile_list(
    validator: Validator, target: type[list[Any]]
) -> CompiledValidator[list[Any]]:
    """Compile a validator for list[T]."""
    args = get_args(target)
    if not args:

        def validate_list_untyped(data: object) -> list[Any]:
            if type(data) is list:
                return list(data)
            if isinstance(data, tuple):
                return list(data)
            raise ValidationError(target, data)

        return validate_list_untyped

    elem_validate = validator._compile(args[0])

    def validate_list(data: object) -> list[Any]:
        if type(data) is list:
            return [elem_validate(item) for item in data]
        if isinstance(data, tuple):
            return [elem_validate(item) for item in data]
        raise ValidationError(target, data)

    return validate_list


def compile_tuple(
    validator: Validator, target: type[tuple[Any, ...]]
) -> CompiledValidator[tuple[Any, ...]]:
    """Compile a validator for tuple[T, ...] or tuple[T1, T2, ...]."""
    args = get_args(target)
    if not args:

        def validate_tuple_untyped(data: object) -> tuple[Any, ...]:
            if isinstance(data, (list, tuple)):
                return tuple(data)
            raise ValidationError(target, data)

        return validate_tuple_untyped

    # Check for homogeneous tuple[T, ...]
    if len(args) == 2 and args[1] is Ellipsis:
        elem_validate = validator._compile(args[0])

        def validate_tuple_homogeneous(data: object) -> tuple[Any, ...]:
            if isinstance(data, (list, tuple)):
                return tuple(elem_validate(item) for item in data)
            raise ValidationError(target, data)

        return validate_tuple_homogeneous

    # Fixed-length tuple[T1, T2, ...]
    elem_validators = tuple(validator._compile(t) for t in args)
    expected_len = len(elem_validators)

    def validate_tuple_fixed(data: object) -> tuple[Any, ...]:
        if not isinstance(data, (list, tuple)):
            raise ValidationError(target, data)
        if len(data) != expected_len:
            raise ValidationError(target, data)
        return tuple(v(item) for v, item in zip(elem_validators, data))

    return validate_tuple_fixed


def compile_dict(
    validator: Validator, target: type[dict[Any, Any]]
) -> CompiledValidator[dict[Any, Any]]:
    """Compile a validator for dict[K, V]."""
    args = get_args(target)
    if not args:

        def validate_dict_untyped(data: object) -> dict[Any, Any]:
            if type(data) is dict:
                return dict(data)
            mapping = _coerce_to_mapping(data)
            if mapping is None:
                raise ValidationError(target, data)
            return dict(mapping)

        return validate_dict_untyped

    key_type, val_type = args
    val_validate = validator._compile(val_type)

    # Optimize for dict[str, T] - inline key validation (very common pattern)
    if key_type is str:

        def validate_dict_str_key(data: object) -> dict[Any, Any]:
            if type(data) is dict:
                result: dict[str, Any] = {}
                for k, v in data.items():
                    if type(k) is not str:
                        raise ValidationError(str, k)
                    result[k] = val_validate(v)
                return result
            mapping = _coerce_to_mapping(data)
            if mapping is None:
                raise ValidationError(target, data)
            result = {}
            for k, v in mapping.items():
                if type(k) is not str:
                    raise ValidationError(str, k)
                result[k] = val_validate(v)
            return result

        return validate_dict_str_key

    key_validate = validator._compile(key_type)

    def validate_dict(data: object) -> dict[Any, Any]:
        if type(data) is dict:
            return {key_validate(k): val_validate(v) for k, v in data.items()}
        mapping = _coerce_to_mapping(data)
        if mapping is None:
            raise ValidationError(target, data)
        return {key_validate(k): val_validate(v) for k, v in mapping.items()}

    return validate_dict


def compile_set(
    validator: Validator, target: type[set[Any]]
) -> CompiledValidator[set[Any]]:
    """Compile a validator for set[T]."""
    args = get_args(target)
    if not args:

        def validate_set_untyped(data: object) -> set[Any]:
            if isinstance(data, (set, frozenset)):
                return set(data)
            raise ValidationError(target, data)

        return validate_set_untyped

    elem_validate = validator._compile(args[0])

    def validate_set(data: object) -> set[Any]:
        if isinstance(data, (set, frozenset)):
            return {elem_validate(item) for item in data}
        raise ValidationError(target, data)

    return validate_set


def compile_frozenset(
    validator: Validator, target: type[frozenset[Any]]
) -> CompiledValidator[frozenset[Any]]:
    """Compile a validator for frozenset[T]."""
    args = get_args(target)
    if not args:

        def validate_frozenset_untyped(data: object) -> frozenset[Any]:
            if isinstance(data, (set, frozenset)):
                return frozenset(data)
            raise ValidationError(target, data)

        return validate_frozenset_untyped

    elem_validate = validator._compile(args[0])

    def validate_frozenset(data: object) -> frozenset[Any]:
        if isinstance(data, (set, frozenset)):
            return frozenset(elem_validate(item) for item in data)
        raise ValidationError(target, data)

    return validate_frozenset


def compile_union(validator: Validator, target: type[Any]) -> CompiledValidator[Any]:
    """Compile a validator for Union[T1, T2, ...]."""
    args = get_args(target)
    if not args:
        raise ValidationError(target, None)

    # Optimize for T | None (Optional[T]) - very common pattern
    if len(args) == 2 and type(None) in args:
        other_type = args[0] if args[1] is type(None) else args[1]
        other_validator = validator._compile(other_type)

        def validate_optional(data: object) -> Any:
            if data is None:
                return None
            return other_validator(data)

        return validate_optional

    # Check if all types are simple primitives (can use type dispatch)
    primitive_types = {int, float, str, bool, type(None)}
    if all(t in primitive_types for t in args):
        # Build type set for O(1) membership check
        has_bool = bool in args
        has_int = int in args
        has_float = float in args
        has_str = str in args
        has_none = type(None) in args
        # Check if float comes before int (affects coercion)
        float_before_int = has_float and has_int and args.index(float) < args.index(int)

        def validate_primitive_union(data: object) -> Any:
            data_type = type(data)
            # Check each type inline - avoids dict lookup and redundant type() calls
            if data_type is bool:
                if has_bool:
                    return data
                raise ValidationError(target, data)
            if data_type is int:
                # If float comes before int in union, coerce int to float
                if float_before_int:
                    return float(data)
                if has_int:
                    return data
                if has_float:
                    return float(data)
                raise ValidationError(target, data)
            if data_type is str:
                if has_str:
                    return data
                raise ValidationError(target, data)
            if data_type is float:
                if has_float:
                    return data
                raise ValidationError(target, data)
            if data is None:
                if has_none:
                    return None
                raise ValidationError(target, data)
            raise ValidationError(target, data)

        return validate_primitive_union

    # Optimize for 2-type union (no loop overhead)
    if len(args) == 2:
        v0 = validator._compile(args[0])
        v1 = validator._compile(args[1])

        def validate_union_2(data: object) -> Any:
            try:
                return v0(data)
            except ValidationError:
                pass
            try:
                return v1(data)
            except ValidationError:
                pass
            raise ValidationError(target, data)

        return validate_union_2

    # Build input-type dispatch table to avoid backtracking
    # Group validators by what input types they can accept
    validators = tuple(validator._compile(t) for t in args)
    dict_validators: list[CompiledValidator[Any]] = []
    list_validators: list[CompiledValidator[Any]] = []
    other_validators: list[CompiledValidator[Any]] = []

    for t, v in zip(args, validators):
        origin = get_origin(t)
        # Types that accept dict input
        if origin is dict or is_typeddict(t) or _is_dataclass_type(t):
            dict_validators.append(v)
        # Types that accept list/tuple input
        elif origin in (list, tuple) or _is_namedtuple(t):
            list_validators.append(v)
        else:
            # Primitives and other types - could match anything
            other_validators.append(v)

    # Convert to tuples for faster iteration
    dict_validators_t = tuple(dict_validators)
    list_validators_t = tuple(list_validators)
    other_validators_t = tuple(other_validators)

    def validate_union(data: object) -> Any:
        data_type = type(data)
        # Dispatch based on input type to avoid unnecessary backtracking
        if data_type is dict:
            # Try dict-accepting validators first, then others
            for v in dict_validators_t:
                try:
                    return v(data)
                except ValidationError:
                    continue
            for v in other_validators_t:
                try:
                    return v(data)
                except ValidationError:
                    continue
        elif data_type is list or isinstance(data, tuple):
            # Try list-accepting validators first, then others
            for v in list_validators_t:
                try:
                    return v(data)
                except ValidationError:
                    continue
            for v in other_validators_t:
                try:
                    return v(data)
                except ValidationError:
                    continue
        else:
            # For other types (primitives), try other_validators first
            for v in other_validators_t:
                try:
                    return v(data)
                except ValidationError:
                    continue
            # Then try all validators in case of unusual coercions
            for v in validators:
                try:
                    return v(data)
                except ValidationError:
                    continue
        raise ValidationError(target, data)

    return validate_union


def compile_literal(validator: Validator, target: type[Any]) -> CompiledValidator[Any]:
    """Compile a validator for Literal[v1, v2, ...]."""
    allowed = get_args(target)

    def validate_literal(data: object) -> Any:
        for val in allowed:
            if type(data) is type(val) and data == val:
                return data
        raise ValidationError(target, data)

    return validate_literal


def compile_typed_dict(
    validator: Validator, target: type[Any]
) -> CompiledValidator[Any]:
    """Compile a validator for TypedDict."""
    hints = get_type_hints(target)
    required_keys = getattr(target, "__required_keys__", frozenset())
    field_validators = {key: validator._compile(hint) for key, hint in hints.items()}

    def validate_typed_dict(data: object) -> Any:
        # Fast path for dict input
        if type(data) is dict:
            for k in data:
                if type(k) is not str:
                    raise ValidationError(target, data)
            mapping = data
        else:
            mapping = _coerce_to_str_mapping(data)
            if mapping is None:
                raise ValidationError(target, data)

        # Check for missing required keys
        for key in required_keys:
            if key not in mapping:
                raise ValidationError(target, mapping, path=f"missing key: {key}")

        # Check for extra keys and validate in one pass
        result: dict[str, Any] = {}
        for key, value in mapping.items():
            v = field_validators.get(key)
            if v is None:
                raise ValidationError(target, mapping, path=f"unexpected key: {key}")
            result[key] = v(value)
        return result

    return validate_typed_dict


def compile_namedtuple(
    validator: Validator, target: type[Any]
) -> CompiledValidator[Any]:
    """Compile a validator for NamedTuple."""
    fields: tuple[str, ...] = target._fields  # type: ignore[union-attr]
    hints = get_type_hints(target)
    defaults: dict[str, object] = {}
    if hasattr(target, "_field_defaults"):
        defaults = target._field_defaults  # type: ignore[union-attr]

    all_keys = frozenset(fields)
    required_keys = frozenset(f for f in fields if f not in defaults)
    field_validators = {field: validator._compile(hints[field]) for field in fields}

    def validate_namedtuple(data: object) -> Any:
        mapping = _coerce_to_str_mapping(data)
        if mapping is not None:
            data_keys = frozenset(mapping.keys())

            for key in required_keys:
                if key not in data_keys:
                    raise ValidationError(target, mapping, path=f"missing field: {key}")

            for key in data_keys:
                if key not in all_keys:
                    raise ValidationError(
                        target, mapping, path=f"unexpected key: {key}"
                    )

            validated: dict[str, Any] = {}
            for field in fields:
                if field in data_keys:
                    validated[field] = field_validators[field](mapping[field])

            return target(**validated)

        if isinstance(data, (list, tuple)):
            if len(data) != len(fields):
                raise ValidationError(target, data)
            validated_items = [
                field_validators[field](item) for field, item in zip(fields, data)
            ]
            return target(*validated_items)

        raise ValidationError(target, data)

    return validate_namedtuple


def compile_dataclass(
    validator: Validator, target: type[Any]
) -> CompiledValidator[Any]:
    """Compile a validator for dataclass."""
    hints = get_type_hints(target)
    dc_fields = dataclasses.fields(cast(type, target))
    field_names = [f.name for f in dc_fields]
    num_fields = len(field_names)

    # Check if all fields are required (no defaults)
    all_required = all(
        f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
        for f in dc_fields
    )

    # Compile field validators
    field_validators_list = [validator._compile(hints[name]) for name in field_names]

    if all_required:
        # Generate optimized code for all-required case
        return _generate_dataclass_validator(
            target, field_names, field_validators_list, num_fields
        )

    # Fallback for dataclasses with optional fields
    required_keys = frozenset(
        f.name
        for f in dc_fields
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    )
    field_validators = dict(zip(field_names, field_validators_list))

    def validate_dataclass(data: object) -> Any:
        # Fast path for dict input (most common case)
        if type(data) is dict:
            mapping = data
        else:
            mapping = _coerce_to_mapping(data)
            if mapping is None:
                raise ValidationError(target, data)

        # Check for missing required keys
        for key in required_keys:
            if key not in mapping:
                raise ValidationError(target, mapping, path=f"missing field: {key}")

        # Check for extra keys and validate in one pass
        validated: dict[str, Any] = {}
        for key, value in mapping.items():
            v = field_validators.get(key)
            if v is None:
                raise ValidationError(target, mapping, path=f"unexpected key: {key}")
            validated[key] = v(value)

        return target(**validated)

    return validate_dataclass


def _generate_dataclass_validator(
    target: type,
    field_names: list[str],
    field_validators: list[CompiledValidator[Any]],
    num_fields: int,
) -> CompiledValidator[Any]:
    """Generate optimized validator for dataclass with all required fields."""
    # Build the validation expressions for each field
    field_exprs = ", ".join(
        f"{name}=_v{i}(_d[{name!r}])" for i, name in enumerate(field_names)
    )
    expected_keys = set(field_names)

    # Generate the function code
    code = f"""
def _validate(_d):
    try:
        return _target({field_exprs})
    except KeyError as _e:
        raise _ValidationError(_target, _d, path=f"missing field: {{_e.args[0]}}")
"""

    # Build the namespace with all required references
    namespace: dict[str, Any] = {
        "_target": target,
        "_ValidationError": ValidationError,
    }
    for i, v in enumerate(field_validators):
        namespace[f"_v{i}"] = v

    exec(code, namespace)  # noqa: S102
    inner_validate = namespace["_validate"]

    # Wrap with type checking and extra key detection
    def validate_dataclass(data: object) -> Any:
        if type(data) is dict:
            _d = data
        else:
            _d = _coerce_to_mapping(data)
            if _d is None:
                raise ValidationError(target, data)

        # Validate fields first (KeyError catches missing fields)
        result = inner_validate(_d)

        # Check for extra keys only if count differs (happy path: no set operations)
        if len(_d) != num_fields:
            _extra = set(_d.keys()) - expected_keys
            raise ValidationError(
                target, _d, path=f"unexpected key: {next(iter(_extra))}"
            )

        return result

    return validate_dataclass


# Private default validator instance (frozen to prevent modification)
_DEFAULT_VALIDATOR = Validator(frozen=True)

# Try to import Rust accelerator
_RUST_VALIDATOR: Any = None
try:
    from frfr._core import Validator as _RustValidator

    _RUST_VALIDATOR = _RustValidator()
except ImportError:
    pass


def _contains_structured_type(target: type) -> bool:
    """Check if a type contains dataclass, TypedDict, or NamedTuple."""
    # Check TypedDict
    if is_typeddict(target):
        return True

    # Check dataclass (must be a class, not instance)
    if dataclasses.is_dataclass(target) and isinstance(target, type):
        return True

    # Check NamedTuple (tuple subclass with _fields)
    if isinstance(target, type) and issubclass(target, tuple) and hasattr(target, "_fields"):
        return True

    # Check generic args recursively
    for arg in get_args(target):
        if isinstance(arg, type) or hasattr(arg, "__origin__"):
            if _contains_structured_type(arg):
                return True

    return False


# Cache for structured type checks
_STRUCTURED_TYPE_CACHE: dict[int, bool] = {}


def validate[T](target: type[T], data: object) -> T:
    """Validate and coerce data to the given type.

    This is the main entry point for frfr. Uses the default validator
    with built-in handlers for standard types.

    Automatically uses Rust acceleration for types that benefit from it
    (primitives, lists, dicts without dataclasses).

    Args:
        target: The type to validate against.
        data: The data to validate.

    Returns:
        The validated data, coerced to the target type if needed.

    Raises:
        ValidationError: If the data does not match the expected type.
    """
    # If Rust is available, check if we should use it
    if _RUST_VALIDATOR is not None:
        target_id = id(target)
        has_structured = _STRUCTURED_TYPE_CACHE.get(target_id)
        if has_structured is None:
            has_structured = _contains_structured_type(target)
            _STRUCTURED_TYPE_CACHE[target_id] = has_structured

        # Use Rust for types without structured data (3-4x faster)
        if not has_structured:
            return _RUST_VALIDATOR.validate(target, data)  # type: ignore[return-value]

    # Use Python for types with structured data (avoids FFI overhead)
    return _DEFAULT_VALIDATOR.validate(target, data)
