# scheming_dynamic

Store ckanext-scheming dataset schemas in the database and edit them without
a server restart.

## How it works

- Schemas live in the `scheming_schema` table (`entity_type` + `schema_type`
  primary key, JSONB `definition`). `schema_type` is a unique entity type (e.g. `dataset_type`)
  and must match the `dataset_type` field inside the definition.
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
