from pathlib import Path

from sqlalchemy import DateTime, Integer, String, Text, create_engine, inspect

from app.database import create_schema
from app.config import settings


def test_fresh_migrations_create_required_schema(monkeypatch, tmp_path: Path) -> None:
    database_file = tmp_path / "fresh-schema.db"
    database_url = f"sqlite+pysqlite:///{database_file.as_posix()}"
    monkeypatch.setattr(settings, "database_url", database_url)
    create_schema()
    create_schema()
    engine = create_engine(database_url)
    schema = inspect(engine)
    expected_tables = {
        "users", "documents", "chunks", "conversations", "messages", "citations", "feedback"
    }
    assert expected_tables <= set(schema.get_table_names())

    expected_foreign_keys = {
        "documents": {("owner_id", "users", "SET NULL")},
        "chunks": {("document_id", "documents", "CASCADE")},
        "conversations": {("user_id", "users", "SET NULL"), ("document_id", "documents", "SET NULL")},
        "messages": {("conversation_id", "conversations", "CASCADE")},
        "citations": {("message_id", "messages", "CASCADE"), ("chunk_id", "chunks", "CASCADE")},
        "feedback": {("message_id", "messages", "CASCADE"), ("user_id", "users", "SET NULL")},
    }
    for table in expected_tables:
        assert schema.get_pk_constraint(table)["constrained_columns"] == ["id"]
        columns = {column["name"]: column for column in schema.get_columns(table)}
        assert {"created_at", "updated_at"} <= columns.keys()
        assert columns["id"]["type"].python_type is not None
        actual_foreign_keys = {
            (column, foreign_key["referred_table"])
            for foreign_key in schema.get_foreign_keys(table)
            for column in foreign_key["constrained_columns"]
        }
        expected_pairs = {(column, referred_table) for column, referred_table, _ in expected_foreign_keys.get(table, set())}
        assert expected_pairs <= actual_foreign_keys
        for foreign_key in schema.get_foreign_keys(table):
            for column in foreign_key["constrained_columns"]:
                expected_ondelete = next(
                    ondelete
                    for expected_column, referred_table, ondelete in expected_foreign_keys.get(table, set())
                    if expected_column == column and referred_table == foreign_key["referred_table"]
                )
                assert foreign_key["options"].get("ondelete") == expected_ondelete

    document_columns = {column["name"] for column in schema.get_columns("documents")}
    assert {"owner_id", "filename", "version", "status", "hash", "created_at"} <= document_columns
    document_types = {column["name"]: column["type"] for column in schema.get_columns("documents")}
    assert isinstance(document_types["filename"], String)
    assert isinstance(document_types["version"], Integer)
    assert isinstance(document_types["hash"], String)
    assert isinstance(document_types["created_at"], DateTime)
    chunk_columns = {column["name"] for column in schema.get_columns("chunks")}
    assert {
        "id", "document_id", "text", "page", "section", "embedding_id", "token_count", "created_at"
    } <= chunk_columns
    chunk_types = {column["name"]: column["type"] for column in schema.get_columns("chunks")}
    assert isinstance(chunk_types["text"], Text)
    assert isinstance(chunk_types["page"], Integer)
    assert isinstance(chunk_types["token_count"], Integer)
    assert isinstance(chunk_types["embedding_id"], String)
    assert any(
        constraint.get("column_names") == ["hash"]
        for constraint in schema.get_unique_constraints("documents")
    )
    assert any(
        constraint.get("column_names") == ["document_id", "chunk_index"]
        for constraint in schema.get_unique_constraints("chunks")
    )
    assert "ck_chunks_text_not_empty" in {
        constraint["name"] for constraint in schema.get_check_constraints("chunks")
    }
    for table in expected_tables:
        assert schema.get_indexes(table)

    engine.dispose()