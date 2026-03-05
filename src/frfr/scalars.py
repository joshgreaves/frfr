"""Compile functions for scalar/primitive types."""

import datetime as dt
import decimal
import pathlib
import uuid
from typing import Any, Callable

import frfr
import frfr.types


def compile_any(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Any (accepts everything)."""
    return lambda data, path: data


def compile_bool(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for bool."""

    def _bool(data: object, path: str) -> Any:
        if type(data) is not bool:
            raise frfr.ValidationError(target, data, path=path)
        return data

    return _bool


def compile_int(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for int."""

    def _int(data: object, path: str) -> Any:
        if type(data) is bool:
            raise frfr.ValidationError(target, data, path=path)
        if type(data) is not int:
            raise frfr.ValidationError(target, data, path=path)
        return data

    return _int


def compile_float(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for float."""

    def _float(data: object, path: str) -> Any:
        if type(data) is bool:
            raise frfr.ValidationError(target, data, path=path)
        if type(data) is float:
            return data
        if type(data) is int:
            return float(data)
        raise frfr.ValidationError(target, data, path=path)

    return _float


def compile_str(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for str."""

    def _str(data: object, path: str) -> Any:
        if type(data) is not str:
            raise frfr.ValidationError(target, data, path=path)
        return data

    return _str


def compile_none(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for None."""

    def _none(data: object, path: str) -> Any:
        if data is not None:
            raise frfr.ValidationError(target, data, path=path)
        return None

    return _none


def compile_bytes(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for bytes."""

    def _bytes(data: object, path: str) -> Any:
        if type(data) is not bytes:
            raise frfr.ValidationError(target, data, path=path)
        return data

    return _bytes


def compile_decimal(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for decimal.Decimal.

    Accepts Decimal instances, int (lossless widening), and strings (exact
    decimal representation). Rejects float — Decimal(0.1) captures binary
    imprecision, not the intended value.
    """

    def _decimal(data: object, path: str) -> Any:
        if type(data) is bool:
            raise frfr.ValidationError(target, data, path=path)
        if isinstance(data, decimal.Decimal):
            return data
        if type(data) is int:
            return decimal.Decimal(data)
        if type(data) is str:
            try:
                return decimal.Decimal(data)
            except decimal.InvalidOperation:
                raise frfr.ValidationError(target, data, path=path)
        raise frfr.ValidationError(target, data, path=path)

    return _decimal


def compile_enum(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Enum types.

    Accepts enum instances (passthrough) or raw member values (coerced to the
    enum instance). Raises ValidationError for values that are not valid members.
    """
    enum_cls = target

    def _enum(data: object, path: str) -> Any:
        if isinstance(data, enum_cls):  # type: ignore[arg-type]
            return data
        try:
            return enum_cls(data)  # type: ignore[operator]
        except (ValueError, KeyError):
            raise frfr.ValidationError(target, data, path=path)

    return _enum


def compile_datetime(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for datetime.datetime.

    Accepts datetime instances or ISO 8601 strings. Rejects bare date instances
    (date is a supertype of datetime, not the other way around).
    """

    def _datetime(data: object, path: str) -> Any:
        if isinstance(data, dt.datetime):
            return data
        if type(data) is str:
            try:
                return dt.datetime.fromisoformat(data)
            except ValueError:
                raise frfr.ValidationError(target, data, path=path)
        raise frfr.ValidationError(target, data, path=path)

    return _datetime


def compile_date(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for datetime.date.

    Accepts date instances or ISO 8601 date strings. datetime instances are
    accepted and narrowed to date (datetime IS a date, and it's not surprising).
    """

    def _date(data: object, path: str) -> Any:
        # datetime must be checked before date: datetime is a subclass of date,
        # so isinstance(data, dt.date) is True for datetime instances too.
        if isinstance(data, dt.datetime):
            return data.date()
        if isinstance(data, dt.date):
            return data
        if type(data) is str:
            try:
                return dt.date.fromisoformat(data)
            except ValueError:
                raise frfr.ValidationError(target, data, path=path)
        raise frfr.ValidationError(target, data, path=path)

    return _date


def compile_time(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for datetime.time.

    Accepts time instances or ISO 8601 time strings.
    """

    def _time(data: object, path: str) -> Any:
        if isinstance(data, dt.time):
            return data
        if type(data) is str:
            try:
                return dt.time.fromisoformat(data)
            except ValueError:
                raise frfr.ValidationError(target, data, path=path)
        raise frfr.ValidationError(target, data, path=path)

    return _time


def compile_timedelta(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for datetime.timedelta.

    Accepts only timedelta instances. There is no standard string representation
    for timedelta, so no string coercion is performed.
    """

    def _timedelta(data: object, path: str) -> Any:
        if not isinstance(data, dt.timedelta):
            raise frfr.ValidationError(target, data, path=path)
        return data

    return _timedelta


def compile_uuid(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for uuid.UUID.

    Accepts UUID instances or standard UUID strings.
    """

    def _uuid(data: object, path: str) -> Any:
        if isinstance(data, uuid.UUID):
            return data
        if type(data) is str:
            try:
                return uuid.UUID(data)
            except ValueError:
                raise frfr.ValidationError(target, data, path=path)
        raise frfr.ValidationError(target, data, path=path)

    return _uuid


def compile_path(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for pathlib.Path.

    Accepts Path instances or strings. str -> Path is idiomatic and lossless.
    """

    def _path(data: object, path: str) -> Any:
        if isinstance(data, pathlib.Path):
            return data
        if type(data) is str:
            return pathlib.Path(data)
        raise frfr.ValidationError(target, data, path=path)

    return _path
