"""Shared type definitions for frfr handlers and compilers.

No frfr imports — pure stdlib only. This keeps the import graph acyclic:
scalars/containers/structured can import frfr.types without triggering
a circular import through frfr.validation.
"""

from typing import Any, Callable, Protocol


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(
        self,
        expected: Any,
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


class Handler[T](Protocol):
    """A module-level handler function that performs validation directly.

    Handlers receive a ValidatorProtocol to enable recursive validation.
    The path parameter tracks location in ntested structures for error messages.
    """

    def __call__(
        self, validator: ValidatorProtocol, target: type[T], data: object, path: str
    ) -> T: ...
