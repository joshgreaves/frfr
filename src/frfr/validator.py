"""Core validation logic for frfr."""

import typing


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, expected: type, actual: object, path: str = "") -> None:
        self.expected = expected
        self.actual = actual
        self.path = path
        actual_type = type(actual).__name__
        actual_repr = repr(actual)
        location = f"{path} - " if path else ""
        message = f"{location}expected {expected.__name__}, got {actual_type} ({actual_repr})"
        super().__init__(message)


def validate[T](target: type[T], data: object) -> T:
    """Validate and coerce data to the given type.

    Args:
        target: The type to validate against.
        data: The data to validate.

    Returns:
        The validated data, coerced to the target type if needed.

    Raises:
        ValidationError: If the data does not match the expected type.
    """
    return _validate_impl(target, data, path="")


def _validate_impl[T](target: type[T], data: object, path: str) -> T:
    """Internal validation implementation with path tracking."""
    # Handle int (with explicit bool rejection)
    if target is int:
        return typing.cast(T, _validate_int(data, path))

    raise ValidationError(target, data, path)


def _validate_int(data: object, path: str) -> int:
    """Validate that data is an int (not a bool)."""
    # Reject bool explicitly - even though bool is a subclass of int
    if type(data) is bool:
        raise ValidationError(int, data, path)

    if type(data) is not int:
        raise ValidationError(int, data, path)

    return data
