"""Core validation machinery: error class, Validator, and validate()."""

import collections.abc
import datetime as dt
import decimal
import pathlib
import threading
import types
import uuid
from typing import (
    Annotated,
    Any,
    Callable,
    Final,
    Literal,
    Union,
    cast,
    get_origin,
    is_typeddict,
)

import frfr.containers
import frfr.scalars
import frfr.structured
import frfr.types
import frfr.utils


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
        self._handlers: dict[Any, frfr.types.Handler[Any]] = {}
        self._predicate_handlers: list[
            tuple[Callable[[object], bool], frfr.types.Handler[Any]]
        ] = []
        self._compilers: dict[Any, frfr.types.CompileFunc] = {}
        self._predicate_compilers: list[
            tuple[Callable[[object], bool], frfr.types.CompileFunc]
        ] = []
        self._compiled: dict[int, frfr.types.CompiledValidator[Any]] = {}
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
        self._compilers[Any] = frfr.scalars.compile_any
        self._compilers[bool] = frfr.scalars.compile_bool
        self._compilers[int] = frfr.scalars.compile_int
        self._compilers[float] = frfr.scalars.compile_float
        self._compilers[str] = frfr.scalars.compile_str
        self._compilers[type(None)] = frfr.scalars.compile_none
        self._compilers[bytes] = frfr.scalars.compile_bytes
        self._compilers[decimal.Decimal] = frfr.scalars.compile_decimal
        self._compilers[dt.datetime] = frfr.scalars.compile_datetime
        self._compilers[dt.date] = frfr.scalars.compile_date
        self._compilers[dt.time] = frfr.scalars.compile_time
        self._compilers[dt.timedelta] = frfr.scalars.compile_timedelta
        self._compilers[uuid.UUID] = frfr.scalars.compile_uuid
        self._compilers[pathlib.Path] = frfr.scalars.compile_path
        self._compilers[list] = frfr.containers.compile_list
        self._compilers[tuple] = frfr.containers.compile_tuple
        self._compilers[dict] = frfr.containers.compile_dict
        self._compilers[set] = frfr.containers.compile_set
        self._compilers[frozenset] = frfr.containers.compile_frozenset
        self._compilers[collections.abc.Sequence] = frfr.containers.compile_sequence
        self._compilers[collections.abc.Mapping] = frfr.containers.compile_abc_mapping
        self._compilers[Annotated] = frfr.containers.compile_annotated
        self._compilers[Union] = frfr.containers.compile_union
        self._compilers[types.UnionType] = frfr.containers.compile_union
        self._compilers[Literal] = frfr.containers.compile_literal
        self._compilers[Final] = frfr.containers.compile_final
        self._predicate_compilers = [
            (frfr.utils.is_newtype, frfr.containers.compile_newtype),
            (frfr.utils.is_enum_type, frfr.scalars.compile_enum),
            (is_typeddict, frfr.structured.compile_typed_dict),
            (frfr.utils.is_namedtuple, frfr.structured.compile_namedtuple),
            (frfr.utils.is_dataclass_type, frfr.structured.compile_dataclass),
        ]

    def register_type_handler[T](
        self, target: type[T], handler: frfr.types.Handler[T]
    ) -> None:
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
        handler: frfr.types.Handler[T],
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

    def _get_compiled(self, target: object) -> frfr.types.CompiledValidator[Any]:
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

    def _build_compiled(self, target: object) -> frfr.types.CompiledValidator[Any]:
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
            raise frfr.types.ValidationError(target, data, path=path)

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
