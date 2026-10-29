from alembic import op
import sqlalchemy as sa


revision = "20261001_0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    timestamps = (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=True),
            *timestamps,
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "documents" not in tables:
        op.create_table(
            "documents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=True),
            sa.Column("filename", sa.String(length=512), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("file_type", sa.String(length=10), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            *timestamps,
            sa.CheckConstraint("file_size > 0", name="ck_documents_file_size"),
            sa.CheckConstraint("file_type IN ('pdf', 'docx')", name="ck_documents_file_type"),
            sa.CheckConstraint("status IN ('processing', 'indexed', 'failed')", name="ck_documents_status"),
            sa.CheckConstraint("version > 0", name="ck_documents_version"),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("hash", name="uq_documents_hash"),
        )
        op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
        op.create_index("ix_documents_status", "documents", ["status"])

    if "chunks" not in tables:
        op.create_table(
            "chunks",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("document_id", sa.Uuid(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("embedding_id", sa.String(length=256), nullable=True),
            sa.Column("page", sa.Integer(), nullable=True),
            sa.Column("section", sa.String(length=512), nullable=True),
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            *timestamps,
            sa.CheckConstraint("chunk_index >= 0", name="ck_chunks_index"),
            sa.CheckConstraint("length(trim(text)) > 0", name="ck_chunks_text_not_empty"),
            sa.CheckConstraint("page IS NULL OR page >= 1", name="ck_chunks_page"),
            sa.CheckConstraint("token_count >= 0", name="ck_chunks_token_count"),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        )
        op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
        op.create_index("ix_chunks_content_hash", "chunks", ["content_hash"])
        op.create_index("ix_chunks_document_page", "chunks", ["document_id", "page"])

    if "conversations" not in tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=True),
            sa.Column("title", sa.String(length=512), nullable=True),
            *timestamps,
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    if "messages" not in tables:
        op.create_table(
            "messages",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("conversation_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            *timestamps,
            sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    if "citations" not in tables:
        op.create_table(
            "citations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("message_id", sa.Uuid(), nullable=False),
            sa.Column("chunk_id", sa.Uuid(), nullable=False),
            sa.Column("quoted_text", sa.Text(), nullable=True),
            *timestamps,
            sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("message_id", "chunk_id", name="uq_citations_message_chunk"),
        )
        op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"])

    if "feedback" not in tables:
        op.create_table(
            "feedback",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("message_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            *timestamps,
            sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
            sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("message_id", "user_id", name="uq_feedback_message_user"),
        )
        op.create_index("ix_feedback_message_id", "feedback", ["message_id"])
        op.create_index("ix_feedback_user_id", "feedback", ["user_id"])


def downgrade() -> None:
    # This baseline can adopt pre-existing tables, so dropping them would risk user data.
    pass