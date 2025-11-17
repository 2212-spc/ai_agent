from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    func,
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


class AgentConfig(Base):
    """Custom Agent configuration saved by users."""

    __tablename__ = "agent_configs"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    config = Column(Text, nullable=False)  # JSON string: nodes, edges, settings
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ConversationHistory(Base):
    """对话历史记录 - 存储用户与AI的完整对话"""

    __tablename__ = "conversation_history"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)  # 可选的用户ID，用于多用户场景
    session_id = Column(String, nullable=False)  # 会话ID，用于区分不同对话会话
    role = Column(String, nullable=False)  # "user" 或 "assistant"
    content = Column(Text, nullable=False)  # 消息内容
    extra_metadata = Column(Text, nullable=True)  # JSON string，存储额外信息（如工具调用、检索结果等）
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LongTermMemory(Base):
    """长期记忆 - 存储提取的重要信息、用户偏好、关键事实等"""

    __tablename__ = "long_term_memory"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)  # 可选的用户ID
    memory_type = Column(String, nullable=False)  # "fact", "preference", "event", "relationship" 等
    content = Column(Text, nullable=False)  # 记忆内容
    importance_score = Column(Integer, nullable=False, default=50)  # 重要性评分 0-100
    source_conversation_id = Column(String, nullable=True)  # 来源对话ID
    extra_metadata = Column(Text, nullable=True)  # JSON string，存储额外信息
    access_count = Column(Integer, nullable=False, default=0)  # 访问次数
    last_accessed_at = Column(DateTime, nullable=True)  # 最后访问时间
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SessionConfig(Base):
    """会话配置 - 控制记忆共享等设置"""

    __tablename__ = "session_config"

    session_id = Column(String, primary_key=True)  # 会话ID
    user_id = Column(String, nullable=True)  # 用户ID
    share_memory_across_sessions = Column(Boolean, nullable=False, default=True)  # 是否跨会话共享记忆
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PromptTemplate(Base):
    """Prompt模板 - 存储智能体的prompt模板"""
    
    __tablename__ = "prompt_templates"
    
    id = Column(String, primary_key=True)  # 模板ID
    name = Column(String, nullable=False)  # 模板名称
    agent_id = Column(String, nullable=False)  # 关联的智能体ID (如: analysis_specialist)
    content = Column(Text, nullable=False)  # Prompt内容
    description = Column(Text, nullable=True)  # 模板描述
    is_default = Column(Boolean, nullable=False, default=False)  # 是否为默认模板（系统预设，不推荐修改）
    is_active = Column(Boolean, nullable=False, default=True)  # 是否激活（当前是否被使用）
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(Base):
    """用户表 - 存储用户账号信息"""
    
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)  # 加密后的密码
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


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


def get_agent_config_by_id(session: Session, agent_id: str) -> AgentConfig | None:
    """Return an agent configuration by its identifier."""
    statement = select(AgentConfig).where(AgentConfig.id == agent_id)
    return session.execute(statement).scalar_one_or_none()


def list_agent_configs(session: Session, include_inactive: bool = False) -> list[AgentConfig]:
    """List all agent configurations."""
    statement = select(AgentConfig).order_by(AgentConfig.created_at.desc())
    if not include_inactive:
        statement = statement.where(AgentConfig.is_active.is_(True))
    return list(session.execute(statement).scalars())


def save_conversation_message(
    session: Session,
    session_id: str,
    role: str,
    content: str,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> ConversationHistory:
    """保存对话消息到历史记录"""
    msg_id = str(uuid.uuid4())
    record = ConversationHistory(
        id=msg_id,
        user_id=user_id,
        session_id=session_id,
        role=role,
        content=content,
        extra_metadata=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_conversation_history(
    session: Session,
    session_id: str,
    limit: int = 20,
    user_id: Optional[str] = None,
) -> list[ConversationHistory]:
    """获取指定会话的对话历史"""
    statement = (
        select(ConversationHistory)
        .where(ConversationHistory.session_id == session_id)
        .order_by(ConversationHistory.created_at.asc())
    )
    if user_id:
        statement = statement.where(ConversationHistory.user_id == user_id)
    
    if limit > 0:
        # 获取最新的 limit 条记录
        count_statement = select(func.count()).select_from(
            select(ConversationHistory)
            .where(ConversationHistory.session_id == session_id)
            .subquery()
        )
        total = session.execute(count_statement).scalar() or 0
        if total > limit:
            offset = total - limit
            statement = statement.offset(offset)
    
    return list(session.execute(statement).scalars())


def save_long_term_memory(
    session: Session,
    memory_type: str,
    content: str,
    importance_score: int = 50,
    user_id: Optional[str] = None,
    source_conversation_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> LongTermMemory:
    """保存长期记忆"""
    memory_id = str(uuid.uuid4())
    record = LongTermMemory(
        id=memory_id,
        user_id=user_id,
        memory_type=memory_type,
        content=content,
        importance_score=max(0, min(100, importance_score)),
        source_conversation_id=source_conversation_id,
        extra_metadata=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def search_long_term_memory(
    session: Session,
    query: str,
    user_id: Optional[str] = None,
    memory_types: Optional[list[str]] = None,
    limit: int = 10,
    min_importance: int = 0,
) -> list[LongTermMemory]:
    """搜索长期记忆（基于关键词匹配）"""
    statement = select(LongTermMemory).where(
        LongTermMemory.content.like(f"%{query}%")
    )
    
    if user_id:
        statement = statement.where(LongTermMemory.user_id == user_id)
    
    if memory_types:
        statement = statement.where(LongTermMemory.memory_type.in_(memory_types))
    
    statement = statement.where(
        LongTermMemory.importance_score >= min_importance
    ).order_by(
        LongTermMemory.importance_score.desc(),
        LongTermMemory.last_accessed_at.desc().nullslast(),
        LongTermMemory.created_at.desc()
    ).limit(limit)
    
    return list(session.execute(statement).scalars())


def get_recent_memories(
    session: Session,
    user_id: Optional[str] = None,
    limit: int = 20,
) -> list[LongTermMemory]:
    """获取最近的记忆（按访问时间和重要性）"""
    statement = select(LongTermMemory).order_by(
        LongTermMemory.last_accessed_at.desc().nullslast(),
        LongTermMemory.importance_score.desc(),
        LongTermMemory.created_at.desc()
    ).limit(limit)
    
    if user_id:
        statement = statement.where(LongTermMemory.user_id == user_id)
    
    return list(session.execute(statement).scalars())


def update_memory_access(
    session: Session,
    memory_id: str,
) -> Optional[LongTermMemory]:
    """更新记忆的访问信息"""
    memory = session.get(LongTermMemory, memory_id)
    if memory:
        memory.access_count += 1
        memory.last_accessed_at = datetime.utcnow()
        session.commit()
        session.refresh(memory)
    return memory


def get_similar_memories(
    session: Session,
    memory_type: str,
    content: str,
    user_id: Optional[str] = None,
    limit: int = 10,
) -> list[LongTermMemory]:
    """
    获取相似类型的记忆，用于去重检查
    返回同一类型、同一用户的记忆列表
    """
    statement = select(LongTermMemory).where(
        LongTermMemory.memory_type == memory_type
    )
    
    if user_id:
        statement = statement.where(LongTermMemory.user_id == user_id)
    
    statement = statement.order_by(
        LongTermMemory.importance_score.desc(),
        LongTermMemory.created_at.desc()
    ).limit(limit)
    
    return list(session.execute(statement).scalars())


def update_memory_content(
    session: Session,
    memory_id: str,
    new_content: str,
    new_importance_score: Optional[int] = None,
    new_metadata: Optional[dict] = None,
) -> Optional[LongTermMemory]:
    """
    更新记忆的内容、重要性评分和元数据
    用于合并相似记忆
    """
    memory = session.get(LongTermMemory, memory_id)
    if not memory:
        return None
    
    memory.content = new_content
    if new_importance_score is not None:
        memory.importance_score = max(0, min(100, new_importance_score))
    
    # 合并元数据
    if new_metadata:
        existing_metadata = {}
        if memory.extra_metadata:
            try:
                existing_metadata = json.loads(memory.extra_metadata)
            except:
                pass
        
        # 合并元数据
        existing_metadata.update(new_metadata)
        # 添加合并记录
        if "merged_from" not in existing_metadata:
            existing_metadata["merged_from"] = []
        if isinstance(new_metadata.get("source_ids"), list):
            existing_metadata["merged_from"].extend(new_metadata["source_ids"])
        
        memory.extra_metadata = json.dumps(existing_metadata, ensure_ascii=False)
    
    memory.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(memory)
    return memory


def merge_memories(
    session: Session,
    target_memory_id: str,
    source_memory_id: str,
) -> Optional[LongTermMemory]:
    """
    合并两个记忆
    将 source_memory 的信息合并到 target_memory，然后删除 source_memory
    
    Returns:
        合并后的目标记忆
    """
    target = session.get(LongTermMemory, target_memory_id)
    source = session.get(LongTermMemory, source_memory_id)
    
    if not target or not source:
        return None
    
    # 合并访问统计
    target.access_count += source.access_count
    
    # 更新最后访问时间为最近的
    if source.last_accessed_at:
        if not target.last_accessed_at or source.last_accessed_at > target.last_accessed_at:
            target.last_accessed_at = source.last_accessed_at
    
    # 更新重要性评分为更高的
    if source.importance_score > target.importance_score:
        target.importance_score = source.importance_score
    
    # 合并元数据
    target_metadata = {}
    if target.extra_metadata:
        try:
            target_metadata = json.loads(target.extra_metadata)
        except:
            pass
    
    source_metadata = {}
    if source.extra_metadata:
        try:
            source_metadata = json.loads(source.extra_metadata)
        except:
            pass
    
    # 记录合并历史
    if "merged_from" not in target_metadata:
        target_metadata["merged_from"] = []
    target_metadata["merged_from"].append(source.id)
    target_metadata["merged_at"] = datetime.utcnow().isoformat()
    
    # 保留两个记忆的元数据信息
    if source_metadata:
        target_metadata["source_metadata"] = source_metadata
    
    target.extra_metadata = json.dumps(target_metadata, ensure_ascii=False)
    target.updated_at = datetime.utcnow()
    
    # 删除源记忆
    session.delete(source)
    session.commit()
    session.refresh(target)
    
    return target


def get_session_config(
    session: Session,
    session_id: str,
) -> Optional[SessionConfig]:
    """获取会话配置"""
    return session.get(SessionConfig, session_id)


def create_or_update_session_config(
    session: Session,
    session_id: str,
    share_memory_across_sessions: bool = True,
    user_id: Optional[str] = None,
) -> SessionConfig:
    """创建或更新会话配置"""
    config = session.get(SessionConfig, session_id)
    if not config:
        config = SessionConfig(
            session_id=session_id,
            user_id=user_id,
            share_memory_across_sessions=share_memory_across_sessions,
        )
        session.add(config)
    else:
        config.share_memory_across_sessions = share_memory_across_sessions
        if user_id:
            config.user_id = user_id
        config.updated_at = datetime.utcnow()
    
    session.commit()
    session.refresh(config)
    return config


def list_conversation_sessions(
    session: Session,
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    列出所有会话列表（按最后更新时间排序）
    返回每个会话的摘要信息
    """
    from sqlalchemy import func, distinct
    
    # 查询所有唯一的 session_id
    statement = (
        select(
            ConversationHistory.session_id,
            func.max(ConversationHistory.created_at).label("last_message_time"),
            func.count(ConversationHistory.id).label("message_count"),
            func.min(ConversationHistory.created_at).label("first_message_time"),
        )
        .group_by(ConversationHistory.session_id)
    )
    
    if user_id:
        statement = statement.where(ConversationHistory.user_id == user_id)
    
    # 按最后消息时间排序
    statement = statement.order_by(func.max(ConversationHistory.created_at).desc())
    
    # 分页
    statement = statement.offset(offset).limit(limit)
    
    results = session.execute(statement).all()
    
    # 获取每个会话的第一条和最后一条消息作为摘要
    sessions = []
    for row in results:
        session_id = row.session_id
        
        # 获取会话的第一条用户消息作为标题
        first_msg_statement = (
            select(ConversationHistory)
            .where(
                ConversationHistory.session_id == session_id,
                ConversationHistory.role == "user"
            )
            .order_by(ConversationHistory.created_at.asc())
            .limit(1)
        )
        first_msg = session.execute(first_msg_statement).scalar_one_or_none()
        
        # 获取最后一条消息
        last_msg_statement = (
            select(ConversationHistory)
            .where(ConversationHistory.session_id == session_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(1)
        )
        last_msg = session.execute(last_msg_statement).scalar_one_or_none()
        
        title = (first_msg.content[:50] + "...") if first_msg and len(first_msg.content) > 50 else (first_msg.content if first_msg else "新对话")
        preview = (last_msg.content[:100] + "...") if last_msg and len(last_msg.content) > 100 else (last_msg.content if last_msg else "")
        
        sessions.append({
            "session_id": session_id,
            "title": title,
            "message_count": row.message_count,
            "first_message_time": row.first_message_time.isoformat() if row.first_message_time else None,
            "last_message_time": row.last_message_time.isoformat() if row.last_message_time else None,
            "preview": preview,
        })
    
    return sessions


def search_conversation_sessions(
    session: Session,
    query: str,
    user_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    搜索会话（基于对话内容）
    """
    from sqlalchemy import distinct
    
    # 查找包含关键词的会话
    statement = (
        select(distinct(ConversationHistory.session_id))
        .where(ConversationHistory.content.like(f"%{query}%"))
    )
    
    if user_id:
        statement = statement.where(ConversationHistory.user_id == user_id)
    
    statement = statement.limit(limit)
    
    session_ids = [row[0] for row in session.execute(statement).all()]
    
    if not session_ids:
        return []
    
    # 获取这些会话的详细信息
    from sqlalchemy import func
    statement = (
        select(
            ConversationHistory.session_id,
            func.max(ConversationHistory.created_at).label("last_message_time"),
            func.count(ConversationHistory.id).label("message_count"),
            func.min(ConversationHistory.created_at).label("first_message_time"),
        )
        .where(ConversationHistory.session_id.in_(session_ids))
        .group_by(ConversationHistory.session_id)
        .order_by(func.max(ConversationHistory.created_at).desc())
    )
    
    results = session.execute(statement).all()
    
    sessions = []
    for row in results:
        session_id = row.session_id
        
        first_msg_statement = (
            select(ConversationHistory)
            .where(
                ConversationHistory.session_id == session_id,
                ConversationHistory.role == "user"
            )
            .order_by(ConversationHistory.created_at.asc())
            .limit(1)
        )
        first_msg = session.execute(first_msg_statement).scalar_one_or_none()
        
        last_msg_statement = (
            select(ConversationHistory)
            .where(ConversationHistory.session_id == session_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(1)
        )
        last_msg = session.execute(last_msg_statement).scalar_one_or_none()
        
        title = (first_msg.content[:50] + "...") if first_msg and len(first_msg.content) > 50 else (first_msg.content if first_msg else "新对话")
        preview = (last_msg.content[:100] + "...") if last_msg and len(last_msg.content) > 100 else (last_msg.content if last_msg else "")
        
        sessions.append({
            "session_id": session_id,
            "title": title,
            "message_count": row.message_count,
            "first_message_time": row.first_message_time.isoformat() if row.first_message_time else None,
            "last_message_time": row.last_message_time.isoformat() if row.last_message_time else None,
            "preview": preview,
        })
    
    return sessions


def delete_conversation_session(
    session: Session,
    session_id: str,
    user_id: Optional[str] = None,
) -> int:
    """
    删除整个会话的所有消息
    
    Returns:
        删除的消息数量
    """
    statement = select(ConversationHistory).where(
        ConversationHistory.session_id == session_id
    )
    
    if user_id:
        statement = statement.where(ConversationHistory.user_id == user_id)
    
    messages = list(session.execute(statement).scalars())
    
    count = len(messages)
    for msg in messages:
        session.delete(msg)
    
    # 同时删除会话配置
    config = session.get(SessionConfig, session_id)
    if config:
        session.delete(config)
    
    session.commit()
    return count


def delete_conversation_message(
    session: Session,
    message_id: str,
    user_id: Optional[str] = None,
) -> bool:
    """
    删除单条消息
    
    Returns:
        是否删除成功
    """
    message = session.get(ConversationHistory, message_id)
    if not message:
        return False
    
    if user_id and message.user_id != user_id:
        return False
    
    session.delete(message)
    session.commit()
    return True


# ==================== Prompt模板相关函数 ====================

def get_prompt_template_by_id(session: Session, template_id: str) -> PromptTemplate | None:
    """根据ID获取prompt模板"""
    return session.get(PromptTemplate, template_id)


def get_active_prompt_for_agent(session: Session, agent_id: str) -> PromptTemplate | None:
    """获取指定智能体当前激活的prompt模板"""
    statement = select(PromptTemplate).where(
        PromptTemplate.agent_id == agent_id,
        PromptTemplate.is_active.is_(True)
    ).order_by(PromptTemplate.created_at.desc()).limit(1)
    return session.execute(statement).scalar_one_or_none()


def list_prompt_templates(
    session: Session,
    agent_id: Optional[str] = None,
    include_inactive: bool = False,
) -> list[PromptTemplate]:
    """列出prompt模板"""
    statement = select(PromptTemplate)
    
    if agent_id:
        statement = statement.where(PromptTemplate.agent_id == agent_id)
    
    if not include_inactive:
        statement = statement.where(PromptTemplate.is_active.is_(True))
    
    statement = statement.order_by(
        PromptTemplate.is_default.desc(),  # 默认模板排在前面
        PromptTemplate.created_at.desc()
    )
    
    return list(session.execute(statement).scalars())


def create_prompt_template(
    session: Session,
    name: str,
    agent_id: str,
    content: str,
    description: Optional[str] = None,
    is_default: bool = False,
) -> PromptTemplate:
    """创建新的prompt模板"""
    template_id = str(uuid.uuid4())
    template = PromptTemplate(
        id=template_id,
        name=name,
        agent_id=agent_id,
        content=content,
        description=description,
        is_default=is_default,
        is_active=True,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def update_prompt_template(
    session: Session,
    template_id: str,
    name: Optional[str] = None,
    content: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> PromptTemplate | None:
    """更新prompt模板"""
    template = session.get(PromptTemplate, template_id)
    if not template:
        return None
    
    if name is not None:
        template.name = name
    if content is not None:
        template.content = content
    if description is not None:
        template.description = description
    if is_active is not None:
        template.is_active = is_active
    
    template.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(template)
    return template


def activate_prompt_template(session: Session, template_id: str, agent_id: str) -> PromptTemplate | None:
    """激活指定的prompt模板（同时将同一智能体的其他模板设为非激活）"""
    template = session.get(PromptTemplate, template_id)
    if not template or template.agent_id != agent_id:
        return None
    
    # 将同一智能体的所有模板设为非激活
    statement = select(PromptTemplate).where(
        PromptTemplate.agent_id == agent_id
    )
    other_templates = list(session.execute(statement).scalars())
    for t in other_templates:
        t.is_active = False
    
    # 激活指定的模板
    template.is_active = True
    template.updated_at = datetime.utcnow()
    
    session.commit()
    session.refresh(template)
    return template


def delete_prompt_template(session: Session, template_id: str) -> bool:
    """删除prompt模板（不能删除默认模板）"""
    template = session.get(PromptTemplate, template_id)
    if not template:
        return False
    
    # 不允许删除默认模板
    if template.is_default:
        return False
    
    session.delete(template)
    session.commit()
    return True
