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
            # The schema's pattern keeps file under root/themes/; only then is this join safe.
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
