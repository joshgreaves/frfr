"""Core validation logic for frfr."""

from typing import Any, Callable, Protocol, cast, get_args, get_origin


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


class ValidatorProtocol(Protocol):
    """Protocol for validators. Used in handler type signatures."""

    def validate[T](self, target: type[T], data: object) -> T:
        """Validate and coerce data to the given type."""
        ...


# Type alias for handler functions.
# Handlers receive a ValidatorProtocol to enable recursive validation.
type Handler[T] = Callable[[ValidatorProtocol, type[T], object], T]


class Validator:
    """Type validator with extensible handlers.

    Handlers receive the validator instance to enable recursive validation
    of nested types (e.g., list[int] needs to validate each element).

    All validators start with built-in handlers for standard types.
    Use `frozen=True` to prevent further registration (used internally
    for the default validator).
    """

    def __init__(self, *, frozen: bool = False) -> None:
        self._handlers: dict[type, Handler[Any]] = {}
        self._frozen = frozen
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in handlers. Called during __init__."""
        self._handlers[int] = parse_int
        self._handlers[float] = parse_float
        self._handlers[str] = parse_str
        self._handlers[bool] = parse_bool
        self._handlers[type(None)] = parse_none
        self._handlers[list] = parse_list
        self._handlers[tuple] = parse_tuple

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
        # Handle Any explicitly (special form, not a regular type)
        if target is Any:
            return cast(T, data)

        # Try exact match first
        handler = self._handlers.get(target)
        if handler is not None:
            return cast(T, handler(self, target, data))

        # For generic types like list[int], try the origin type (list)
        origin = get_origin(target)
        if origin is not None:
            handler = self._handlers.get(origin)
            if handler is not None:
                return cast(T, handler(self, target, data))

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


def parse_any(validator: ValidatorProtocol, target: type[Any], data: object) -> Any:
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
