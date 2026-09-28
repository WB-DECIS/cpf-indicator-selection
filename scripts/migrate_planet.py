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
