"""The JSON Schemas accept the valid fixtures and reject each invalid case."""
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _schema(name):
    return json.loads((ROOT / "schema" / name).read_text(encoding="utf-8"))


def _cases(name):
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _messages(schema_name, document):
    return [e.message for e in Draft202012Validator(_schema(schema_name)).iter_errors(document)]


THEME_CASES = _cases("invalid-theme-cases.yaml")
INDEX_CASES = _cases("invalid-index-cases.yaml")


def _objects(node):
    """Every sub-schema that describes an object."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from _objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from _objects(value)


@pytest.mark.parametrize("name", ["themes-index.schema.json", "theme.schema.json"])
def test_schema_is_draft_2020_12_and_closed(name):
    schema = _schema(name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    objects = list(_objects(schema))
    assert objects
    assert all(obj.get("additionalProperties") is False for obj in objects)


def test_valid_index_passes():
    doc = yaml.safe_load((FIXTURES / "valid" / "themes.yaml").read_text(encoding="utf-8"))
    Draft202012Validator(_schema("themes-index.schema.json")).validate(doc)


def test_valid_theme_passes():
    doc = yaml.safe_load(
        (FIXTURES / "valid" / "themes" / "infrastructure.yaml").read_text(encoding="utf-8")
    )
    Draft202012Validator(_schema("theme.schema.json")).validate(doc)


def test_sector_mean_false_is_allowed():
    doc = yaml.safe_load(
        (FIXTURES / "valid" / "themes" / "infrastructure.yaml").read_text(encoding="utf-8")
    )
    doc["sectors"][0]["indicators"][0]["sector_mean"] = False
    Draft202012Validator(_schema("theme.schema.json")).validate(doc)


def test_dimensions_and_most_recent_are_allowed():
    doc = yaml.safe_load(
        (FIXTURES / "valid" / "themes" / "infrastructure.yaml").read_text(encoding="utf-8")
    )
    indicator = doc["sectors"][0]["indicators"][0]
    indicator["dimensions"] = {"UNIT_MEASURE": "10P5PS", "COMP_BREAKDOWN_1": "_T"}
    indicator["most_recent"] = True
    Draft202012Validator(_schema("theme.schema.json")).validate(doc)


@pytest.mark.parametrize("case", sorted(THEME_CASES))
def test_invalid_theme_fails(case):
    messages = _messages("theme.schema.json", THEME_CASES[case]["document"])
    assert any(THEME_CASES[case]["error"] in m for m in messages), messages


@pytest.mark.parametrize("case", sorted(INDEX_CASES))
def test_invalid_index_fails(case):
    messages = _messages("themes-index.schema.json", INDEX_CASES[case]["document"])
    assert any(INDEX_CASES[case]["error"] in m for m in messages), messages
