# scheming_dynamic

Store ckanext-scheming dataset schemas in the database and edit them without
a server restart.

## How it works

- Schemas live in the `scheming_schema_version` table (`entity_type` +
  `schema_type` + `version` primary key, JSONB `definition`). `schema_type`
  is a unique entity type (e.g. `dataset_type`) and must match the
  `dataset_type` field inside the definition. A schema's live definition is
  its head (highest) version row: `scheming_schema_create` locks version 1
  immediately, and edits either overwrite that head row in place (nothing
  has pinned it yet) or fork the next version (an entity is already pinned
  to it) — see `scheming_schema_pin`.
- Before ckanext-scheming returns any dataset schema it asks this extension
  whether anything changed since the last merge — a cheap lookup of a single
  row in `scheming_state` (one row per counter key, a version counter
  bumped on every create/update/delete), at most once per request. When it
  did, all dataset schemas are rebuilt: the file-defined schemas from
  `scheming.dataset_schemas` overlaid with the database rows. A database
  schema with the same type name as a file schema wins.
- The check runs per worker process, so changes made through the API
  propagate to every worker without coordination.
- Dataset types created after startup are served by catch-all
  `/<package_type>/...` blueprints. Types registered at startup keep their
  regular CKAN blueprints, which always take precedence. URLs built with
  `url_for("<type>.read")` for database-only types are rewritten through the
  catch-all blueprints by a Flask `url_build_error_handler`.
- Field presets work the same way: they live in the `scheming_preset` table
  and get overlaid onto the presets registered at startup (built-in plus any
  `scheming.presets` files), checked with the same per-request/per-worker
  fingerprint as schemas. A database preset with the same name as a
  built-in/file-registered one wins, same as a database schema overriding
  a file schema of the same type. A database preset can base itself on
  another registered preset — built-in or database — via its own `preset`
  value, resolved once when it's read from the database. A base chain that
  would loop is rejected when the preset is created/updated, not at read
  time.

## Setup

```sh
pip install ckanext-scheming[dynamic]
```

```ini
ckan.plugins = scheming_datasets scheming_dynamic
# let scheming handle dataset types CKAN did not know about at startup
scheming.dataset_fallback = true
```

Apply the migration:

```sh
ckan db upgrade -p scheming_dynamic
```

### Enabling on a portal with existing data

If the portal already has datasets under a file-defined (`scheming.dataset_schemas`)
type, importing that schema into the database and pinning existing datasets to it
keeps them validating/rendering against the exact schema they were created with,
even after later edits. Run once per existing dataset type:

```sh
ckan scheming-dynamic sync --type dataset SCHEMA_TYPE
ckan scheming-dynamic pin --type dataset SCHEMA_TYPE
```

`sync` imports the static definition into the database and locks it as version 1.
`pin` then locks every not-yet-pinned dataset of that type to a specific version

See [CLI](#cli) below for the full flag reference.

## API

All actions are sysadmin-only.

- `scheming_schema_create(definition, entity_type="dataset")` — schema type is taken from the definition's type field
- `scheming_schema_update(schema_type, definition, entity_type="dataset")`
- `scheming_schema_delete(schema_type, entity_type="dataset")` — refuses if a dataset of that type still exists
- `scheming_preset_create(definition)` — `definition` is `{"preset_name": ..., "values": {...}}`; preset name is taken from `definition.preset_name`
- `scheming_preset_update(preset_name, definition)`
- `scheming_preset_delete(preset_name)` — refuses if any (database) schema field still uses this preset, directly or through another preset based on it

Schema migration (see [Migrations](#migrations)):

- `scheming_migration_status(entity_type="dataset", schema_type=None)` — how many datasets of each schema type lag behind its live version
- `scheming_migration_mapping_show(schema_type, from_version, to_version)` — the stored mapping (or the auto-derived suggestion), the field-by-field classification, and what still needs deciding
- `scheming_migration_mapping_update(schema_type, from_version, to_version, mapping)`
- `scheming_migration_mapping_delete(schema_type, from_version, to_version)`
- `scheming_migration_apply(schema_type, from_version, to_version, id=None, values=None, dry_run=False)` — with `id`, migrates that dataset synchronously; without it, queues a background run over every dataset still pinned to `from_version`
- `scheming_migration_run_list(entity_type="dataset", schema_type=None, limit=20, offset=0)`
- `scheming_migration_run_show(id)` — a run plus its per-dataset results
- `scheming_migration_run_cancel(id)` — stop a queued or running migration after its current dataset

Definitions are validated against a JSON Schema mirroring the minimal shape.
`values` accepts the same attributes a dataset/resource field can (`validators`,
`form_snippet`, `display_snippet`, `choices`, `field_name`, `preset`, ...);
setting `values.preset` bases the new preset on another registered one.


## CLI

- `ckan scheming-dynamic validation-schema --type dataset|group|organization` — print the JSON Schema that validates a ckanext-scheming schema definition
- `ckan scheming-dynamic validate --type dataset schema.yaml [more.json ...]` — validate schema definition file(s) against that JSON Schema
- `ckan scheming-dynamic sync --type dataset SCHEMA_TYPE` — bootstrap a dynamic schema from its static (file-defined) definition: creates it and locks version 1 if none exists yet, or locks a new version if the static definition changed since the last locked version (reports and does nothing if unchanged). Run this once when turning on scheming_dynamic on a portal that already has entities of `SCHEMA_TYPE`; existing entities are left unpinned.
- `ckan scheming-dynamic pin --type dataset SCHEMA_TYPE [-v VERSION] [--no-validate] [--dry-run]` — pin every not-yet-pinned entity of `SCHEMA_TYPE` to a locked schema version (default: current HEAD). Each entity's data is validated against that version first; entities that fail are reported and left unpinned rather than failing the whole command. `--no-validate` pins everything unconditionally, skipping that check. `--dry-run` reports what would be pinned/would fail without writing any pins.
- `ckan scheming-dynamic migration status --type dataset [SCHEMA_TYPE]` — how far each schema type lags behind its live version
- `ckan scheming-dynamic migration mapping --type dataset SCHEMA_TYPE FROM TO [--json]` — the field mapping between two versions, plus whatever still needs a decision. Exits non-zero while anything is undecided
- `ckan scheming-dynamic migration apply --type dataset SCHEMA_TYPE FROM TO [--dry-run]` — migrate every dataset pinned to `FROM`. Runs inline with a progress bar, so a portal with no job worker can still migrate
- `ckan scheming-dynamic migration runs --type dataset [RUN_ID]` — list runs, or show one with its per-dataset results
- `ckan scheming-dynamic migration cancel RUN_ID`
- `ckan scheming-dynamic migration prune --older-than DAYS` — drop the recorded before/after values from old run items, keeping their outcome

## Admin UI

Sysadmins get a **Scheming** tab under `/ckan-admin/` (mounted at
`/ckan-admin/scheming/`), with **Schemas** and **Presets** sub-tabs listing
the dynamic dataset schemas and field presets and allowing creating, editing
and deleting them. Create/update/delete go through the `scheming_schema_*`/
`scheming_preset_*` actions, so the same validation applies and
`ValidationError`s are shown in the form.

A **Migrations** sub-tab lists how far each schema type lags behind its live
version, with the mapping editor, the run history, and the guided per-dataset
form for anything a mapping cannot answer generically.

The definition is edited either as raw JSON in a textarea or through a form
generated from the JSON Schema by [JSON Editor](https://github.com/json-editor/json-editor).
The generated form supports adding/removing dataset and resource fields,
reordering them with move up/down buttons and picking `preset` values from
the registered presets (built-in, file-registered, and database). A
**Preview form** button on the schema form renders the current (unsaved)
definition with the same form snippets the real dataset/resource forms use.

## Migrations

Datasets stay pinned to the schema version they were created under, so a portal
accumulates datasets spread across old versions. A migration moves them onto a
newer version of **the same schema** — changing a dataset's *type* is out of
scope, and so is going back to an older version.

### Mapping

A migration is driven by a *mapping*: one entry per field of the target version,
stored per ordered version pair in `scheming_schema_migration`. Most of it is
derived automatically by comparing the two versions, restricted to the
attributes that decide whether a stored value is still valid (`validators`,
`choices`, `repeating_subfields`, `required`). Label, help text, snippets and
field order never block an automatic mapping.

| case | what happens |
|------|--------------|
| unchanged, or loosened (validator dropped, choice added, no longer required) | copied automatically |
| tightened (validator added) | copied, flagged |
| a choice that stored data uses was removed | needs a replacement value |
| became required | needs an answer |
| new optional field, or one with a default | filled automatically |
| new required field with no default | needs an answer |
| removed field | needs an explicit acknowledgement that its data is lost |
| looks like a renamed field | proposed, but never applied without confirmation |

A rename is never accepted silently even on a perfect signature match: a wrong
rename moves data into the wrong field and nothing downstream catches it.

Each entry picks an action — `copy` (optionally with a `value_map` rewriting
individual values), `constant`, `default`, `drop`, or `manual`. `manual` defers
the field to the guided per-dataset form, and a mapping containing one cannot
be applied in bulk.

### Running

One dataset migrates synchronously; more than one is queued as a background
job. Either way the result is a *run* (`scheming_schema_migration_run`) with one
item per dataset recording `ok`/`failed`/`skipped`, the validation errors, and
the before/after values of every field that actually changed.

Per dataset the migration reads the data under its current pin, rebuilds it
against the target schema, moves the pin, and calls `package_update`. If that
fails validation, the pin change is rolled back with it — a dataset is never
left pinned to a version its data does not satisfy. Failures are recorded and
the run continues.

Only one run may be active per version pair at a time, enforced by a partial
unique index. Applying a mapping is idempotent: a dataset already on the target
version is recorded `skipped`, so a run killed halfway is resumed by running it
again.

### Data loss

There is no revert. Datasets are meant to converge on the live schema, and the
"the mapping was wrong" case is what the mapping preview and `--dry-run` exist
to catch before anything is written.

The one irreversible action is `drop`. Its guards are the explicit
acknowledgement required in the mapping, the dry run, and the `changes` recorded
on each run item — a diff, not a full snapshot, so it survives later edits to
the dataset. `migration prune` is what finally discards those values, and it
never runs on its own.

## Known limitations

- Only dataset schemas are merged at runtime; `group`/`organization` rows
  can be stored but are not yet picked up by ckanext-scheming.
- Changing a schema does not reindex existing datasets; run
  `ckan search-index rebuild` after incompatible changes, including after a
  migration.
- Migrations only cover datasets that are pinned. Datasets predating pinning
  resolve to the live schema and must be adopted with `pin` first.
- A mapping is authored against presets as they resolve *now*. Because presets
  are unversioned (below), a stored mapping can silently come to mean something
  different after a preset is edited. Better to implement preset versioning
  or store expanded preset.
- Version locking only covers the schema `definition` itself, not the
  presets it references. `SchemingPreset` rows are live/unversioned and
  shared globally, so editing a preset changes what every schema version
  using it resolves to, including versions already locked/pinned. A real
  fix needs preset versioning (or expanding+freezing preset values into the
  schema snapshot at lock time, at the cost of the raw/editable definition).
