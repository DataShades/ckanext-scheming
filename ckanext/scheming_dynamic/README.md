# scheming_dynamic

Store ckanext-scheming dataset schemas in the database and edit them without
a server restart.

## How it works

- Schemas live in the `scheming_schema` table (`entity_type` + `schema_type`
  primary key, JSONB `definition`). `schema_type` is a unique entity type (e.g. `dataset_type`)
  and must match the `dataset_type` field inside the definition.
- Before ckanext-scheming returns any dataset schema it asks this extension
  whether anything changed since the last merge — a cheap lookup of a single
  row in `scheming_schema_state` (one row per entity_type, a version counter
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
- `scheming_schema_delete(schema_type, entity_type="dataset")`

Definitions are validated against a JSON Schema mirroring the minimal shape


## Admin UI

Sysadmins get a **Scheming** tab under `/ckan-admin/` (mounted at
`/ckan-admin/scheming/`) that lists the dynamic dataset schemas and allows
creating, editing and deleting them. Create/update/delete go through the
`scheming_schema_*` actions, so the same validation applies and
`ValidationError`s are shown in the form.

The definition is edited either as raw JSON in a textarea or through a form
generated from the JSON Schema by [react-jsonschema-form](https://github.com/rjsf-team/react-jsonschema-form).
The generated form supports adding/removing dataset and resource fields,
reordering them with move up/down buttons and picking `preset` values from
the registered presets. A **Preview form** button renders the
current (unsaved) definition with the same form snippets the real
dataset/resource forms use.

## Known limitations

- Only dataset schemas are merged at runtime; `group`/`organization` rows
  can be stored but are not yet picked up by ckanext-scheming.
- Changing a schema does not reindex existing datasets; run
  `ckan search-index rebuild` after incompatible changes.
- Custom presets must be registered at startup via `scheming.presets`;
  definitions referencing unregistered presets are rejected.
