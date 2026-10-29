from alembic import op
import sqlalchemy as sa


revision = "20261002_0001"
down_revision = "20261001_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    document_columns = {column["name"] for column in sa.inspect(bind).get_columns("documents")}
    if "hash" not in document_columns:
        if "sha256" in document_columns:
            op.alter_column("documents", "sha256", new_column_name="hash")
        else:
            op.add_column("documents", sa.Column("hash", sa.String(length=64), nullable=True))
    document_columns = {column["name"] for column in sa.inspect(bind).get_columns("documents")}
    if "owner_id" not in document_columns:
        _add_uuid_fk_column(
            "documents", "owner_id", "fk_documents_owner_id_users", "users", "SET NULL"
        )
        op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    if "version" not in document_columns:
        op.add_column("documents", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    _ensure_check_constraint("documents", "ck_documents_version", "version > 0")
    document_indexes = sa.inspect(bind).get_indexes("documents")
    unique_hash_index = any(index.get("unique") and index.get("column_names") == ["hash"] for index in document_indexes)
    unique_hash_constraint = any(
        constraint.get("column_names") == ["hash"]
        for constraint in sa.inspect(bind).get_unique_constraints("documents")
    )
    if not unique_hash_index and not unique_hash_constraint:
        op.create_index("ix_documents_hash", "documents", ["hash"], unique=True)

    chunk_columns = {column["name"] for column in sa.inspect(bind).get_columns("chunks")}
    if "embedding_id" not in chunk_columns:
        op.add_column("chunks", sa.Column("embedding_id", sa.String(length=256), nullable=True))
    _ensure_check_constraint("chunks", "ck_chunks_text_not_empty", "length(trim(text)) > 0")

    if "document_id" not in {column["name"] for column in sa.inspect(bind).get_columns("conversations")}:
        _add_uuid_fk_column(
            "conversations",
            "document_id",
            "fk_conversations_document_id_documents",
            "documents",
            "SET NULL",
        )
        op.create_index("ix_conversations_document_id", "conversations", ["document_id"])

    if "latency_ms" not in {column["name"] for column in sa.inspect(bind).get_columns("messages")}:
        op.add_column("messages", sa.Column("latency_ms", sa.Integer(), nullable=True))
    _ensure_check_constraint("messages", "ck_messages_latency", "latency_ms IS NULL OR latency_ms >= 0")

    if "relevance_score" not in {column["name"] for column in sa.inspect(bind).get_columns("citations")}:
        op.add_column(
            "citations",
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
        )
    _ensure_check_constraint("citations", "ck_citations_relevance_score", "relevance_score BETWEEN 0 AND 1")


def downgrade() -> None:
    op.drop_column("citations", "relevance_score")
    op.drop_column("messages", "latency_ms")
    op.drop_index("ix_conversations_document_id", table_name="conversations")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("conversations", recreate="always") as batch:
            batch.drop_constraint("fk_conversations_document_id_documents", type_="foreignkey")
            batch.drop_column("document_id")
        with op.batch_alter_table("chunks", recreate="always") as batch:
            batch.drop_constraint("ck_chunks_text_not_empty", type_="check")
            batch.drop_column("embedding_id")
        with op.batch_alter_table("messages", recreate="always") as batch:
            batch.drop_constraint("ck_messages_latency", type_="check")
            batch.drop_column("latency_ms")
        with op.batch_alter_table("citations", recreate="always") as batch:
            batch.drop_constraint("ck_citations_relevance_score", type_="check")
            batch.drop_column("relevance_score")
        with op.batch_alter_table("documents", recreate="always") as batch:
            batch.drop_constraint("ck_documents_version", type_="check")
            batch.drop_constraint("fk_documents_owner_id_users", type_="foreignkey")
            batch.drop_column("owner_id")
            batch.drop_column("version")
            batch.alter_column("hash", new_column_name="sha256")
    else:
        op.drop_constraint("ck_citations_relevance_score", "citations", type_="check")
        op.drop_constraint("fk_conversations_document_id_documents", "conversations", type_="foreignkey")
        op.drop_column("conversations", "document_id")
        op.drop_constraint("ck_chunks_text_not_empty", "chunks", type_="check")
        op.drop_column("chunks", "embedding_id")
        op.drop_constraint("ck_messages_latency", "messages", type_="check")
        op.drop_column("messages", "latency_ms")
        op.drop_index("ix_documents_owner_id", table_name="documents")
        op.drop_constraint("ck_documents_version", "documents", type_="check")
        op.drop_constraint("fk_documents_owner_id_users", "documents", type_="foreignkey")
        op.drop_column("documents", "owner_id")
        op.drop_column("documents", "version")
        op.alter_column("documents", "hash", new_column_name="sha256")


def _add_uuid_fk_column(
    table: str, column: str, constraint: str, referred_table: str, ondelete: str
) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.add_column(sa.Column(column, sa.Uuid(), nullable=True))
            batch.create_foreign_key(
                constraint, referred_table, [column], ["id"], ondelete=ondelete
            )
    else:
        op.add_column(table, sa.Column(column, sa.Uuid(), nullable=True))
        op.create_foreign_key(
            constraint, table, referred_table, [column], ["id"], ondelete=ondelete
        )


def _ensure_check_constraint(table: str, name: str, expression: str) -> None:
    bind = op.get_bind()
    constraints = {constraint["name"] for constraint in sa.inspect(bind).get_check_constraints(table)}
    if name in constraints:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.create_check_constraint(name, expression)
    else:
        op.create_check_constraint(name, table, expression)