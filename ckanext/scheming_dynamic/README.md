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

Definitions are validated against a JSON Schema mirroring the minimal shape.
`values` accepts the same attributes a dataset/resource field can (`validators`,
`form_snippet`, `display_snippet`, `choices`, `field_name`, `preset`, ...);
setting `values.preset` bases the new preset on another registered one.


## CLI

- `ckan scheming-dynamic validation-schema --type dataset|group|organization` — print the JSON Schema that validates a ckanext-scheming schema definition
- `ckan scheming-dynamic validate --type dataset schema.yaml [more.json ...]` — validate schema definition file(s) against that JSON Schema
- `ckan scheming-dynamic sync --type dataset SCHEMA_TYPE` — bootstrap a dynamic schema from its static (file-defined) definition: creates it and locks version 1 if none exists yet, or locks a new version if the static definition changed since the last locked version (reports and does nothing if unchanged). Run this once when turning on scheming_dynamic on a portal that already has entities of `SCHEMA_TYPE`; existing entities are left unpinned.
- `ckan scheming-dynamic pin --type dataset SCHEMA_TYPE [-v VERSION] [--no-validate] [--dry-run]` — pin every not-yet-pinned entity of `SCHEMA_TYPE` to a locked schema version (default: current HEAD). Each entity's data is validated against that version first; entities that fail are reported and left unpinned rather than failing the whole command. `--no-validate` pins everything unconditionally, skipping that check. `--dry-run` reports what would be pinned/would fail without writing any pins.

## Admin UI

Sysadmins get a **Scheming** tab under `/ckan-admin/` (mounted at
`/ckan-admin/scheming/`), with **Schemas** and **Presets** sub-tabs listing
the dynamic dataset schemas and field presets and allowing creating, editing
and deleting them. Create/update/delete go through the `scheming_schema_*`/
`scheming_preset_*` actions, so the same validation applies and
`ValidationError`s are shown in the form.

The definition is edited either as raw JSON in a textarea or through a form
generated from the JSON Schema by [JSON Editor](https://github.com/json-editor/json-editor).
The generated form supports adding/removing dataset and resource fields,
reordering them with move up/down buttons and picking `preset` values from
the registered presets (built-in, file-registered, and database). A
**Preview form** button on the schema form renders the current (unsaved)
definition with the same form snippets the real dataset/resource forms use.

## Known limitations

- Only dataset schemas are merged at runtime; `group`/`organization` rows
  can be stored but are not yet picked up by ckanext-scheming.
- Changing a schema does not reindex existing datasets; run
  `ckan search-index rebuild` after incompatible changes.
- Version locking only covers the schema `definition` itself, not the
  presets it references. `SchemingPreset` rows are live/unversioned and
  shared globally, so editing a preset changes what every schema version
  using it resolves to, including versions already locked/pinned. A real
  fix needs preset versioning (or expanding+freezing preset values into the
  schema snapshot at lock time, at the cost of the raw/editable definition).
