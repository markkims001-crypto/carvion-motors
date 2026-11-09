"""Add seller-owned dealership profiles.

Revision ID: d41e20261109
Revises: a27f63d96112
"""
from alembic import op
import sqlalchemy as sa

revision = "d41e20261109"
down_revision = "a27f63d96112"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "dealerships" not in inspector.get_table_names():
        op.create_table(
            "dealerships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=150), nullable=False, unique=True),
            sa.Column("location", sa.String(length=160), nullable=False),
            sa.Column("phone", sa.String(length=20), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("logo_url", sa.String(length=500), nullable=True),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("dealerships")}
    if "ix_dealerships_owner_id" not in indexes:
        op.create_index("ix_dealerships_owner_id", "dealerships", ["owner_id"])
    if "ix_dealerships_slug" not in indexes:
        op.create_index("ix_dealerships_slug", "dealerships", ["slug"])


def downgrade():
    op.drop_table("dealerships")
