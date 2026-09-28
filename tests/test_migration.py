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
