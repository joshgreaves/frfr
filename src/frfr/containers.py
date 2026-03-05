"""Compile functions for parameterized and container types."""

from typing import Any, Callable, get_args

import frfr.types
import frfr.utils


def compile_list(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for list."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (list, tuple)):
                raise frfr.types.ValidationError(target, data, path=path)
            return list(data)

        return _untyped

    elem = get_compiled(args[0])

    def _typed(data: object, path: str) -> Any:
        if not isinstance(data, (list, tuple)):
            raise frfr.types.ValidationError(target, data, path=path)
        return [elem(item, f"{path}[{i}]") for i, item in enumerate(data)]

    return _typed


def compile_tuple(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for tuple."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (list, tuple)):
                raise frfr.types.ValidationError(target, data, path=path)
            return tuple(data)

        return _untyped

    if len(args) == 2 and args[1] is Ellipsis:
        elem = get_compiled(args[0])

        def _homo(data: object, path: str) -> Any:
            if not isinstance(data, (list, tuple)):
                raise frfr.types.ValidationError(target, data, path=path)
            return tuple(elem(item, f"{path}[{i}]") for i, item in enumerate(data))

        return _homo

    field_fns = tuple(get_compiled(t) for t in args)
    n = len(args)

    def _fixed(data: object, path: str) -> Any:
        if not isinstance(data, (list, tuple)):
            raise frfr.types.ValidationError(target, data, path=path)
        if len(data) != n:
            raise frfr.types.ValidationError(target, data, path=path)
        return tuple(
            fn(item, f"{path}[{i}]")
            for i, (fn, item) in enumerate(zip(field_fns, data))
        )

    return _fixed


def compile_dict(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for dict."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            mapping = frfr.utils.coerce_to_mapping(data)
            if mapping is None:
                raise frfr.types.ValidationError(target, data, path=path)
            return dict(mapping)

        return _untyped

    key_type, val_type = args
    key_fn = get_compiled(key_type)
    val_fn = get_compiled(val_type)

    def _typed(data: object, path: str) -> Any:
        mapping = frfr.utils.coerce_to_mapping(data)
        if mapping is None:
            raise frfr.types.ValidationError(target, data, path=path)
        result: dict[Any, Any] = {}
        for k, v in mapping.items():
            key_segment = frfr.utils.format_key_path_segment(k)
            key_path = f"{path}{key_segment}" if path else key_segment
            result[key_fn(k, f"{key_path}[key]")] = val_fn(v, key_path)
        return result

    return _typed


def compile_set(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for set."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (set, frozenset)):
                raise frfr.types.ValidationError(target, data, path=path)
            return set(data)

        return _untyped

    elem = get_compiled(args[0])

    def _typed(data: object, path: str) -> Any:
        if not isinstance(data, (set, frozenset)):
            raise frfr.types.ValidationError(target, data, path=path)
        return {elem(item, path) for item in data}

    return _typed


def compile_frozenset(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for frozenset."""
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if not isinstance(data, (set, frozenset)):
                raise frfr.types.ValidationError(target, data, path=path)
            return frozenset(data)

        return _untyped

    elem = get_compiled(args[0])

    def _typed(data: object, path: str) -> Any:
        if not isinstance(data, (set, frozenset)):
            raise frfr.types.ValidationError(target, data, path=path)
        return frozenset(elem(item, path) for item in data)

    return _typed


def compile_sequence(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Sequence[T].

    Accepts list or tuple. Explicitly rejects str and bytes even though they
    are technically sequences — a Sequence[str] means a list of strings, not
    a bare string. Returns a list.
    """
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            if isinstance(data, (str, bytes)) or not isinstance(data, (list, tuple)):
                raise frfr.types.ValidationError(target, data, path=path)
            return list(data)

        return _untyped

    elem = get_compiled(args[0])

    def _typed(data: object, path: str) -> Any:
        if isinstance(data, (str, bytes)) or not isinstance(data, (list, tuple)):
            raise frfr.types.ValidationError(target, data, path=path)
        return [elem(item, f"{path}[{i}]") for i, item in enumerate(data)]

    return _typed


def compile_abc_mapping(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Mapping[K, V].

    Accepts any Mapping input, validates keys and values, returns a dict.
    """
    args = get_args(target)
    if not args:

        def _untyped(data: object, path: str) -> Any:
            mapping = frfr.utils.coerce_to_mapping(data)
            if mapping is None:
                raise frfr.types.ValidationError(target, data, path=path)
            return dict(mapping)

        return _untyped

    key_type, val_type = args
    key_fn = get_compiled(key_type)
    val_fn = get_compiled(val_type)

    def _typed(data: object, path: str) -> Any:
        mapping = frfr.utils.coerce_to_mapping(data)
        if mapping is None:
            raise frfr.types.ValidationError(target, data, path=path)
        result: dict[Any, Any] = {}
        for k, v in mapping.items():
            key_segment = frfr.utils.format_key_path_segment(k)
            key_path = f"{path}{key_segment}" if path else key_segment
            result[key_fn(k, f"{key_path}[key]")] = val_fn(v, key_path)
        return result

    return _typed


def compile_union(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Union types."""
    args = get_args(target)
    if not args:

        def _empty(data: object, path: str) -> Any:
            raise frfr.types.ValidationError(target, data, path=path)

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
            except frfr.types.ValidationError:
                pass
            try:
                return fn1(data, path)
            except frfr.types.ValidationError:
                pass
            raise frfr.types.ValidationError(target, data, path=path)

        return _union2

    # N-type union: pre-compiled members tuple, single loop.
    member_fns = tuple(get_compiled(t) for t in args)

    def _unionN(data: object, path: str) -> Any:
        for fn in member_fns:
            try:
                return fn(data, path)
            except frfr.types.ValidationError:
                continue
        raise frfr.types.ValidationError(target, data, path=path)

    return _unionN


def compile_literal(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Literal types."""
    from typing import get_args

    allowed = get_args(target)

    def _literal(data: object, path: str) -> Any:
        for val in allowed:
            if type(data) is type(val) and data == val:
                return data
        raise frfr.types.ValidationError(target, data, path=path)

    return _literal


def compile_annotated(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Annotated — ignores metadata, validates the inner type."""
    from typing import get_args

    return get_compiled(get_args(target)[0])


def compile_newtype(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for NewType — unwraps to the base type."""
    return get_compiled(target.__supertype__)  # type: ignore[union-attr]


def compile_final(
    target: object,
    get_compiled: Callable[[object], frfr.types.CompiledValidator[Any]],
) -> frfr.types.CompiledValidator[Any]:
    """Compile a validator for Final[T] — treats as T."""
    args = get_args(target)
    if not args:
        return lambda data, path: data
    return get_compiled(args[0])
