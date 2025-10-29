from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


class DocumentRecord(Base):
    """Metadata describing an ingested knowledge base document."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    original_name = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_hash = Column(String, nullable=False, unique=True)
    mime_type = Column(String, nullable=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    summary = Column(Text, nullable=True)


class ToolRecord(Base):
    """Registered MCP tool configuration."""

    __tablename__ = "tools"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    tool_type = Column(String, nullable=False)
    config = Column(Text, nullable=False)  # JSON string
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ToolExecutionLog(Base):
    """Audit log for tool executions initiated via the platform."""

    __tablename__ = "tool_execution_logs"

    id = Column(String, primary_key=True)
    tool_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(Text, nullable=True)  # JSON string
    result_preview = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def init_engine(sqlite_path: Path) -> sessionmaker[Session]:
    """Initialise the SQLite engine and return a session factory."""
    global _engine, _SessionLocal

    if _engine is None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{sqlite_path}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(
            bind=_engine,
            future=True,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    if _SessionLocal is None:
        raise RuntimeError("Session factory initialisation failed.")

    return _SessionLocal


def get_session_factory() -> sessionmaker[Session]:
    """Return the cached session factory, ensuring init_engine was called."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised. Call init_engine() first.")
    return _SessionLocal


def get_document_by_hash(session: Session, content_hash: str) -> DocumentRecord | None:
    """Return an existing document by its content hash if it exists."""
    statement = select(DocumentRecord).where(DocumentRecord.content_hash == content_hash)
    return session.execute(statement).scalar_one_or_none()


def get_document_by_id(session: Session, document_id: str) -> DocumentRecord | None:
    """Return an existing document by id if it exists."""
    statement = select(DocumentRecord).where(DocumentRecord.id == document_id)
    return session.execute(statement).scalar_one_or_none()


def iter_documents(session: Session) -> Generator[DocumentRecord, None, None]:
    """Yield documents ordered by creation date descending."""
    statement = (
        select(DocumentRecord).order_by(DocumentRecord.created_at.desc()).execution_options(stream_results=True)
    )
    for row in session.execute(statement):
        yield row[0]


def get_tool_by_id(session: Session, tool_id: str) -> ToolRecord | None:
    """Return a tool configuration by its identifier."""
    statement = select(ToolRecord).where(ToolRecord.id == tool_id)
    return session.execute(statement).scalar_one_or_none()


def list_tools(session: Session, include_inactive: bool = False) -> list[ToolRecord]:
    """List registered tools, optionally filtering inactive ones."""
    statement = select(ToolRecord).order_by(ToolRecord.created_at.desc())
    if not include_inactive:
        statement = statement.where(ToolRecord.is_active.is_(True))
    return list(session.execute(statement).scalars())


def list_tool_logs(session: Session, limit: int = 50) -> list[ToolExecutionLog]:
    """Return recent tool execution logs."""
    statement = (
        select(ToolExecutionLog)
        .order_by(ToolExecutionLog.created_at.desc())
        .limit(limit)
    )
    return list(session.execute(statement).scalars())
