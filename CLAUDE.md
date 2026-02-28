# frfr

Runtime type validation library for Python. validates your data fr fr (for real for real).

## What it does

```python
import frfr

my_object = frfr.validate(MyType, data)
```

That's it. Pass a type and some data, get back a validated and coerced instance of that type. If it's cap (invalid), it raises an exception.

## Code style

- Follow [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- Import modules, not classes or functions: `import os` not `from os import path`
- Exception: `typing` imports can use `from typing import Any, Protocol, ...`
- Use `ruff` for formatting
- Use `ty` and `pyright` for type checking
- Tests live alongside source: `src/frfr/mymodule.py` → `src/frfr/mymodule_test.py`
- Use `pytest` but NO fixtures. Use helper functions for setup (more explicit)

## Commands

```bash
uv run ruff format .           # format code
uv run ruff check --fix .      # lint and fix
uv run pyright                  # type check
uv run pytest                   # run tests
```

## Architecture

### Handler pattern

Each target type has a handler: `Callable[[ValidatorProtocol, type[T], object], T]`

```python
def parse_int(
    validator: ValidatorProtocol, target: type[int], data: object
) -> int:
    if type(data) is bool:
        raise ValidationError(target, data)
    if type(data) is int:
        return data
    raise ValidationError(target, data)
```

Handlers receive:
1. `validator` - enables recursive validation for nested types (e.g., `list[int]`)
2. `target` - the full target type (important for generics like `list[str]`)
3. `data` - the data to validate

### ValidatorProtocol

Protocol with just `validate()` method. Used in handler type signatures:

```python
class ValidatorProtocol(Protocol):
    def validate[T](self, target: type[T], data: object) -> T: ...
```

### Validator class

Concrete implementation with handler registration:

```python
class Validator:
    def __init__(self, *, frozen: bool = False) -> None:
        self._handlers: dict[type, Handler] = {}
        self._frozen = frozen
        self._register_builtins()  # all validators start with built-ins

    def register(self, target: type[T], handler: Handler[T]) -> None:
        if self._frozen:
            raise RuntimeError("Cannot register on a frozen validator")
        self._handlers[target] = handler

    def validate(self, target: type[T], data: object) -> T:
        handler = self._handlers.get(target)
        if handler:
            return handler(self, target, data)
        raise ValidationError(target, data)
```

### Module API

- `frfr.validate()` - uses a private frozen `Validator` instance
- `frfr.Validator` - class for custom instances (comes with built-in handlers)
- `frfr.ValidatorProtocol` - protocol for handler type signatures
- `frfr.ValidationError` - exception raised on validation failure
- `frfr.parse_int`, `frfr.parse_float`, etc. - exposed handlers for composition

Users cannot register on the default validator (it's frozen). They create their own:

```python
my_validator = frfr.Validator()
my_validator.register(int, my_custom_int_handler)
```

## Design decisions

### Strict type validation
- `"1"` does NOT coerce to `int` - let your serialization lib handle that
- `1.0` does NOT coerce to `int` - int means int, no cap
- `True`/`False` do NOT coerce to `int` - even though bool is technically int subclass
- `1` DOES coerce to `float` - lossless widening is valid

### Type equivalences
- `tuple[T, ...]` and `list[T]` are equivalent (both accept JSON arrays)
- Coercion always produces the target type (list becomes tuple if that's what you asked for)

### Always return new objects for mutable containers
- Mutable containers (list, dict, set) always return a NEW object, never the original
- This ensures safety: mutations to validated data don't affect the original input
- Immutable types (int, float, str, bool, None, tuple) can return the original since they can't be mutated
- Performance tradeoff is acceptable for typical JSON payloads; safety > speed

### Supported types (planned)
- Primitives: `str`, `int`, `float`, `bool`, `None`
- Containers: `list`, `dict`, `tuple`, `set`
- Typing constructs: `Optional`, `Union`, `Literal`, `TypedDict`
- Classes: `dataclass`, regular classes with `__init__`
- Generic types: `list[str]`, `dict[str, int]`, etc.

## Project structure

```
src/frfr/
├── __init__.py       # public API exports
├── validator.py      # Validator class, handlers, validate()
├── validator_test.py # tests
└── py.typed          # PEP 561 marker
```
