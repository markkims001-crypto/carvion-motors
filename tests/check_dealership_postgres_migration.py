"""Exercise dealership Alembic revision on a disposable PostgreSQL database."""
import importlib.util
import os
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

engine = sa.create_engine(os.environ["TEST_DATABASE_URL"])
path = Path("migrations/versions/d41e20261109_add_dealership_profiles.py")
spec = importlib.util.spec_from_file_location("dealership_revision", path)
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)

with engine.begin() as connection:
    connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    ctx = MigrationContext.configure(connection)
    operations = Operations(ctx)
    original_op = revision.op
    revision.op = operations
    try:
        revision.upgrade()
        inspector = sa.inspect(connection)
        assert "dealerships" in inspector.get_table_names()
        cols = {c["name"] for c in inspector.get_columns("dealerships")}
        assert {"owner_id", "slug", "is_verified", "created_at"} <= cols
        revision.upgrade()  # safe when Flask db.create_all created the table already
        revision.downgrade()
        assert "dealerships" not in sa.inspect(connection).get_table_names()
    finally:
        revision.op = original_op
print("PostgreSQL dealership migration upgrade, repeat, and downgrade passed")
