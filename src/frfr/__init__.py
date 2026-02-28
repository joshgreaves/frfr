"""frfr - runtime type validation that's actually valid. no cap."""

from frfr.validator import ValidationError
from frfr.validator import Validator
from frfr.validator import ValidatorProtocol
from frfr.validator import parse_bool
from frfr.validator import parse_float
from frfr.validator import parse_int
from frfr.validator import parse_list
from frfr.validator import parse_none
from frfr.validator import parse_str
from frfr.validator import validate

__all__ = [
    "ValidationError",
    "Validator",
    "ValidatorProtocol",
    "parse_bool",
    "parse_float",
    "parse_int",
    "parse_list",
    "parse_none",
    "parse_str",
    "validate",
]
