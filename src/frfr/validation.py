"""Core validation logic for frfr."""

import collections.abc
import dataclasses
import functools
import threading
import types

from typing import (
    Annotated,
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


@functools.cache
def _get_type_hints(target: type) -> dict[str, Any]:
    """Return type hints for a type, cached permanently per type.

    get_type_hints() is expensive: it resolves forward references by inspecting
    the module's globals and walks the MRO. Profiling shows it accounts for ~53%
    of total validation time when called on every TypedDict/dataclass/NamedTuple
    validation. Since a type's hints never change at runtime, caching is safe and
    effectively makes this free after the first call per type.
    """
    return get_type_hints(target)


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


class CompiledValidator[T](Protocol):
    """A pre-compiled validator closure produced by compile_* functions.

    Unlike Handler, a CompiledValidator has already captured its target type,
    child validators, and any pre-computed type metadata (get_args results,
    field hints, etc.) at build time. Call-time cost is just the function call
    itself — no type introspection per invocation.
    """

    def __call__(self, data: object, path: str) -> T: ...


class CompileFunc(Protocol):
    """A module-level compile function that builds a CompiledValidator closure.

    Receives the full target type (important for generics like list[str]) and
    a get_compiled callable for recursively compiling child types.
    """

    def __call__(
        self,
        target: object,
        get_compiled: Callable[[object], CompiledValidator[Any]],
    ) -> CompiledValidator[Any]: ...


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_namedtuple(t: object) -> bool:
    """Return True if t is a NamedTuple class (not an instance)."""
    return isinstance(t, type) and issubclass(t, tuple) and hasattr(t, "_fields")


@functools.cache
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


def _is_newtype(t: object) -> bool:
    """Return True if t is a NewType (callable with __supertype__, not a plain class)."""
    return callable(t) and not isinstance(t, type) and hasattr(t, "__supertype__")


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
    if type(data) is dict:
        return (
            cast(collections.abc.Mapping[str, object], data)
            if all(isinstance(k, str) for k in data)
            else None
        )
    mapping = _coerce_to_mapping(data)
    if mapping is None:
        return None
    if not all(isinstance(k, str) for k in mapping):
        return None
    return cast(collections.abc.Mapping[str, object], mapping)


# ---------------------------------------------------------------------------
# Module-level compile functions
# ---------------------------------------------------------------------------


def compile_int(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for int."""

    def _int(data: object, path: str) -> Any:
        if type(data) is bool:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        if type(data) is not int:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return data

    return _int


def compile_float(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for float."""

    def _float(data: object, path: str) -> Any:
        if type(data) is bool:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        if type(data) is float:
            return data
        if type(data) is int:
            return float(data)
        raise ValidationError(target, data, path=path)  # type: ignore[arg-type]

    return _float


def compile_str(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for str."""

    def _str(data: object, path: str) -> Any:
        if type(data) is not str:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return data

    return _str


def compile_bool(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for bool."""

    def _bool(data: object, path: str) -> Any:
        if type(data) is not bool:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return data

    return _bool


def compile_none(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for None."""

    def _none(data: object, path: str) -> Any:
        if data is not None:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return None

    return _none


def compile_any(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for Any (accepts everything)."""
    return lambda data, path: data


def compile_list(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for list."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (list, tuple)):
                raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
            return list(data)

        return _untyped

    elem = get_compiled(args[0])

    def _typed(data: object, path: str) -> Any:
        if not isinstance(data, (list, tuple)):
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return [elem(item, f"{path}[{i}]") for i, item in enumerate(data)]

    return _typed


def compile_tuple(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for tuple."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (list, tuple)):
                raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
            return tuple(data)

        return _untyped

    if len(args) == 2 and args[1] is Ellipsis:
        elem = get_compiled(args[0])

        def _homo(data: object, path: str) -> Any:
            if not isinstance(data, (list, tuple)):
                raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
            return tuple(elem(item, f"{path}[{i}]") for i, item in enumerate(data))

        return _homo

    field_fns = tuple(get_compiled(t) for t in args)
    n = len(args)

    def _fixed(data: object, path: str) -> Any:
        if not isinstance(data, (list, tuple)):
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        if len(data) != n:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return tuple(
            fn(item, f"{path}[{i}]")
            for i, (fn, item) in enumerate(zip(field_fns, data))
        )

    return _fixed


def compile_dict(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for dict."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            mapping = _coerce_to_mapping(data)
            if mapping is None:
                raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
            return dict(mapping)

        return _untyped

    key_type, val_type = args
    key_fn = get_compiled(key_type)
    val_fn = get_compiled(val_type)

    def _typed(data: object, path: str) -> Any:
        mapping = _coerce_to_mapping(data)
        if mapping is None:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        result: dict[Any, Any] = {}
        for k, v in mapping.items():
            key_segment = _format_key_path_segment(k)
            key_path = f"{path}{key_segment}" if path else key_segment
            result[key_fn(k, f"{key_path}[key]")] = val_fn(v, key_path)
        return result

    return _typed


def compile_set(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for set."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (set, frozenset)):
                raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
            return set(data)

        return _untyped

    elem = get_compiled(args[0])

    def _typed(data: object, path: str) -> Any:
        if not isinstance(data, (set, frozenset)):
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return {elem(item, path) for item in data}

    return _typed


def compile_frozenset(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for frozenset."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (set, frozenset)):
                raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
            return frozenset(data)

        return _untyped

    elem = get_compiled(args[0])

    def _typed(data: object, path: str) -> Any:
        if not isinstance(data, (set, frozenset)):
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]
        return frozenset(elem(item, path) for item in data)

    return _typed


def compile_newtype(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for NewType — unwraps to the base type."""
    return get_compiled(target.__supertype__)  # type: ignore[union-attr]


def compile_annotated(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for Annotated — ignores metadata, validates the inner type."""
    return get_compiled(get_args(target)[0])


def compile_union(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for Union types."""
    args = get_args(target)
    if not args:

        def _empty(data: object, path: str) -> Any:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]

        return _empty

    # T | None (Optional[T]): None check avoids try/except entirely on the happy path.
    if len(args) == 2 and type(None) in args:
        other = args[0] if args[1] is type(None) else args[1]
        other_fn = get_compiled(other)

        def _optional(data: object, path: str) -> Any:
            if data is None:
                return None
            return other_fn(data, path)

        return _optional

    # 2-type union: unrolled to avoid list iteration overhead.
    if len(args) == 2:
        fn0 = get_compiled(args[0])
        fn1 = get_compiled(args[1])

        def _union2(data: object, path: str) -> Any:
            try:
                return fn0(data, path)
            except ValidationError:
                pass
            try:
                return fn1(data, path)
            except ValidationError:
                pass
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]

        return _union2

    # N-type union: pre-compiled members tuple, single loop.
    member_fns = tuple(get_compiled(t) for t in args)

    def _unionN(data: object, path: str) -> Any:
        for fn in member_fns:
            try:
                return fn(data, path)
            except ValidationError:
                continue
        raise ValidationError(target, data, path=path)  # type: ignore[arg-type]

    return _unionN


def compile_literal(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for Literal types."""
    allowed = get_args(target)

    def _literal(data: object, path: str) -> Any:
        for val in allowed:
            if type(data) is type(val) and data == val:
                return data
        raise ValidationError(target, data, path=path)  # type: ignore[arg-type]

    return _literal


def compile_typed_dict(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for TypedDict types."""
    target_type = cast(type, target)
    hints = _get_type_hints(target_type)
    required_keys: frozenset[str] = getattr(
        target_type, "__required_keys__", frozenset()
    )
    optional_keys: frozenset[str] = getattr(
        target_type, "__optional_keys__", frozenset()
    )
    all_keys = required_keys | optional_keys
    field_fns = {key: get_compiled(vtype) for key, vtype in hints.items()}
    # Precompute path segments for known keys (avoids isinstance+isidentifier per key)
    key_segments = {key: _format_key_path_segment(key) for key in all_keys}

    def _typed_dict(data: object, path: str) -> Any:
        if type(data) is dict:
            mapping: collections.abc.Mapping[str, object] = cast(
                collections.abc.Mapping[str, object], data
            )
        else:
            _mapping = _coerce_to_str_mapping(data)
            if _mapping is None:
                raise ValidationError(target_type, data, path=path)
            mapping = _mapping

        data_keys: set[str] = set(mapping.keys())

        missing = required_keys - data_keys
        if missing:
            missing_key = min(missing)
            key_segment = key_segments[missing_key]
            key_path = f"{path}{key_segment}" if path else key_segment
            raise ValidationError(
                target_type, mapping, path=key_path, message="missing required key"
            )

        extra = data_keys - all_keys
        if extra:
            extra_key = min(extra)
            # Extra keys aren't precomputed, format on demand (error path only)
            key_segment = _format_key_path_segment(extra_key)
            key_path = f"{path}{key_segment}" if path else key_segment
            raise ValidationError(
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
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for NamedTuple types."""
    target_type = cast(type, target)
    fields: tuple[str, ...] = target_type._fields  # type: ignore[union-attr]
    hints = _get_type_hints(target_type)
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
            mapping = _coerce_to_str_mapping(data)

        if mapping is not None:
            data_keys = frozenset(mapping.keys())

            missing = required_keys - data_keys
            if missing:
                missing_key = min(missing)
                seg = field_segments[missing_key]
                field_path = f"{path}{seg}" if path else seg
                raise ValidationError(
                    target_type,
                    mapping,
                    path=field_path,
                    message="missing required field",
                )

            extra = data_keys - all_keys
            if extra:
                extra_key = min(extra)
                # Extra keys aren't precomputed, format on demand (error path only)
                seg = _format_key_path_segment(extra_key)
                field_path = f"{path}{seg}" if path else seg
                raise ValidationError(
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
                raise ValidationError(target_type, data, path=path)
            return target_type(
                *(
                    field_fns[field](item, f"{path}[{i}]")
                    for i, (field, item) in enumerate(zip(fields, data))
                )
            )

        raise ValidationError(target_type, data, path=path)

    return _namedtuple


def compile_dataclass(
    target: object,
    get_compiled: Callable[[object], CompiledValidator[Any]],
) -> CompiledValidator[Any]:
    """Compile a validator for dataclass types."""
    target_type = cast(type, target)
    hints = _get_type_hints(target_type)
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
            _mapping = _coerce_to_mapping(data)
            if _mapping is None:
                raise ValidationError(target_type, data, path=path)
            mapping = _mapping

        data_keys = frozenset(mapping.keys())

        missing = required_keys - data_keys
        if missing:
            missing_key = min(missing)
            seg = field_segments[missing_key]
            field_path = f"{path}{seg}" if path else seg
            raise ValidationError(
                target_type,
                mapping,
                path=field_path,
                message="missing required field",
            )

        extra = data_keys - all_keys
        if extra:
            extra_key = min(extra)
            # Extra keys aren't precomputed, format on demand (error path only)
            seg = _format_key_path_segment(extra_key)
            field_path = f"{path}{seg}" if path else seg
            raise ValidationError(
                target_type, mapping, path=field_path, message="unexpected field"
            )

        validated: dict[str, Any] = {}
        for key in data_keys:
            seg = field_segments[key]
            key_path = f"{path}{seg}" if path else seg
            validated[key] = field_fns[key](mapping[key], key_path)
        return target_type(**validated)

    return _dataclass


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------


class Validator:
    """Type validator with extensible handlers.

    Handlers receive the validator instance to enable recursive validation
    of nested types (e.g., list[int] needs to validate each element).

    All validators start with built-in compilers for standard types.
    Use `frozen=True` to prevent further registration (used internally
    for the default validator).

    Memory note: the compiled cache grows by one entry per distinct type seen.
    In practice this is fine since the number of types in an application is
    small and fixed. If you need to bound memory (e.g., validating many
    dynamically-generated types), create a new Validator() instance to get
    a fresh cache.
    """

    def __init__(self, *, frozen: bool = False) -> None:
        self._handlers: dict[Any, Handler[Any]] = {}
        self._predicate_handlers: list[
            tuple[Callable[[object], bool], Handler[Any]]
        ] = []
        self._compilers: dict[Any, CompileFunc] = {}
        self._predicate_compilers: list[
            tuple[Callable[[object], bool], CompileFunc]
        ] = []
        self._compiled: dict[int, CompiledValidator[Any]] = {}
        # Strong references to every type we've compiled. Prevents CPython from
        # GC-ing type objects (e.g. temporary `float | None` in test calls) and
        # reusing their id() for a new type — which would cause _compiled to return
        # the wrong cached fn for the new type.
        self._compiled_refs: list[object] = []
        # Lock for thread-safe access to _compiled and _compiling.
        self._compiled_lock = threading.RLock()
        # Set of type ids currently being compiled (for recursion detection).
        self._compiling: set[int] = set()
        self._frozen = frozen
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in compilers. Called during __init__."""
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
        self._compilers[Annotated] = compile_annotated
        self._compilers[Union] = compile_union
        self._compilers[types.UnionType] = compile_union
        self._compilers[Literal] = compile_literal
        self._predicate_compilers = [
            (_is_newtype, compile_newtype),
            (is_typeddict, compile_typed_dict),
            (_is_namedtuple, compile_namedtuple),
            (_is_dataclass_type, compile_dataclass),
        ]

    def register_type_handler[T](self, target: type[T], handler: Handler[T]) -> None:
        """Register a handler for an exact target type.

        Args:
            target: The type to register a handler for.
            handler: A function that takes (validator, target_type, data, path) and
                     returns a validated/coerced instance of target_type.
                     The validator is passed to enable recursive validation.

        Raises:
            RuntimeError: If the validator is frozen.
        """
        if self._frozen:
            raise RuntimeError("Cannot register on a frozen validator")
        # Compiled closures capture child validators at build time, so a new
        # handler for (e.g.) int would silently be ignored by any already-compiled
        # list[int] validator. Clearing the cache forces a full recompile on next use.
        with self._compiled_lock:
            self._handlers[target] = handler
            self._compiled.clear()
            self._compiled_refs.clear()
            self._compiling.clear()

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
            handler: A function that takes (validator, target_type, data, path) and
                     returns a validated/coerced instance of target_type.

        Raises:
            RuntimeError: If the validator is frozen.
        """
        if self._frozen:
            raise RuntimeError("Cannot register on a frozen validator")
        # Same reasoning as register_type_handler: compiled closures capture
        # child validators at build time, so a new predicate handler must
        # invalidate the cache to take effect on already-seen types.
        with self._compiled_lock:
            self._predicate_handlers.insert(0, (predicate, handler))
            self._compiled.clear()
            self._compiled_refs.clear()
            self._compiling.clear()

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
        return cast(T, self._get_compiled(target)(data, path))

    def _get_compiled(self, target: object) -> CompiledValidator[Any]:
        """Return a compiled validator for target, building and caching it on first call.

        Compiled validators are closures that pre-capture all type information
        (get_args results, field hints, child compiled validators) so repeated
        calls pay only an id() dict lookup plus a direct function call — no
        per-call type introspection.

        Keyed by id(target) to distinguish e.g. int | float from float | int
        (Python treats these as equal but they have different arg orderings).

        Recursive types are handled via _compiling set: if we're asked to compile
        a type that's already mid-compilation, we return a late-binding wrapper
        that defers the real lookup to call time (by which point compilation of
        the outer type will have finished and the real fn will be in the cache).

        Thread-safe: uses double-checked locking. The fast path (cache hit) avoids
        the lock entirely since dict.get() is atomic in CPython due to the GIL.
        """
        tid = id(target)

        # Fast path: check cache without lock (dict.get is atomic in CPython)
        fn = self._compiled.get(tid)
        if fn is not None:
            return fn

        # Slow path: acquire lock for compilation
        with self._compiled_lock:
            # Double-check after acquiring lock
            fn = self._compiled.get(tid)
            if fn is not None:
                return fn

            if tid in self._compiling:
                # Recursive type detected: return a wrapper that looks up the
                # real compiled fn at call time. By then, the outer _get_compiled
                # call will have stored the real fn under this id.
                def _recursive_wrapper(data: object, path: str) -> Any:
                    with self._compiled_lock:
                        compiled_fn = self._compiled.get(tid)
                    if compiled_fn is None:
                        raise RuntimeError(
                            f"Compilation failed for recursive type {target!r}"
                        )
                    return compiled_fn(data, path)

                return _recursive_wrapper

            self._compiling.add(tid)
            try:
                fn = self._build_compiled(target)
                self._compiled[tid] = fn
                self._compiled_refs.append(target)  # keep type alive; see __init__
                return fn
            finally:
                self._compiling.discard(tid)

    def _build_compiled(self, target: object) -> CompiledValidator[Any]:
        """Resolve the handler/compiler for target and build an optimized closure.

        Lookup precedence (highest to lowest):
        1. User exact-type handler (_handlers)
        2. User predicate handler (_predicate_handlers, most recently registered wins)
        3. Built-in exact-type compiler (_compilers)
        4. Built-in predicate compiler (_predicate_compilers)
        5. Origin-based lookup for parameterized types (e.g., list[int] → list)
        """
        gc = self._get_compiled

        # 1. User exact-type handler
        handler = self._handlers.get(target)
        if handler is not None:
            v, t, h = self, target, handler
            return lambda data, path: h(v, t, data, path)  # type: ignore[arg-type]

        # 2. User predicate handlers (most recently registered wins)
        for pred, hand in self._predicate_handlers:
            if pred(target):
                v, t, h = self, target, hand
                return lambda data, path: h(v, t, data, path)  # type: ignore[arg-type]

        # 3. Built-in exact-type compiler
        compiler = self._compilers.get(target)
        if compiler is not None:
            return compiler(target, gc)

        # 4. Built-in predicate compilers
        for pred, comp in self._predicate_compilers:
            if pred(target):
                return comp(target, gc)

        # 5. Origin-based (parameterized types like list[int], int | str)
        origin = get_origin(target)
        if origin is not None:
            compiler = self._compilers.get(origin)
            if compiler is not None:
                return compiler(target, gc)

        def _unknown(data: object, path: str) -> Any:
            raise ValidationError(target, data, path=path)  # type: ignore[arg-type]

        return _unknown


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
