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
my_validator.register_type_handler(int, my_custom_int_handler)
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

### Union types - order matters
- Union types are tried in declaration order; the first matching type wins
- Coercion rules still apply within each type attempt
- Example: `Union[float, int]` with `1` → `1.0` (int coerces to float, float wins)
- Example: `Union[int, float]` with `1` → `1` (int matches first, no coercion needed)
- Both `Union[A, B]` and `A | B` syntax are supported

### Set types - no list/tuple coercion
- `set` and `frozenset` only accept set/frozenset as input
- No coercion from list/tuple - could silently lose data (duplicates)
- Ordering doesn't transfer meaningfully between lists and sets
- `set` ↔ `frozenset` coercion is allowed (lossless, both are set-like)

### Always return new objects for mutable containers
- Mutable containers (list, dict, set) always return a NEW object, never the original
- This ensures safety: mutations to validated data don't affect the original input
- Immutable types (int, float, str, bool, None, tuple) can return the original since they can't be mutated
- Performance tradeoff is acceptable for typical JSON payloads; safety > speed

### Supported types
**Implemented:**
- Primitives: `str`, `int`, `float`, `bool`, `None`, `Any`
- Containers: `list[T]`, `dict[K, V]`, `tuple[T, ...]`, `tuple[T1, T2, ...]`, `set[T]`, `frozenset[T]`
- Typing constructs: `Union[T1, T2]`, `T | None`, `TypedDict`, `Literal["a", "b"]`
- Classes: `@dataclass` (construct from dict/Mapping; dataclass instances coerce to dict)
- Generic types: `list[str]`, `dict[str, int]`, etc.
- Mapping coercion: `OrderedDict`, `MappingProxyType`, etc. → `dict`

**Planned:**
- `NamedTuple`

## Project structure

```
src/frfr/
├── __init__.py        # public API exports
├── validation.py      # Validator class, handlers, validate()
├── validation_test.py # tests
└── py.typed           # PEP 561 marker
```

## Next steps

### Types to implement
- [x] `@dataclass` - major use case, construct from dict
- [x] `NamedTuple` - similar to dataclass

### API cleanup
- [x] Simplify public API: only export `frfr.validate`, `frfr.ValidationError`, `frfr.Validator`
- [x] Move parse functions to internal: `from frfr.validation import parse_int` (not `frfr.parse_int`)
- [x] Rename `validator.py` → `validation.py`

### Architecture fix
- [x] Any, Union, TypedDict are hardcoded in `validate()` method - can't be overridden
- [x] Should be registered handlers like everything else, not special-cased
- [x] Users creating custom Validators should be able to customize these behaviors

### Testing
- [ ] Add large-scale integration tests with deeply nested types
- [ ] Complex type combinations (e.g., `dict[str, list[tuple[int, Optional[str]]]]`)
- [ ] Edge cases and error message quality tests

### Error messages
- [ ] Improve error messages with full paths (e.g., `data.users[0].age`)
- [ ] Currently `ValidationError` has `path` param but handlers don't propagate it
- [ ] Need to pass path context through recursive validation calls

### Type hints
- [ ] `validate()` uses `type[T]` which pyright rejects for Union/Literal/Any type forms
- Validation works correctly at runtime — this is a type-hint-only limitation
- The right fix is `TypeForm[T]` from PEP 747 (`typing_extensions >= 4.15` has it), but
  pyright 1.1.x doesn't yet infer T correctly for `UnionType` through `TypeForm`
- For now, call sites using Union/Literal/Any use `# type: ignore[arg-type]`
- Revisit when pyright adds full `TypeForm` support

### Documentation & release
- [ ] Polish README with more examples
- [ ] Add CHANGELOG.md
- [ ] Set up branch protections on main
- [ ] Configure PyPI publishing (GitHub Actions workflow)
- [ ] First release to PyPI
