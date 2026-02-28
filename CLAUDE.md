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

## Design decisions

### Strict type validation
- `"1"` does NOT coerce to `int` - let your serialization lib handle that
- `1.0` does NOT coerce to `int` - int means int, no cap
- `True`/`False` do NOT coerce to `int` - even though bool is technically int subclass
- `1` DOES coerce to `float` - lossless widening is valid

### Type equivalences
- `tuple[T, ...]` and `list[T]` are equivalent (both accept JSON arrays)
- Coercion always produces the target type (list becomes tuple if that's what you asked for)

### Supported types (planned)
- Primitives: `str`, `int`, `float`, `bool`, `None`
- Containers: `list`, `dict`, `tuple`, `set`
- Typing constructs: `Optional`, `Union`, `Literal`, `TypedDict`
- Classes: `dataclass`, regular classes with `__init__`
- Generic types: `list[str]`, `dict[str, int]`, etc.

## Project structure

```
src/frfr/
├── __init__.py      # public API (validate function)
├── _validators.py   # validation logic
└── *_test.py        # tests alongside source
```
