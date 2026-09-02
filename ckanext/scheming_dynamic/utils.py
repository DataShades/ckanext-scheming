from __future__ import annotations

from ckan import model

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


def remove_pin(entity_type: str, entity_id: str) -> None:
    """Drop an entity's schema pin.

    The counterpart to ``ensure_pinned``, called from the entity-delete
    hook so a pin never outlives the entity it belongs to. Runs inside the
    delete action's transaction -- no commit of its own. A no-op when the
    entity was never pinned."""
    model.Session.query(SchemingSchemaPin).filter(
        SchemingSchemaPin.entity_type == entity_type,
        SchemingSchemaPin.entity_id == entity_id,
    ).delete()
