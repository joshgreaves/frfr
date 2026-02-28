"""frfr - runtime type validation that's actually valid. no cap."""

from frfr.validator import ValidationError
from frfr.validator import validate

__all__ = ["validate", "ValidationError"]
