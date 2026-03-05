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
- Use `pytest` but NO fixtures; use explicit helper functions for setup

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

### Type equivalences

- `tuple[T, ...]` and `list[T]` are equivalent (both accept JSON arrays)
- Coercion always produces the target type (list becomes tuple if that's what you asked for)
- Mapping coercion: `OrderedDict`, `MappingProxyType`, etc. → `dict`

### Union types - order matters

- Union types are tried in declaration order; the first matching type wins
- Example: `Union[float, int]` with `1` → `1.0` (int coerces to float, float wins)
- Example: `Union[int, float]` with `1` → `1` (int matches first, no coercion needed)

### Container behavior

- `list`/`tuple` inputs are accepted for sequence-like targets where appropriate
- `set`/`frozenset` do not accept list/tuple input (avoid duplicate-loss surprises)
- Mutable outputs (`list`, `dict`, `set`) are always NEW objects, never the original
- This ensures safety: mutations to validated data don't affect the original input

## Type-checker note

`validate()` currently uses `type[T]` in signatures. Runtime behavior is correct, but static checkers still require suppressions for some type forms (`Union`, `Literal`, `Any`, `NewType`, `Final`, `Annotated` in some contexts).

The right fix is `TypeForm[T]` from PEP 747 (`typing_extensions >= 4.15` has it), but pyright doesn't yet infer T correctly for `UnionType` through `TypeForm`. For now, call sites using these type forms use `# type: ignore[arg-type]`. Revisit when pyright adds full `TypeForm` support.

## Project structure

```text
src/frfr/
├── __init__.py
├── validation.py
├── types.py
├── utils.py
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
