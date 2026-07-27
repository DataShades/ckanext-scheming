import pytest

from ckanext.scheming_dynamic import schema_sync


@pytest.fixture
def clean_db(reset_db, migrate_db_for):
    reset_db()
    migrate_db_for("scheming_dynamic")


@pytest.fixture(autouse=True)
def reset_schema_sync():
    # the fingerprint is module state and would survive a clean_db
    schema_sync.reset()
