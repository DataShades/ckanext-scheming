# scheming_dynamic

Store ckanext-scheming dataset schemas in the database and edit them without
a server restart.

## How it works

- Schemas live in the `scheming_schema` table (`entity_type` + `schema_type`
  primary key, JSONB `definition`). `schema_type` is a unique entity type (e.g. `dataset_type`)
  and must match the `dataset_type` field inside the definition.
- Before ckanext-scheming returns any dataset schema it asks this extension
  whether the table changed since the last merge (a cheap
  `count(*) + max(updated)` scan, at most once per request). When it did,
  all dataset schemas are rebuilt: the file-defined schemas from
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

- `scheming_schema_create(schema_type, definition, entity_type="dataset")`
- `scheming_schema_update(schema_type, definition, entity_type="dataset")`
- `scheming_schema_delete(schema_type, entity_type="dataset")`

Definitions are validated against a JSON Schema mirroring the minimal shape
of a ckanext-scheming schema file; `preset` values are checked against the
presets registered at startup.

## Known limitations

- Only dataset schemas are merged at runtime; `group`/`organization` rows
  can be stored but are not yet picked up by ckanext-scheming.
- Form pages (`start_form_page`) work for types known at startup only: the
  paged create/edit routes are registered per type when the app boots.
- Changing a schema does not reindex existing datasets; run
  `ckan search-index rebuild` after incompatible changes.
- Custom presets must be registered at startup via `scheming.presets`;
  definitions referencing unregistered presets are rejected.
