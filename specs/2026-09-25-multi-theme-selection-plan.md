# Multi-theme cpf-indicator-selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single `indicator-selection.yaml` into one indicator list per theme plus an ordered index, with a JSON Schema, a validator and CI, so that adding a theme becomes a data change that CI checks before `cpf-data360-sync` ever reads it.

**Architecture:** `themes.yaml` lists the published themes (`{id, name, file}`, in tab order); each `themes/<id>.yaml` holds one theme's sectors and indicators in display order. Two JSON Schema files (draft 2020-12) describe the two file kinds, and `scripts/validate.py` applies them plus the four cross-file rules a schema cannot express. The sync job validates against the same schema files, read from `main`, and implements the same four rules. `themes/planet.yaml` is generated once from today's `planet:` block; `indicator-selection.yaml` stays untouched until the new sync job is live.

**Tech Stack:** Python 3.11+ (verified on 3.11; CI uses 3.12), PyYAML 6, jsonschema 4 (`Draft202012Validator`), pytest 8+, GitHub Actions.

**Spec:** [`specs/2026-09-25-multi-theme-design.md`](https://github.com/WB-DECIS/cpf-report/blob/claude/vigilant-mayer-k6q1po/specs/2026-09-25-multi-theme-design.md) in cpf-report: §1 ("Indicator lists"), "Seams and owners", Rollout steps 0 and 4, "Adding a theme afterwards". Read them before starting; this plan argues from them.

## Global Constraints

- **Seams implemented** (spec → "Seams and owners"). This repository is the producer of:

  > | selection → sync | `themes.yaml`, `themes/<id>.yaml` (7 fields + optional `sector_mean`) and their JSON Schema | `cpf-indicator-selection` (schema, CI) | `cpf-data360-sync` (validates against the same schema, plus the cross-file rules) | selection CI; sync parser tests |

  It is also where the manual half of "sync → api, on Connect" is written down for new themes (README → Adding a theme; spec → "Adding a theme afterwards").
- **Fixed contract** (shared with the sync and API plans; do not change a value here without changing it there):
  - `themes.yaml`: `themes:` → list of `{id, name, file}`. `id` matches `^[a-z][a-z0-9_]*$`. Order is the app's tab order.
  - `themes/<id>.yaml`: `sectors:` → list of `{name, indicators}`; each indicator has seven required non-empty strings — `short_name`, `dataset_id`, `indicator_id`, `full_name`, `group`, `direction`, `label` — plus an optional boolean `sector_mean` (default `true`). `direction` is `higher_is_better` or `lower_is_better`. `sectors` and `indicators` are non-empty.
  - Both schemas are JSON Schema draft 2020-12 with `additionalProperties: false` on every object.
  - Cross-file rules, in `scripts/validate.py` and in the sync: (1) theme `id`s unique in `themes.yaml`; (2) every listed `file` exists; (3) `short_name` unique within a file; (4) sector names unique within a file after `norm(s) = " ".join(s.replace("_", " ").split()).lower()` (mirrors cpf-report's `.norm_sector()`).
  - Files under `themes/` that `themes.yaml` does not list are **drafts**: schema-checked only. Listing a theme publishes it.
  - Planet migration: `agriculture → Agriculture`, `climate_change → Climate change`, `environment → Environment`, `water → Water`; `total_ghg_emissions` gets `sector_mean: false`; order preserved.
  - Raw base URL the sync reads from: `https://raw.githubusercontent.com/WB-DECIS/cpf-indicator-selection/main/`. Paths in this repository (`themes.yaml`, `schema/*.json`, `themes/*.yaml`) are therefore part of the contract.
- **Vocabulary:** **theme** everywhere; "pillar" and "vertical" are retired in new files.
- **Do not edit `indicator-selection.yaml`.** The current sync job reads it until rollout step 2; it is deleted in step 6.
- **Tests never touch the network**, and never depend on anything outside this repository.
- **Running:** from the repository root, in a virtualenv: `pip install -r requirements-dev.txt`, then `python scripts/validate.py` and `pytest`.
- **Commits:** conventional prefixes (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`). Work on branch `claude/vigilant-mayer-k6q1po` (already checked out). Do not push.
- **Scope:** this repository only. The sync, API and app changes have their own plans.

### Rollout note

- This plan is **rollout step 0**. It is safe on its own: the current sync job still reads `indicator-selection.yaml`.
- **Keep Planet's four sector names** (`Agriculture`, `Climate change`, `Environment`, `Water`) until step 3 is live. From step 2 the new sync publishes them from `themes/planet.yaml`, and the app deployed until step 3 hard-codes them; a renamed sector breaks its whole Sectors grid. `tests/test_migration.py` enforces this (Task 4).
- **Before cpf-report deploys (step 3)**, the Planet team confirms the order of `themes/planet.yaml`: the new app follows list order instead of its out-of-date constants. Any reorder before step 6 is made in both `themes/planet.yaml` and `indicator-selection.yaml` (the parity test requires it; reordering the old file is harmless).

## File map

| File | Status | Responsibility |
|---|---|---|
| `requirements-dev.txt`, `pyproject.toml`, `.gitignore` | new | Test dependencies; pytest configuration only (`scripts/` on the import path) |
| `schema/themes-index.schema.json` | new | Schema for `themes.yaml` |
| `schema/theme.schema.json` | new | Schema for `themes/<id>.yaml` |
| `scripts/validate.py` | new | CLI and `check()` / `validate_root()` / `norm_sector()`: schema plus cross-file rules |
| `scripts/migrate_planet.py` | new | One-off: `planet:` block → `themes/planet.yaml` |
| `themes/planet.yaml` | new (generated) | Planet's list in the new shape |
| `themes.yaml` | new | Index: Planet only |
| `.github/CODEOWNERS` | new | Platform owner vs theme teams (placeholder handles) |
| `.github/workflows/validate.yml` | new | CI: validator + pytest on pull requests and pushes to `main` |
| `tests/fixtures/valid/…` | new | A valid root: index + the shared Infrastructure fixture |
| `tests/fixtures/invalid-theme-cases.yaml`, `tests/fixtures/invalid-index-cases.yaml` | new | Named documents each schema must reject, with the expected message |
| `tests/test_schema.py`, `tests/test_validate.py`, `tests/test_migration.py`, `tests/test_repository.py` | new | One file per unit |
| `README.md` | rewrite | Layout, theme files, validation, adding a theme, retiring the old file, ownership |
| `indicator-selection.yaml` | unchanged | Read by the current sync job until step 2; deleted in step 6 |

---

### Task 1: Tooling

**Files:**
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`
- Create: `.gitignore`

**Interfaces:**
- Produces: `pip install -r requirements-dev.txt` (used by CI, Task 5); `pytest` collecting `tests/` with `scripts/` on `sys.path`, so tests `import validate` and `import migrate_planet`.

- [ ] **Step 1: Check the branch**

```bash
git branch --show-current
```

Expected: `claude/vigilant-mayer-k6q1po`.

- [ ] **Step 2: Add the test dependencies**

Create `requirements-dev.txt`:

```text
pyyaml>=6.0
jsonschema>=4.18
pytest>=8.0
```

Create `pyproject.toml`:

```toml
# Test configuration only: this repository holds data, not a Python package.
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["scripts"]
addopts = "-ra"
```

Create `.gitignore`:

```text
__pycache__/
.pytest_cache/
```

- [ ] **Step 3: Install and run pytest**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Expected: `collected 0 items`, a `PytestConfigWarning: No files were found in testpaths` warning, exit code 5 (no tests yet — Task 2 adds the first). `.venv/` is local; do not commit it.

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt pyproject.toml .gitignore
git commit -m "chore: add pytest tooling and dev requirements"
```

---

### Task 2: JSON Schemas

**Files:**
- Create: `tests/fixtures/valid/themes.yaml`
- Create: `tests/fixtures/valid/themes/infrastructure.yaml`
- Create: `tests/fixtures/invalid-theme-cases.yaml`
- Create: `tests/fixtures/invalid-index-cases.yaml`
- Test: `tests/test_schema.py`
- Create: `schema/themes-index.schema.json`
- Create: `schema/theme.schema.json`

**Interfaces:**
- Produces: `schema/themes-index.schema.json` and `schema/theme.schema.json` — the seam artifact `cpf-data360-sync` validates against (read from the raw base URL on `main`).
- Produces: `tests/fixtures/valid/` — a valid repository root (index + the shared Infrastructure fixture, verbatim from the shared contract), reused by Task 3.

- [ ] **Step 1: Add the valid fixtures**

Create `tests/fixtures/valid/themes.yaml`:

```yaml
themes:
  - id: infrastructure
    name: Infrastructure
    file: themes/infrastructure.yaml
```

Create `tests/fixtures/valid/themes/infrastructure.yaml` (the shared Infrastructure fixture — identical in every repository that uses it):

```yaml
sectors:
  - name: Energy
    indicators:
      - short_name: access_to_electricity
        dataset_id: WB_WDI
        indicator_id: WB_WDI_EG_ELC_ACCS_ZS
        full_name: Access to electricity (% of population)
        group: Access
        direction: higher_is_better
        label: Access to electricity
  - name: Water
    indicators:
      - short_name: safely_managed_drinking_water
        dataset_id: WB_WDI
        indicator_id: WB_WDI_SH_H2O_SMDW_ZS
        full_name: People using safely managed drinking water services (% of population)
        group: WASH
        direction: higher_is_better
        label: Safe drinking water
  - name: ICT and digital
    indicators:
      - short_name: internet_users
        dataset_id: WB_WDI
        indicator_id: WB_WDI_IT_NET_USER_ZS
        full_name: Individuals using the Internet (% of population)
        group: Access
        direction: higher_is_better
        label: Internet users
```

- [ ] **Step 2: Add the invalid cases**

Each case names the message fragment the schema must give, so a case cannot pass by failing for an unrelated reason.

Create `tests/fixtures/invalid-theme-cases.yaml`:

```yaml
# Theme documents the schema must reject. Each key is a test id; `error` is a
# fragment of the message the schema must give; `document` is the theme file.
missing_label:
  error: "'label' is a required property"
  document:
    sectors:
      - name: Energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better}
empty_label:
  error: "should be non-empty"
  document:
    sectors:
      - name: Energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: ""}
numeric_label:
  error: "2020 is not of type 'string'"
  document:
    sectors:
      - name: Energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: 2020}
unknown_direction:
  error: "'up' is not one of"
  document:
    sectors:
      - name: Energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: up, label: L}
string_sector_mean:
  error: "'false' is not of type 'boolean'"
  document:
    sectors:
      - name: Energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: L, sector_mean: "false"}
extra_indicator_field:
  error: "('unit' was unexpected)"
  document:
    sectors:
      - name: Energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: L, unit: kg}
extra_sector_field:
  error: "('key' was unexpected)"
  document:
    sectors:
      - name: Energy
        key: energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: L}
extra_top_level_field:
  error: "('pillar' was unexpected)"
  document:
    pillar: infrastructure
    sectors:
      - name: Energy
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: L}
empty_sector_name:
  error: "should be non-empty"
  document:
    sectors:
      - name: ""
        indicators:
          - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: L}
no_sectors:
  error: "[] should be non-empty"
  document:
    sectors: []
no_indicators:
  error: "[] should be non-empty"
  document:
    sectors:
      - name: Energy
        indicators: []
old_nested_shape:
  error: "'sectors' is a required property"
  document:
    planet:
      agriculture:
        - {short_name: a, dataset_id: D, indicator_id: I, full_name: F, group: G, direction: higher_is_better, label: L}
```

Create `tests/fixtures/invalid-index-cases.yaml`:

```yaml
# themes.yaml documents the schema must reject. Each key is a test id; `error`
# is a fragment of the message the schema must give; `document` is the index.
uppercase_id:
  error: "'Planet' does not match"
  document:
    themes:
      - {id: Planet, name: Planet, file: themes/planet.yaml}
id_starts_with_digit:
  error: "'2planet' does not match"
  document:
    themes:
      - {id: 2planet, name: Planet, file: themes/planet.yaml}
hyphen_in_id:
  error: "'planet-2' does not match"
  document:
    themes:
      - {id: planet-2, name: Planet, file: themes/planet.yaml}
missing_file:
  error: "'file' is a required property"
  document:
    themes:
      - {id: planet, name: Planet}
empty_name:
  error: "should be non-empty"
  document:
    themes:
      - {id: planet, name: "", file: themes/planet.yaml}
extra_theme_field:
  error: "('order' was unexpected)"
  document:
    themes:
      - {id: planet, name: Planet, file: themes/planet.yaml, order: 1}
extra_top_level_field:
  error: "('version' was unexpected)"
  document:
    version: 1
    themes:
      - {id: planet, name: Planet, file: themes/planet.yaml}
no_themes:
  error: "[] should be non-empty"
  document:
    themes: []
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_schema.py`:

```python
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


@pytest.mark.parametrize("case", sorted(THEME_CASES))
def test_invalid_theme_fails(case):
    messages = _messages("theme.schema.json", THEME_CASES[case]["document"])
    assert any(THEME_CASES[case]["error"] in m for m in messages), messages


@pytest.mark.parametrize("case", sorted(INDEX_CASES))
def test_invalid_index_fails(case):
    messages = _messages("themes-index.schema.json", INDEX_CASES[case]["document"])
    assert any(INDEX_CASES[case]["error"] in m for m in messages), messages
```

- [ ] **Step 4: Run them to verify they fail**

Run: `pytest -q`
Expected: `25 failed`, each with `FileNotFoundError: [Errno 2] No such file or directory: '…/schema/themes-index.schema.json'` (or `theme.schema.json`).

- [ ] **Step 5: Write the schemas**

Create `schema/themes-index.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://raw.githubusercontent.com/WB-DECIS/cpf-indicator-selection/main/schema/themes-index.schema.json",
  "title": "CPF themes index (themes.yaml)",
  "description": "Ordered list of published themes. Order is the tab order in the app; listing a theme publishes it.",
  "type": "object",
  "additionalProperties": false,
  "required": ["themes"],
  "properties": {
    "themes": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "name", "file"],
        "properties": {
          "id": {
            "description": "Pin-name suffix in the sync job and Shiny module namespace in the app.",
            "type": "string",
            "pattern": "^[a-z][a-z0-9_]*$"
          },
          "name": {
            "description": "Display name, shown as the tab label.",
            "type": "string",
            "minLength": 1
          },
          "file": {
            "description": "Path of the theme's list, relative to the repository root.",
            "type": "string",
            "minLength": 1
          }
        }
      }
    }
  }
}
```

Create `schema/theme.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://raw.githubusercontent.com/WB-DECIS/cpf-indicator-selection/main/schema/theme.schema.json",
  "title": "CPF theme indicator list (themes/<id>.yaml)",
  "description": "One theme's sectors and indicators. List order is display order.",
  "type": "object",
  "additionalProperties": false,
  "required": ["sectors"],
  "properties": {
    "sectors": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/$defs/sector" }
    }
  },
  "$defs": {
    "text": { "type": "string", "minLength": 1 },
    "sector": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "indicators"],
      "properties": {
        "name": { "$ref": "#/$defs/text" },
        "indicators": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/indicator" }
        }
      }
    },
    "indicator": {
      "type": "object",
      "additionalProperties": false,
      "required": ["short_name", "dataset_id", "indicator_id", "full_name", "group", "direction", "label"],
      "properties": {
        "short_name": { "$ref": "#/$defs/text" },
        "dataset_id": { "$ref": "#/$defs/text" },
        "indicator_id": { "$ref": "#/$defs/text" },
        "full_name": { "$ref": "#/$defs/text" },
        "group": { "$ref": "#/$defs/text" },
        "direction": { "enum": ["higher_is_better", "lower_is_better"] },
        "label": { "$ref": "#/$defs/text" },
        "sector_mean": {
          "description": "false keeps the indicator in the per-indicator views but out of its sector's average. Default true.",
          "type": "boolean"
        }
      }
    }
  }
}
```

`themes` has `minItems: 1`: an index with no themes would publish nothing and the API refuses to start with zero themes, so CI rejects it first.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest -q`
Expected: `25 passed`

- [ ] **Step 7: Commit**

```bash
git add schema tests/fixtures tests/test_schema.py
git commit -m "feat: add JSON Schemas for the themes index and theme files"
```

---

### Task 3: Validator

**Files:**
- Test: `tests/test_validate.py`
- Create: `scripts/validate.py`

**Interfaces:**
- Consumes: `schema/*.json` (Task 2), located relative to the script, so `root` only supplies data files.
- Produces:
  - CLI `python scripts/validate.py [root]` (default `.`) — exit 0 and `OK: themes.yaml, N listed theme file(s), M unlisted draft(s)` on stdout; exit 1 and one `ERROR <file>: …` line per problem plus `K error(s) found.` on stderr.
  - `norm_sector(name) -> str` — the contract's `norm()`.
  - `check(root) -> (errors, listed, drafts)` — messages, listed files (index order, POSIX paths relative to `root`), unlisted `themes/*.yaml`.
  - `validate_root(root) -> list[str]` — `check(root)[0]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validate.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest -q`
Expected: collection error — `ModuleNotFoundError: No module named 'validate'`, `1 error`.

- [ ] **Step 3: Implement the validator**

Create `scripts/validate.py`:

```python
"""Validate the theme index and theme files of this repository.

Usage: python scripts/validate.py [root]

Checks themes.yaml against schema/themes-index.schema.json and every theme
file against schema/theme.schema.json, then the rules a JSON Schema cannot
express (cpf-data360-sync implements the same four):

1. theme ids are unique in themes.yaml;
2. every file themes.yaml lists exists;
3. short_name is unique within a listed file;
4. sector names are unique within a listed file after norm_sector().

Files under themes/ that themes.yaml does not list are drafts: they are
schema-checked only. Exits 0 when everything is valid, 1 otherwise.
"""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
INDEX_FILE = "themes.yaml"


def norm_sector(name):
    """Sector-name key: underscores as spaces, whitespace collapsed, lower case.

    Mirrors cpf-report's .norm_sector(); two names with the same key clash.
    """
    return " ".join(name.replace("_", " ").split()).lower()


def _validator(schema_file):
    schema = json.loads((SCHEMA_DIR / schema_file).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _load(path, label, errors):
    """Parsed YAML, or None after recording why it could not be read."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(f"{label}: not valid YAML: {' '.join(str(exc).split())}")
        return None


def _schema_errors(validator, document, label):
    found = sorted(validator.iter_errors(document), key=lambda e: e.json_path)
    return [f"{label}: {e.json_path}: {e.message}" for e in found]


def _theme_rules(document, label):
    errors = []
    seen_short, seen_sector = set(), {}
    for sector in document["sectors"]:
        key = norm_sector(sector["name"])
        if key in seen_sector:
            errors.append(
                f"{label}: sector '{sector['name']}' has the same name as "
                f"'{seen_sector[key]}' once case, spaces and underscores are ignored"
            )
        else:
            seen_sector[key] = sector["name"]
        for indicator in sector["indicators"]:
            short = indicator["short_name"]
            if short in seen_short:
                errors.append(f"{label}: short_name '{short}' appears more than once")
            seen_short.add(short)
    return errors


def check(root):
    """(errors, listed files, unlisted drafts) for the repository at root."""
    root = Path(root)
    index_path = root / INDEX_FILE
    if not index_path.is_file():
        return [f"{INDEX_FILE}: file not found"], [], []

    errors, listed = [], []
    index = _load(index_path, INDEX_FILE, errors)
    if not errors:
        errors += _schema_errors(_validator("themes-index.schema.json"), index, INDEX_FILE)
    if not errors:
        seen_ids = set()
        for theme in index["themes"]:
            if theme["id"] in seen_ids:
                errors.append(f"{INDEX_FILE}: theme id '{theme['id']}' is listed more than once")
            seen_ids.add(theme["id"])
            file = Path(theme["file"]).as_posix()
            if not (root / file).is_file():
                errors.append(
                    f"{INDEX_FILE}: theme '{theme['id']}' lists {file}, which does not exist"
                )
            elif file not in listed:
                listed.append(file)

    drafts = [
        path.relative_to(root).as_posix()
        for path in sorted((root / "themes").glob("*.yaml"))
        if path.relative_to(root).as_posix() not in listed
    ]
    theme_validator = _validator("theme.schema.json")
    for label in listed + drafts:
        file_errors = []
        document = _load(root / label, label, file_errors)
        if not file_errors:
            file_errors += _schema_errors(theme_validator, document, label)
        if not file_errors and label in listed:
            file_errors += _theme_rules(document, label)
        errors += file_errors
    return errors, listed, drafts


def validate_root(root):
    """All problems found under root, as readable one-line messages."""
    return check(root)[0]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else Path(".")
    errors, listed, drafts = check(root)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        print(f"{len(errors)} error(s) found.", file=sys.stderr)
        return 1
    print(
        f"OK: {INDEX_FILE}, {len(listed)} listed theme file(s), "
        f"{len(drafts)} unlisted draft(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Behaviour worth knowing: a `themes.yaml` that fails its schema stops the index rules (they would read malformed entries), but `themes/*.yaml` are still schema-checked and reported in the same run; a theme file that fails its schema skips rules 3–4 for that file.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest -q`
Expected: `44 passed`

- [ ] **Step 5: Try the CLI**

```bash
python scripts/validate.py tests/fixtures/valid
python scripts/validate.py; echo "exit=$?"
```

Expected:

```text
OK: themes.yaml, 1 listed theme file(s), 0 unlisted draft(s)
ERROR themes.yaml: file not found
1 error(s) found.
exit=1
```

(The repository root has no `themes.yaml` until Task 5.)

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.py tests/test_validate.py
git commit -m "feat: add the theme validator with the cross-file rules"
```

---

### Task 4: Migrate Planet

**Files:**
- Test: `tests/test_migration.py`
- Create: `scripts/migrate_planet.py`
- Create (generated): `themes/planet.yaml`

**Interfaces:**
- Consumes: `indicator-selection.yaml` (`planet:` block, read-only).
- Produces:
  - `themes/planet.yaml` — Planet's list in the new shape, validated by Task 3's rules once listed (Task 5).
  - `migrate_planet.SECTOR_NAMES` (the contract's key → name map), `migrate(planet_block) -> dict`, `render(doc) -> str`.
  - A parity test that keeps `themes/planet.yaml` and `indicator-selection.yaml` in step, and freezes Planet's sector names, until step 6.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_migration.py`:

```python
"""themes/planet.yaml carries the planet: block of indicator-selection.yaml.

The parity test keeps the two files in step while the current sync job still
reads indicator-selection.yaml. Delete this file together with
indicator-selection.yaml (rollout step 6).
"""
from pathlib import Path

import pytest
import yaml

import migrate_planet

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["short_name", "dataset_id", "indicator_id", "full_name", "group", "direction", "label"]


def _load(name):
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_planet_yaml_matches_indicator_selection():
    legacy = _load("indicator-selection.yaml")["planet"]
    planet = _load("themes/planet.yaml")

    expected = [
        (migrate_planet.SECTOR_NAMES[key], [ind[f] for f in FIELDS])
        for key, indicators in legacy.items()
        for ind in indicators
    ]
    actual = [
        (sector["name"], [ind[f] for f in FIELDS])
        for sector in planet["sectors"]
        for ind in sector["indicators"]
    ]
    assert actual == expected


def test_only_total_ghg_emissions_is_out_of_the_sector_mean():
    planet = _load("themes/planet.yaml")
    flagged = {
        ind["short_name"]: ind["sector_mean"]
        for sector in planet["sectors"]
        for ind in sector["indicators"]
        if "sector_mean" in ind
    }
    assert flagged == {"total_ghg_emissions": False}


def test_planet_keeps_its_four_sector_names():
    planet = _load("themes/planet.yaml")
    assert [s["name"] for s in planet["sectors"]] == [
        "Agriculture", "Climate change", "Environment", "Water",
    ]


def test_migrate_maps_keys_and_flags_exclusions():
    block = {
        "climate_change": [
            {f: f"{f}_1" for f in FIELDS} | {"short_name": "total_ghg_emissions"},
        ],
        "water": [{f: f"{f}_2" for f in FIELDS}],
    }
    doc = migrate_planet.migrate(block)
    assert [s["name"] for s in doc["sectors"]] == ["Climate change", "Water"]
    assert doc["sectors"][0]["indicators"][0]["sector_mean"] is False
    assert "sector_mean" not in doc["sectors"][1]["indicators"][0]
    assert list(doc["sectors"][0]["indicators"][0]) == FIELDS + ["sector_mean"]


def test_migrate_rejects_an_unknown_sector_key():
    with pytest.raises(KeyError, match="energy"):
        migrate_planet.migrate({"energy": []})


def test_render_round_trips_and_keeps_a_header():
    doc = migrate_planet.migrate(_load("indicator-selection.yaml")["planet"])
    text = migrate_planet.render(doc)
    assert text.startswith("# themes/planet.yaml\n")
    assert yaml.safe_load(text) == doc
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest -q`
Expected: collection error — `ModuleNotFoundError: No module named 'migrate_planet'`, `1 error`.

- [ ] **Step 3: Implement the migration**

Create `scripts/migrate_planet.py`:

```python
"""One-off: write themes/planet.yaml from the planet: block of indicator-selection.yaml.

Usage: python scripts/migrate_planet.py [root]

After the migration themes/planet.yaml is edited by hand; this script is kept
only as a record of how it was produced, and is deleted with
indicator-selection.yaml (rollout step 6).
"""
import sys
from pathlib import Path

import yaml

# Replaces cpf-data360-sync's SECTOR_KEY_MAP.
SECTOR_NAMES = {
    "agriculture": "Agriculture",
    "climate_change": "Climate change",
    "environment": "Environment",
    "water": "Water",
}
# Replaces cpf-api's aggregation_exclusions.yaml.
OUT_OF_SECTOR_MEAN = {"total_ghg_emissions"}
FIELDS = ["short_name", "dataset_id", "indicator_id", "full_name", "group", "direction", "label"]

HEADER = """\
# themes/planet.yaml
# ------------------
# Planet theme indicator list, owned by the Planet team (see CODEOWNERS).
# Migrated from the planet: block of indicator-selection.yaml by
# scripts/migrate_planet.py; edit this file directly from now on.
# Validated against schema/theme.schema.json by scripts/validate.py.
# List order is display order: sectors, sub-categories (group, by first
# appearance) and indicators. Each indicator: short_name (stable API id,
# unique in this file), dataset_id (Data360 DATABASE_ID), indicator_id,
# full_name, group (-> sub_category), direction, label, and optionally
# sector_mean (default true; false keeps it out of its sector's average).
# Keep the four sector names unchanged until the multi-theme app is live.
"""


class _IndentedDumper(yaml.SafeDumper):
    """Indents list items under their key, as in the repository's examples."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def migrate(planet_block):
    """The theme document for a {sector_key: [indicator, ...]} block, in order."""
    sectors = []
    for key, indicators in planet_block.items():
        entries = []
        for indicator in indicators:
            entry = {field: indicator[field] for field in FIELDS}
            if entry["short_name"] in OUT_OF_SECTOR_MEAN:
                entry["sector_mean"] = False
            entries.append(entry)
        sectors.append({"name": SECTOR_NAMES[key], "indicators": entries})
    return {"sectors": sectors}


def render(doc):
    body = yaml.dump(
        doc, Dumper=_IndentedDumper, sort_keys=False, allow_unicode=True, width=1000
    )
    return HEADER + body


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else Path(".")
    source = yaml.safe_load((root / "indicator-selection.yaml").read_text(encoding="utf-8"))
    target = root / "themes" / "planet.yaml"
    target.parent.mkdir(exist_ok=True)
    target.write_text(render(migrate(source["planet"])), encoding="utf-8")
    print(f"wrote {target.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

The custom dumper indents list items under their key (the layout of the design's examples), and `width=1000` keeps long `full_name`s on one line.

- [ ] **Step 4: Run the tests before generating the file**

Run: `pytest -q`
Expected: `3 failed, 47 passed` — the three tests that read `themes/planet.yaml` fail with `FileNotFoundError`; the `migrate()` / `render()` unit tests pass.

- [ ] **Step 5: Generate `themes/planet.yaml`**

```bash
python scripts/migrate_planet.py
```

Expected: `wrote themes/planet.yaml`. The file is 204 lines. Its head:

```yaml
# themes/planet.yaml
# ------------------
# Planet theme indicator list, owned by the Planet team (see CODEOWNERS).
# Migrated from the planet: block of indicator-selection.yaml by
# scripts/migrate_planet.py; edit this file directly from now on.
# Validated against schema/theme.schema.json by scripts/validate.py.
# List order is display order: sectors, sub-categories (group, by first
# appearance) and indicators. Each indicator: short_name (stable API id,
# unique in this file), dataset_id (Data360 DATABASE_ID), indicator_id,
# full_name, group (-> sub_category), direction, label, and optionally
# sector_mean (default true; false keeps it out of its sector's average).
# Keep the four sector names unchanged until the multi-theme app is live.
sectors:
  - name: Agriculture
    indicators:
      - short_name: food_price_inflation
        dataset_id: FAO_CP
        indicator_id: FAO_CP_23014
        full_name: Food price inflation
        group: Food and Nutrition
        direction: lower_is_better
        label: Food price inflation
      - short_name: ipc_phase3_plus_population
        dataset_id: IPC_IPC
        indicator_id: IPC_IPC_P3PLUS
        full_name: Population in Phase 3 food insecurity or above
        group: Food and Nutrition
        direction: lower_is_better
        label: Food insecurity
      - short_name: stunting_height_for_age_pct
        dataset_id: UNICEF_DW
        indicator_id: UNICEF_DW_NT_ANT_HAZ_NE2
        full_name: Height-for-age <-2 SD (stunting)
        group: Food and Nutrition
        direction: lower_is_better
        label: Stunting
      - short_name: cereal_yield
        dataset_id: WB_WDI
        indicator_id: WB_WDI_AG_YLD_CREL_KG
        full_name: Cereal yield (kg per hectare)
```

and the one flagged indicator:

```yaml
      - short_name: total_ghg_emissions
        dataset_id: OWID_CB
        indicator_id: OWID_CB_TOTAL_GHG
        full_name: Total greenhouse gas emissions
        group: Mitigation
        direction: lower_is_better
        label: Total GHG emissions
        sector_mean: false
```

The only quoted value is `water_stress_withdrawal_ratio`'s `full_name`, which contains `: `.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest -q`
Expected: `50 passed`

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_planet.py tests/test_migration.py themes/planet.yaml
git commit -m "feat: migrate the planet block to themes/planet.yaml"
```

---

### Task 5: Index, CODEOWNERS and CI

**Files:**
- Test: `tests/test_repository.py`
- Create: `themes.yaml`
- Create: `.github/CODEOWNERS`
- Create: `.github/workflows/validate.yml`

**Interfaces:**
- Produces: `themes.yaml` listing Planet — the index the sync job reads from `main` from step 2 on; CI that runs the validator and `pytest` on every pull request and on pushes to `main`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_repository.py`:

```python
"""The repository's own index and theme files pass the validator."""
from pathlib import Path

import validate

ROOT = Path(__file__).resolve().parent.parent


def test_repository_is_valid():
    assert validate.validate_root(ROOT) == []

```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest -q`
Expected: `1 failed, 50 passed` — `AssertionError: assert ['themes.yaml: file not found'] == []`.

- [ ] **Step 3: Add the index**

Create `themes.yaml`:

```yaml
# themes.yaml
# -----------
# Published themes, maintained by the platform owner (see CODEOWNERS).
# Order is the tab order in the app. Listing a theme publishes it at the
# next render of the cpf-data360-sync job, so list a theme only when its
# file is ready. Validated against schema/themes-index.schema.json by
# scripts/validate.py.
themes:
  - id: planet
    name: Planet
    file: themes/planet.yaml
```

- [ ] **Step 4: Add CODEOWNERS**

Create `.github/CODEOWNERS`:

```text
# Replace the placeholder team handles before merging (README -> Ownership).
# The last matching line wins.

# Platform owner: everything not matched below, including the index, the
# schema, the validator and CI.
*                     @WB-DECIS/cpf-platform
/themes.yaml          @WB-DECIS/cpf-platform
/schema/              @WB-DECIS/cpf-platform
/scripts/             @WB-DECIS/cpf-platform
/.github/             @WB-DECIS/cpf-platform

# One line per theme file, owned by that theme's team.
/themes/planet.yaml   @WB-DECIS/planet-team
```

`@WB-DECIS/cpf-platform` and `@WB-DECIS/planet-team` are **placeholders**: replace them with the real team handles before merging. GitHub ignores a line whose owner lacks write access, and the file has effect only with "Require review from Code Owners" on in `main`'s branch protection.

- [ ] **Step 5: Add the workflow**

Create `.github/workflows/validate.yml`:

```yaml
name: validate

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Validate the index and theme files
        run: python scripts/validate.py
      - name: Run the tests
        run: pytest
```

- [ ] **Step 6: Run the validator and the tests**

```bash
python scripts/validate.py; echo "exit=$?"
pytest -q
```

Expected:

```text
OK: themes.yaml, 1 listed theme file(s), 0 unlisted draft(s)
exit=0
51 passed
```

- [ ] **Step 7: Commit**

```bash
git add themes.yaml .github/CODEOWNERS .github/workflows/validate.yml tests/test_repository.py
git commit -m "feat: list planet in themes.yaml and add CODEOWNERS and CI"
```

---

### Task 6: README

**Files:**
- Modify: `README.md` (replace the whole file)

**Interfaces:**
- Produces: the repository's half of the "Adding a theme" runbook (spec → "Adding a theme afterwards"); cpf-report's README carries the cross-repo "Add a theme" row.

- [ ] **Step 1: Replace the README**

The current `README.md` is one paragraph (`This repository contains a YAML file used to specify indicators associated with country profiles. …`). Replace the whole file with:

````markdown
# cpf-indicator-selection

The indicator lists behind the CPF Country Diagnostics dashboard, one list per theme. The
`cpf-data360-sync` job reads them from `main`, fetches each theme's data from Data360 and
publishes it for `cpf-api`; the app shows one tab per theme.

## Layout

| Path | What it is | Owner |
|---|---|---|
| `themes.yaml` | The index: `{id, name, file}` per published theme. Its order is the app's tab order. | Platform owner |
| `themes/<id>.yaml` | One theme's list: sectors, each with its indicators. | That theme's team |
| `schema/themes-index.schema.json`, `schema/theme.schema.json` | JSON Schema (draft 2020-12) for the two file kinds. `cpf-data360-sync` validates against these same files. | Platform owner |
| `scripts/validate.py` | Schema checks plus the cross-file rules below. | Platform owner |
| `scripts/migrate_planet.py` | One-off that produced `themes/planet.yaml`. | Platform owner |
| `indicator-selection.yaml` | The old single-file list. Read by the current sync job only; see "Retiring indicator-selection.yaml". | Platform owner |
| `.github/CODEOWNERS`, `.github/workflows/validate.yml` | Ownership and CI. | Platform owner |

## Theme files

```yaml
sectors:
  - name: Agriculture              # display name, exactly as the app shows it
    indicators:
      - short_name: cereal_yield   # stable API id, unique within this file
        dataset_id: WB_WDI         # Data360 DATABASE_ID (not the code prefix)
        indicator_id: WB_WDI_AG_YLD_CREL_KG
        full_name: Cereal yield (kg per hectare)
        group: Production          # sub-category
        direction: higher_is_better   # or lower_is_better
        label: Cereal yield
        # sector_mean: false       # optional, default true
```

- **List order is display order** for sectors, sub-categories (`group`, in order of first
  appearance) and indicators.
- **`sector_mean: false`** keeps an indicator in the per-indicator views but out of its sector's
  average (the sector bar in the Sectors view). Leave it out for the default, `true`. Planet uses
  it on `total_ghg_emissions`.
- The same `short_name` may appear in another theme's file; an indicator is identified by
  `(theme, short_name)`.

## Validation

`python scripts/validate.py [root]` exits 0 when the repository is valid and 1 with one line per
problem otherwise. CI runs it and `pytest` on every pull request and on pushes to `main`. It checks:

- `themes.yaml` against `schema/themes-index.schema.json`: theme `id`s are lower-case letters,
  digits and underscores, starting with a letter;
- every theme file against `schema/theme.schema.json`: the seven fields above are required
  non-empty strings, `direction` is one of the two values, `sector_mean` is a boolean, no other
  keys, and no empty `sectors` or `indicators` lists;
- the rules a schema cannot express, which `cpf-data360-sync` applies too:
  1. theme `id`s are unique in `themes.yaml`;
  2. every file `themes.yaml` lists exists;
  3. `short_name` is unique within a listed file;
  4. sector names are unique within a listed file once case, spaces and underscores are ignored
     (`Climate change`, `climate_change` and `CLIMATE  CHANGE` clash).

Files under `themes/` that `themes.yaml` does not list are drafts: they are schema-checked only.

Locally:

```bash
pip install -r requirements-dev.txt
python scripts/validate.py
pytest
```

## Adding a theme

1. **Draft.** Open a pull request that adds `themes/<id>.yaml` and a `CODEOWNERS` line for the
   theme's team. Do not list it in `themes.yaml` yet: an unlisted file is only schema-checked, and
   nothing publishes it, so it can be merged and refined on `main`.
2. **Publish.** When the list is ready, the platform owner opens a pull request that adds
   `{id, name, file}` to `themes.yaml`, at the position the tab should take. CI now applies every
   rule to the file. Merging publishes the theme at the next render of the sync job.
3. **Go live** (on Posit Connect, by whoever runs the rollout):
   1. render `cpf-data360-sync` (or wait for its schedule);
   2. grant the API's account viewer access to the theme's two new pins,
      `cpf_observations_<id>` and `cpf_metadata_<id>` — Connect creates them owner-only, and until
      the grant the API logs an ERROR and leaves the theme out;
   3. restart the API, then the app, which builds its theme list at startup.

No code changes in any repository. Before the first theme after Planet, the methodology document
must already be theme-neutral (design, rollout step 5).

## Retiring `indicator-selection.yaml`

`indicator-selection.yaml` stays, unchanged, until the multi-theme sync job is live (design
rollout step 2): the current job still reads it. Until then keep it and `themes/planet.yaml` in
step; `tests/test_migration.py` fails when they differ. It is deleted, with that test and
`scripts/migrate_planet.py`, in the cleanup (rollout step 6).

Keep Planet's four sector names (`Agriculture`, `Climate change`, `Environment`, `Water`)
unchanged until the multi-theme app is live (rollout step 3): the app deployed before it
hard-codes them.

## Ownership

`.github/CODEOWNERS` gives the platform owner the index, the schema, the scripts and CI, and each
theme's team its own file. The handles in it (`@WB-DECIS/cpf-platform`, `@WB-DECIS/planet-team`)
are placeholders: replace them with real teams that have write access, and turn on "Require review
from Code Owners" in the `main` branch protection, or the file has no effect.
````

- [ ] **Step 2: Run everything once more**

```bash
python scripts/validate.py
pytest
```

Expected:

```text
OK: themes.yaml, 1 listed theme file(s), 0 unlisted draft(s)
…
tests/test_migration.py ......                                           [ 11%]
tests/test_repository.py .                                               [ 13%]
tests/test_schema.py .........................                           [ 62%]
tests/test_validate.py ...................                               [100%]

============================== 51 passed in 0.52s ==============================
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document themes, validation and adding a theme"
```

---

## After the tasks

- **Rollout step 0:** open the pull request (after replacing the CODEOWNERS placeholders) and merge once CI is green. Nothing reads the new files yet; the current sync job keeps reading `indicator-selection.yaml`. Then make the `validate` job a required status check on `main`.
- **Local chain** (spec → Verification, before step 3): the sync plan's local run uses this repository through `CPF_SELECTION_DIR=<local checkout>`, with a `themes.yaml` that also lists the Infrastructure draft below. Do that listing in the local checkout only; never push it before step 4.
- **Drafting Infrastructure** (starting point for rollout step 4): copy the shared fixture, `tests/fixtures/valid/themes/infrastructure.yaml`, to `themes/infrastructure.yaml` and add `/themes/infrastructure.yaml @WB-DECIS/<infrastructure-team>` to CODEOWNERS. Leave it out of `themes.yaml` until step 4 (its prerequisite is the methodology's step 5). Verified: unlisted, the validator reports `OK: themes.yaml, 1 listed theme file(s), 1 unlisted draft(s)`; listed, `OK: themes.yaml, 2 listed theme file(s), 0 unlisted draft(s)`; renaming its "ICT and digital" sector to `water` then fails with `ERROR themes/infrastructure.yaml: sector 'water' has the same name as 'Water' once case, spaces and underscores are ignored`. Confirm the three Data360 ids (`WB_WDI_EG_ELC_ACCS_ZS`, `WB_WDI_SH_H2O_SMDW_ZS`, `WB_WDI_IT_NET_USER_ZS`) against the Data360 metadata endpoint before a live local-chain run.
- **Step 3:** once the multi-theme app is live, `test_planet_keeps_its_four_sector_names` can be deleted; the Planet team may then rename sectors.
- **Step 6 (cleanup):** delete `indicator-selection.yaml`, `scripts/migrate_planet.py` and `tests/test_migration.py` in one commit, and update the README's "Retiring `indicator-selection.yaml`" section.
- **Changing the schema later** is a cross-repository change: the sync validates against these files from `main`, so a new required field or a tighter rule rejects every theme at the next render until the lists comply. Add optional fields first.
- **Not verified here:** the workflow was not run on GitHub Actions (its steps were run by hand in a fresh virtualenv: `OK: …`, `51 passed`), and CODEOWNERS enforcement depends on the real handles and branch protection.
