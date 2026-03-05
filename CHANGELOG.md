# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - 2026-03-05

### Added
- Initial public release of `frfr`.
- Runtime validation for standard Python typing and data shapes:
  - Scalars: `Any`, `str`, `int`, `float`, `bool`, `None`, `bytes`
  - Stdlib value types: `decimal.Decimal`, `datetime.datetime`, `datetime.date`,
    `datetime.time`, `datetime.timedelta`, `uuid.UUID`, `pathlib.Path`
  - Containers: `list`, `dict`, `tuple` (fixed and variadic), `set`, `frozenset`
  - Abstract collections: `collections.abc.Sequence`, `collections.abc.Mapping`
  - Typing forms: `Union` / `|`, `Literal`, `Annotated` (transparent), `NewType`, `Final`
  - Structured types: `TypedDict`, `dataclass`, `NamedTuple`

### Notes
- Strict-by-default semantics (no broad implicit coercion).
- Path-aware validation errors.
- Extensible `Validator` API for custom type handlers.
- Wheel packaging excludes `*_test.py` modules.
