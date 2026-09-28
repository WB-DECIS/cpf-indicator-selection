"""The repository's own index and theme files pass the validator."""
from pathlib import Path

import validate

ROOT = Path(__file__).resolve().parent.parent


def test_repository_is_valid():
    assert validate.validate_root(ROOT) == []
