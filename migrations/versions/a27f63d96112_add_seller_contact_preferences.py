
"""Add seller contact preferences

Revision ID: a27f63d96112
Revises: 00cfddfc8924
"""

from alembic import op
import sqlalchemy as sa

revision = "a27f63d96112"
down_revision = "00cfddfc8924"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "allow_phone_contact",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "allow_whatsapp_contact",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade():
    op.drop_column("users", "allow_whatsapp_contact")
    op.drop_column("users", "allow_phone_contact")
