"""Support section-specific blocked periods and persisted link groups.

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table keeps this migration usable with SQLite, which cannot
    # add a foreign key constraint through ALTER TABLE.
    with op.batch_alter_table("reserved_slots") as batch_op:
        batch_op.add_column(sa.Column("section_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_reserved_slots_section", "sections", ["section_id"], ["id"])
        batch_op.create_index("ix_reserved_slots_section_id", ["section_id"])
    op.add_column("courses", sa.Column("link_group", sa.String(length=50), nullable=True))
    op.add_column("courses", sa.Column("batch_label", sa.String(length=50), nullable=True))
    op.create_index("ix_courses_link_group", "courses", ["link_group"])


def downgrade() -> None:
    op.drop_index("ix_courses_link_group", table_name="courses")
    op.drop_column("courses", "batch_label")
    op.drop_column("courses", "link_group")
    with op.batch_alter_table("reserved_slots") as batch_op:
        batch_op.drop_index("ix_reserved_slots_section_id")
        batch_op.drop_constraint("fk_reserved_slots_section", type_="foreignkey")
        batch_op.drop_column("section_id")
