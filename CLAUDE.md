# frfr

Runtime type validation library for Python. validates your data fr fr (for real for real).

## What it does

```python
import frfr

value = frfr.validate(TargetType, data)
```

Pass a target type and data. You get back validated/coerced output or a `ValidationError`.

## Code style

- Follow [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- Import modules, not classes/functions (except `typing` imports)
- Use `ruff` for formatting and linting
- Use both `ty` and `pyright` for type checking
- Tests live alongside source: `src/frfr/module.py` -> `src/frfr/module_test.py`
- Use `pytest` and explicit helper functions; avoid fixtures unless clearly needed

## Commands

```bash
uv run ruff format .      # format code
uv run ruff check --fix . # lint and fix
uv run ty check           # type check (ty)
uv run pyright            # type check (pyright)
uv run pytest             # run tests
make ci                   # run full CI locally
```

## Architecture

### Compile-first validator design

frfr compiles validation closures per target type and caches them. After first compile, repeated calls avoid per-call type introspection.

Core flow:
1. `Validator.validate(target, data)` delegates to `_validate_at(target, data, path="")`
2. `_get_compiled(target)` fetches or builds a compiled validator function
3. Compiled function validates/coerces with path-aware errors

### Registration model

`Validator` supports user extension with handler registration:
- `register_type_handler(target, handler)` for exact-type overrides
- `register_predicate_handler(predicate, handler)` for predicate-based overrides

Registering handlers clears compiled cache so new behavior applies to already-seen types.

### Built-in compiler coverage

Built-ins include:
- Scalars: `Any`, `bool`, `int`, `float`, `str`, `None`, `bytes`
- Stdlib value types: `Decimal`, `datetime/date/time/timedelta`, `UUID`, `Path`
- Containers: `list`, `tuple`, `dict`, `set`, `frozenset`
- Abstract collections: `Sequence`, `Mapping`
- Typing forms: `Annotated` (transparent), `Union` / `|`, `Literal`, `Final`
- Predicate-based: `Enum` types, `NewType`, `TypedDict`, `NamedTuple`, dataclasses

### Public API

`frfr` exports only:
- `frfr.validate`
- `frfr.Validator`
- `frfr.ValidationError`

## Design decisions

### Strict by default

- No `"1"` -> `int`
- No `1.0` -> `int`
- No `True` -> `int`
- Yes `1` -> `float` (lossless widening)

### Structure enforcement

- TypedDict/dataclass/NamedTuple reject unknown keys/fields
- Required keys/fields must be present
- Validation errors include full path context (e.g. `.users[0].age`)

### Container behavior

- `list`/`tuple` inputs are accepted for sequence-like targets where appropriate
- `set`/`frozenset` do not accept list/tuple input (avoid duplicate-loss surprises)
- Mutable outputs (`list`, `dict`, `set`) are returned as new objects

## Type-checker note

`validate()` currently uses `type[T]` in signatures. Runtime behavior is correct, but static checkers still require suppressions for some type forms (`Union`, `Literal`, `Any`, `NewType`, `Final`, `Annotated` in some contexts). Revisit when checker support for richer type-form typing is better.

## Project structure

```text
src/frfr/
├── __init__.py
├── validation.py
├── types.py
├── scalars.py
├── containers.py
├── structured.py
├── *_test.py
└── py.typed
```

## Near-term priorities

- Polish README examples and comparison guidance
- Add `CHANGELOG.md`
- Configure publish workflow to PyPI
- Keep CI/tooling strict (`ruff`, `ty`, `pyright`, `pytest`)
