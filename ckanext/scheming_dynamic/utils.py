from __future__ import annotations

from ckanext.scheming_dynamic.model import SchemingSchemaPin, SchemingSchemaVersion


def ensure_pinned(entity_type: str, entity_id: str, schema_type: str) -> None:
    """Pin an entity to the schema's current head version.

    Called once, at entity-creation time. A no-op when ``schema_type`` has
    no dynamic (database) schema at all -- e.g. a file-defined-only type.
    """
    if SchemingSchemaPin.get(entity_type, entity_id):
        return

    head_version = SchemingSchemaVersion.head_version(entity_type, schema_type)
    if head_version == 0:
        return

    SchemingSchemaPin.pin(entity_type, entity_id, schema_type, head_version)
