"""add identity and support cases

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_role = postgresql.ENUM(
        "REPORTER", "SUPPORT", "APPROVER", "ADMIN", name="user_role", create_type=False
    )
    case_status = postgresql.ENUM(
        "OPEN", "DIAGNOSING", "WAITING_USER", "ESCALATED", name="support_case_status", create_type=False
    )
    user_role.create(op.get_bind(), checkfirst=True)
    case_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_users_organization_id"),
        sa.UniqueConstraint("subject", name="uq_users_subject"),
    )
    op.create_table(
        "user_target_scopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_system_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "user_id"], ["users.organization_id", "users.id"], name="fk_user_target_scopes_scope_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "target_system_id"], ["target_systems.organization_id", "target_systems.id"], name="fk_user_target_scopes_scope_target", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_system_id", name="uq_user_target_scopes_user_target"),
    )
    op.create_table(
        "target_resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("target_system_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "target_system_id"], ["target_systems.organization_id", "target_systems.id"], name="fk_target_resources_scope_target", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "target_system_id", "id", name="uq_target_resources_scope_id"),
        sa.UniqueConstraint("organization_id", "target_system_id", "resource_type", "external_id", name="uq_target_resources_external"),
    )
    op.create_table(
        "user_resource_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("target_system_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "user_id"], ["users.organization_id", "users.id"], name="fk_user_resource_grants_scope_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "target_system_id", "resource_id"], ["target_resources.organization_id", "target_resources.target_system_id", "target_resources.id"], name="fk_user_resource_grants_scope_resource", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "resource_id", name="uq_user_resource_grants_user_resource"),
    )
    op.create_table(
        "support_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("target_system_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_user_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("symptom_code", sa.String(100), nullable=True),
        sa.Column("status", case_status, nullable=False),
        sa.Column("deduplication_key", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "target_system_id"], ["target_systems.organization_id", "target_systems.id"], name="fk_support_cases_scope_target", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "reporter_user_id"], ["users.organization_id", "users.id"], name="fk_support_cases_scope_reporter", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "target_system_id", "resource_id"], ["target_resources.organization_id", "target_resources.target_system_id", "target_resources.id"], name="fk_support_cases_scope_resource", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_support_cases_organization_id"),
        sa.UniqueConstraint("organization_id", "deduplication_key", name="uq_support_cases_deduplication"),
    )
    op.create_index("ix_support_cases_scope_status", "support_cases", ["organization_id", "target_system_id", "status"])
    op.create_table(
        "case_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("support_case_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "support_case_id"], ["support_cases.organization_id", "support_cases.id"], name="fk_case_messages_scope_case", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "author_user_id"], ["users.organization_id", "users.id"], name="fk_case_messages_scope_author", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "support_case_id", "id", name="uq_case_messages_scope_id"),
    )
    op.execute(
        """
        CREATE TRIGGER trg_case_messages_append_only
        BEFORE UPDATE OR DELETE ON case_messages
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_case_messages_append_only ON case_messages")
    op.drop_table("case_messages")
    op.drop_index("ix_support_cases_scope_status", table_name="support_cases")
    op.drop_table("support_cases")
    op.drop_table("user_resource_grants")
    op.drop_table("target_resources")
    op.drop_table("user_target_scopes")
    op.drop_table("users")
    postgresql.ENUM(name="support_case_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
