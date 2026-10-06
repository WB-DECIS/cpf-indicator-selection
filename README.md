# cpf-indicator-selection

The indicator lists behind the CPF Country Diagnostics dashboard, one list per theme. The
`cpf-data360-sync` job reads them — the PROD job from `main`, the DEV job from `DEV` — fetches
each theme's data from Data360 and publishes it for `cpf-api`; the app shows one tab per theme.

## Branches

| Branch | Read by | Environment |
|---|---|---|
| `DEV` | the DEV sync (`CPF_SELECTION_REF=DEV`) | DEV: `dev-cpf-api` and the DEV app |
| `main` | the PROD sync | PROD |

Every change goes to `DEV` first: a feature branch from `DEV`, a pull request into `DEV` (CI
green), a check on the DEV chain, then a pull request `DEV` → `main`, which publishes it to PROD.
Hotfixes branch from `main`, go into `main`, and are then merged back into `DEV`. Both branches
are protected: pull requests required, the `validate` check required, and CODEOWNERS review.

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
        # dimensions:              # optional: the Data360 series to keep
        #   UNIT_MEASURE: PT_GDP
        # most_recent: true        # optional, default false
```

- **List order is display order** for sectors, sub-categories (`group`, in order of first
  appearance) and indicators.
- **`sector_mean: false`** keeps an indicator in the per-indicator views but out of its sector's
  average (the sector bar in the Sectors view). Leave it out for the default, `true`. Planet uses
  it on `total_ghg_emissions`.
- **`dimensions`** picks one series when Data360 returns several per country and period (several
  units, or breakdowns such as a total next to its parts): one code for each dimension to fix,
  among `UNIT_MEASURE`, `SEX`, `AGE`, `URBANISATION` and `COMP_BREAKDOWN_1` to `_3`.
  `cpf-data360-sync` skips, and reports, an indicator that still has several series; it fails
  the indicator when a listed code has no data.
- **`most_recent: true`** always uses the country's most recent value: the latest period within
  each year (the latest month of a monthly series, instead of the year's mean), and the country's
  latest year, with no 80-country rule and no `>2010` average. Peers are compared in that year.
  Planet uses it on `food_price_inflation`.
- The same `short_name` may appear in another theme's file; an indicator is identified by
  `(theme, short_name)`.

## Validation

`python scripts/validate.py [root]` exits 0 when the repository is valid and 1 with one line per
problem otherwise. CI runs it and `pytest` on pull requests into, and pushes to, `DEV` and `main`. It checks:

- `themes.yaml` against `schema/themes-index.schema.json`: theme `id`s are lower-case letters,
  digits and underscores, starting with a letter, and each `file` is `themes/<name>.yaml`, with
  `<name>` following the same rule (no absolute paths, `..` or files outside `themes/`);
- every theme file against `schema/theme.schema.json`: the seven fields above are required
  non-empty strings, `direction` is one of the two values, `sector_mean` and `most_recent` are
  booleans, `dimensions` keys are the dimensions listed above and their codes non-empty strings,
  no other keys, and no empty `sectors`, `indicators` or `dimensions`;
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

1. **Draft.** Open a pull request into `DEV` that adds `themes/<id>.yaml` and a `CODEOWNERS`
   line for the theme's team. Do not list it in `themes.yaml` yet: an unlisted file is only
   schema-checked, and nothing publishes it, so it can be merged and refined on `DEV`.
2. **List it on `DEV`.** When the list is ready, the platform owner opens a pull request into
   `DEV` that adds `{id, name, file}` to `themes.yaml`, at the position the tab should take. CI
   now applies every rule to the file. Merging publishes the theme on the DEV chain only, at the
   next render of the DEV sync job.
3. **Check it on DEV** (on Posit Connect, by whoever runs the rollout):
   1. render the DEV `cpf-data360-sync` content (or wait for its schedule);
   2. grant `dev-cpf-api`'s account viewer access to the theme's two new pins,
      `dev_cpf_observations_<id>` and `dev_cpf_metadata_<id>` — Connect creates them owner-only,
      and until the grant the API logs an ERROR and leaves the theme out;
   3. restart `dev-cpf-api`, then the DEV app, which builds its theme list at startup, and check
      the new tab.
4. **Publish to PROD.** Open a pull request `DEV` → `main`. After it merges, repeat step 3 on
   PROD: render the PROD sync, grant `cpf-api` viewer access to `cpf_observations_<id>` and
   `cpf_metadata_<id>`, restart `cpf-api`, then the app.

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
theme's team its own file. The handles in it (`@WB-DECIS/cpf-platform`, `@WB-DECIS/planet-team`,
`@WB-DECIS/infrastructure-team`) are placeholders: replace them with real teams that have write access, and turn on "Require review
from Code Owners" in the branch protection of both `DEV` and `main`, or the file has no effect.
