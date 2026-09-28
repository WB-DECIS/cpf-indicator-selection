"""scripts/validate.py: schema checks plus the cross-file rules."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import validate

ROOT = Path(__file__).resolve().parent.parent
VALID = Path(__file__).resolve().parent / "fixtures" / "valid"


@pytest.fixture
def root(tmp_path):
    """A writable copy of the valid fixture repository."""
    shutil.copytree(VALID, tmp_path, dirs_exist_ok=True)
    return tmp_path


def read(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def infrastructure(root):
    return read(root / "themes" / "infrastructure.yaml")


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Climate change", "climate change"),
        ("climate_change", "climate change"),
        ("  ICT   and_Digital ", "ict and digital"),
    ],
)
def test_norm_sector(name, expected):
    assert validate.norm_sector(name) == expected


def test_valid_fixture_has_no_errors():
    assert validate.validate_root(VALID) == []


def test_missing_index(root):
    (root / "themes.yaml").unlink()
    assert validate.validate_root(root) == ["themes.yaml: file not found"]


def test_invalid_yaml(root):
    (root / "themes" / "infrastructure.yaml").write_text("sectors: [\n", encoding="utf-8")
    errors = validate.validate_root(root)
    assert len(errors) == 1
    assert errors[0].startswith("themes/infrastructure.yaml: not valid YAML:")


def test_index_schema_error(root):
    write(root / "themes.yaml", {"themes": [{"id": "Infra", "name": "Infrastructure",
                                             "file": "themes/infrastructure.yaml"}]})
    assert validate.validate_root(root) == [
        "themes.yaml: $.themes[0].id: 'Infra' does not match '^[a-z][a-z0-9_]*$'"
    ]


def test_theme_schema_error_names_the_field(root):
    doc = infrastructure(root)
    doc["sectors"][1]["indicators"][0]["direction"] = "up"
    write(root / "themes" / "infrastructure.yaml", doc)
    assert validate.validate_root(root) == [
        "themes/infrastructure.yaml: $.sectors[1].indicators[0].direction: "
        "'up' is not one of ['higher_is_better', 'lower_is_better']"
    ]


def test_duplicate_theme_id(root):
    index = read(root / "themes.yaml")
    index["themes"].append(dict(index["themes"][0], name="Infrastructure again"))
    write(root / "themes.yaml", index)
    assert validate.validate_root(root) == [
        "themes.yaml: theme id 'infrastructure' is listed more than once"
    ]


def test_listed_file_must_exist(root):
    index = read(root / "themes.yaml")
    index["themes"].append({"id": "people", "name": "People", "file": "themes/people.yaml"})
    write(root / "themes.yaml", index)
    assert validate.validate_root(root) == [
        "themes.yaml: theme 'people' lists themes/people.yaml, which does not exist"
    ]


def test_duplicate_short_name_in_a_listed_file(root):
    doc = infrastructure(root)
    doc["sectors"][2]["indicators"][0]["short_name"] = "access_to_electricity"
    write(root / "themes" / "infrastructure.yaml", doc)
    assert validate.validate_root(root) == [
        "themes/infrastructure.yaml: short_name 'access_to_electricity' appears more than once"
    ]


@pytest.mark.parametrize("clash", ["water", "WATER", " Water ", "_water_"])
def test_duplicate_sector_name_after_normalisation(root, clash):
    doc = infrastructure(root)
    doc["sectors"][2]["name"] = clash
    write(root / "themes" / "infrastructure.yaml", doc)
    assert validate.validate_root(root) == [
        f"themes/infrastructure.yaml: sector '{clash}' has the same name as 'Water' "
        "once case, spaces and underscores are ignored"
    ]


def test_same_short_name_in_two_themes_is_allowed(root):
    index = read(root / "themes.yaml")
    index["themes"].append({"id": "planet", "name": "Planet", "file": "themes/planet.yaml"})
    write(root / "themes.yaml", index)
    write(root / "themes" / "planet.yaml", infrastructure(root))
    assert validate.validate_root(root) == []


def test_unlisted_draft_is_schema_checked(root):
    draft = infrastructure(root)
    del draft["sectors"][0]["indicators"][0]["label"]
    write(root / "themes" / "people.yaml", draft)
    assert validate.validate_root(root) == [
        "themes/people.yaml: $.sectors[0].indicators[0]: 'label' is a required property"
    ]


def test_unlisted_draft_skips_the_cross_file_rules(root):
    draft = infrastructure(root)
    draft["sectors"][2]["name"] = "water"
    draft["sectors"][2]["indicators"][0]["short_name"] = "access_to_electricity"
    write(root / "themes" / "people.yaml", draft)
    assert validate.validate_root(root) == []


def test_cli_exit_codes(root):
    script = ROOT / "scripts" / "validate.py"
    ok = subprocess.run([sys.executable, str(script), str(root)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout.strip() == "OK: themes.yaml, 1 listed theme file(s), 0 unlisted draft(s)"

    (root / "themes" / "infrastructure.yaml").unlink()
    bad = subprocess.run([sys.executable, str(script), str(root)], capture_output=True, text=True)
    assert bad.returncode == 1
    assert bad.stderr.splitlines() == [
        "ERROR themes.yaml: theme 'infrastructure' lists themes/infrastructure.yaml, "
        "which does not exist",
        "1 error(s) found.",
    ]
