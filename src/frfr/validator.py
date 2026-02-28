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
        message = (
            f"{location}expected {expected.__name__}, got {actual_type} ({actual_repr})"
        )
        super().__init__(message)


class ValidatorProtocol(typing.Protocol):
    """Protocol for validators. Used in handler type signatures."""

    def validate[T](self, target: type[T], data: object) -> T:
        """Validate and coerce data to the given type."""
        ...


# Type alias for handler functions.
# Handlers receive a ValidatorProtocol to enable recursive validation.
type Handler[T] = typing.Callable[[ValidatorProtocol, type[T], object], T]


class Validator:
    """Type validator with extensible handlers.

    Handlers receive the validator instance to enable recursive validation
    of nested types (e.g., list[int] needs to validate each element).

    All validators start with built-in handlers for standard types.
    Use `frozen=True` to prevent further registration (used internally
    for the default validator).
    """

    def __init__(self, *, frozen: bool = False) -> None:
        self._handlers: dict[type, Handler[typing.Any]] = {}
        self._frozen = frozen
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in handlers. Called during __init__."""
        self._handlers[int] = parse_int
        self._handlers[float] = parse_float
        self._handlers[str] = parse_str
        self._handlers[bool] = parse_bool
        self._handlers[type(None)] = parse_none

    def register[T](self, target: type[T], handler: Handler[T]) -> None:
        """Register a handler for a target type.

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
        handler = self._handlers.get(target)
        if handler is not None:
            return typing.cast(T, handler(self, target, data))

        raise ValidationError(target, data)


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
