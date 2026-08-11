import pytest

from ckanext.scheming.plugins import _SchemingMixin
from ckanext.scheming_dynamic import schema_sync
from ckanext.scheming_dynamic.tests.helpers import SCHEMA_DEFINITION


@pytest.fixture
def clean_db(reset_db, migrate_db_for):
    reset_db()
    migrate_db_for("scheming_dynamic")


@pytest.fixture(autouse=True)
def reset_schema_sync():
    # the fingerprint is module state and would survive a clean_db
    schema_sync.reset()


@pytest.fixture
def schema_definition() -> dict:
    return {**SCHEMA_DEFINITION}


@pytest.fixture
def reload_scheming_presets():
    """Force _SchemingMixin to reload presets from the current config."""
    _SchemingMixin._presets = None
    yield
    _SchemingMixin._presets = None
