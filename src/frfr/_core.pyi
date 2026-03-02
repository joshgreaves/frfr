"""Type stubs for the Rust _core module."""

from typing import Any, TypeVar

T = TypeVar("T")

class ValidationError(Exception):
    """Raised when validation fails."""

    expected: type
    actual: object
    path: str

    def __init__(
        self, expected: type, actual: object, path: str = ""
    ) -> None: ...

class Validator:
    """Validator with compiled type caching."""

    def __init__(self, *, frozen: bool = False) -> None: ...
    def validate(self, target: type[T], data: object) -> T: ...

def validate(target: type[T], data: object) -> T:
    """Validate and coerce data to the given type."""
    ...
