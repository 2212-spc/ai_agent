from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Literal

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import (
    ToolRecord,
    get_session_factory,
    get_tool_by_id,
    init_engine,
    list_tool_logs,
    list_tools,
)
from .rag_service import (
    RetrievedContext,
    delete_document,
    ingest_document,
    list_documents,
    retrieve_context,
)
from .tool_service import (
    build_tool_prompt,
    execute_tool,
    list_builtin_options,
    load_tool_config,
    parse_tool_call,
    validate_tool_config,
)
from .graph_agent import run_agent, stream_agent
from .file_processor import FileProcessor, chunk_text
from .rag_service import ingest_text_chunk
from .agent_builder import execute_custom_agent, stream_custom_agent
from .agent_roles import list_available_agents
from .memory_service import (
    retrieve_relevant_memories,
    save_conversation_and_extract_memories,
    format_memories_for_prompt,
    delete_memory_complete,
    extract_memories_from_conversation,
)
from .auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_token,
)
from .database import (
    AgentConfig,
    ConversationHistory,
    PromptTemplate,
    User,
    Memory,
    SessionConfig,
    UserPreferences,
    get_agent_config_by_id,
    list_agent_configs,
    get_conversation_history,
    list_conversation_sessions,
    search_conversation_sessions,
    delete_conversation_session,
    delete_conversation_message,
    get_prompt_template_by_id,
    get_active_prompt_for_agent,
    list_prompt_templates,
    create_prompt_template,
    update_prompt_template,
    create_memory,
    get_memory_by_id,
    search_memories,
    update_memory,
    delete_memory,
    delete_memories_batch,
    get_session_config,
    update_session_config,
    get_user_preferences,
    update_user_preferences,
    activate_prompt_template,
    delete_prompt_template,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 课程大作业可放开，实际环境请限制域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/frontend/agent_chat.html")

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"🌐 收到请求: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"📤 响应状态: {response.status_code}")
    return response


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    model: str = Field(default="deepseek-chat", description="DeepSeek 模型 ID")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    use_knowledge_base: bool = Field(
        default=False, description="是否启用知识库检索增强（RAG）。"
    )
    top_k: int = Field(
        default=4,
        ge=1,
        le=10,
        description="知识库检索返回的片段数量。",
    )
    use_tools: bool = Field(
        default=False, description="是否允许代理调用 MCP 工具。"
    )
    tool_ids: Optional[List[str]] = Field(
        default=None, description="可选，限制可用的工具 ID 列表。"
    )
    session_id: Optional[str] = Field(
        default=None, description="会话ID，用于长期记忆和对话历史。"
    )
    user_id: Optional[str] = Field(
        default=None, description="用户ID，用于多用户场景。"
    )
    # 记忆控制字段（前端发送）
    memory_mode: Optional[str] = Field(
        default="session", description="记忆模式：'global'（全局记忆）或 'session'（独立记忆）"
    )
    share_memory: Optional[bool] = Field(
        default=None, description="是否共享记忆（显式控制，优先级最高）"
    )


class ContextSnippet(BaseModel):
    document_id: Optional[str]
    original_name: Optional[str]
    content: str


class ToolExecutionResult(BaseModel):
    tool_id: str
    tool_name: str
    output: str


class ChatResponse(BaseModel):
    reply: str
    raw: Dict[str, Any] = Field(default_factory=dict)
    contexts: List[ContextSnippet] = Field(default_factory=list)
    tool_results: List[ToolExecutionResult] = Field(default_factory=list)


class DocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    file_size: int
    chunk_count: int
    created_at: datetime
    summary: Optional[str]


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    tool_type: str
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ToolCreateRequest(BaseModel):
    name: str
    description: str
    tool_type: Literal["builtin", "http_get"]
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ToolUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tool_type: Optional[Literal["builtin", "http_get"]] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ToolExecuteRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    tool_id: str
    tool_name: str
    output: str


class ToolLogItem(BaseModel):
    id: str
    tool_id: str
    tool_name: str
    arguments: Optional[Dict[str, Any]]
    result_preview: Optional[str]
    success: bool
    error_message: Optional[str]
    created_at: datetime


class AgentConfigCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]  # {nodes: [...], edges: [...]}
    is_active: bool = True


class AgentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==================== Prompt模板相关的请求和响应模型 ====================

class PromptTemplateResponse(BaseModel):
    """Prompt模板响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    agent_id: str
    content: str
    description: Optional[str]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PromptTemplateCreateRequest(BaseModel):
    """创建Prompt模板的请求模型"""
    name: str
    agent_id: str
    content: str
    description: Optional[str] = None


class PromptTemplateUpdateRequest(BaseModel):
    """更新Prompt模板的请求模型"""
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PromptGenerateRequest(BaseModel):
    """Prompt生成请求"""
    agent_id: str = Field(..., description="智能体ID")
    user_requirement: str = Field(..., description="用户需求描述（自然语言）")
    reference_style: Optional[str] = Field(None, description="参考风格（如：简洁、详细、专业等）")
    output_format: Optional[str] = Field(None, description="期望的输出格式（如：JSON、Markdown、纯文本等）")


class AgentExecuteRequest(BaseModel):
    agent_id: str
    messages: List[Message]
    use_knowledge_base: bool = False
    use_tools: bool = True


def ensure_directories(settings: Settings) -> None:
    for path in (settings.data_dir, settings.chroma_dir, settings.sqlite_path.parent):
        Path(path).mkdir(parents=True, exist_ok=True)


def register_builtin_tools_on_startup() -> None:
    """
    在启动时自动注册所有内置工具
    
    作用：确保数据库中有可用的内置工具，避免 Agent 找不到工具
    策略：只注册数据库中不存在的工具，避免重复注册
    """
    logger.info("🔧 [启动] 检查并注册内置工具...")
    
    # 获取数据库会话
    SessionLocal = get_session_factory()
    session = SessionLocal()
    
    try:
        # 定义需要注册的内置工具
        builtin_tools_to_register = [
            {
                "name": "天气查询",
                "description": "查询指定城市的实时天气情况，包括温度、湿度、风速等信息。支持中英文城市名。",
                "builtin_key": "get_weather"
            },
            {
                "name": "网页搜索",
                "description": "在互联网上搜索信息。输入搜索关键词，返回相关网页的标题、链接和摘要。适合查找最新信息、新闻、技术文档等。",
                "builtin_key": "web_search"
            },
            {
                "name": "绘制思维导图",
                "description": "使用 Mermaid 语法绘制流程图、思维导图、架构图等结构图，保存为 Markdown 文件。",
                "builtin_key": "draw_diagram"
            },
            {
                "name": "写入笔记",
                "description": "在 data/notes 目录下创建或覆盖笔记文件，可用于记录总结或执行结果。",
                "builtin_key": "write_note"
            },
            {
                "name": "获取网页内容",
                "description": "读取指定网页的完整内容（Markdown格式）。适合深入阅读某个网页的详细信息。",
                "builtin_key": "fetch_webpage"
            },
        ]
        
        # 获取数据库中已存在的工具
        existing_tools = session.query(ToolRecord).all()
        existing_builtin_keys = set()
        
        for tool in existing_tools:
            try:
                config = json.loads(tool.config or "{}")
                if tool.tool_type == "builtin":
                    builtin_key = config.get("builtin_key")
                    if builtin_key:
                        existing_builtin_keys.add(builtin_key)
            except:
                pass
        
        # 注册缺失的工具
        registered_count = 0
        for tool_def in builtin_tools_to_register:
            builtin_key = tool_def["builtin_key"]
            
            if builtin_key in existing_builtin_keys:
                logger.debug(f"   ⏭️  工具已存在: {tool_def['name']} ({builtin_key})")
                continue
            
            # 创建新工具记录
            new_tool = ToolRecord(
                id=uuid.uuid4().hex,
                name=tool_def["name"],
                description=tool_def["description"],
                tool_type="builtin",
                config=json.dumps({"builtin_key": builtin_key}, ensure_ascii=False),
                is_active=True,
            )
            session.add(new_tool)
            registered_count += 1
            logger.info(f"   ✅ 已注册工具: {tool_def['name']} ({builtin_key})")
        
        if registered_count > 0:
            session.commit()
            logger.info(f"🎉 [启动] 成功注册 {registered_count} 个新的内置工具")
        else:
            logger.info(f"✅ [启动] 所有内置工具已存在，无需注册")
        
        # 显示当前可用的工具
        all_active_tools = session.query(ToolRecord).filter(ToolRecord.is_active == True).all()
        logger.info(f"📊 [启动] 当前可用工具数量: {len(all_active_tools)}")
        for tool in all_active_tools:
            config = json.loads(tool.config or "{}")
            builtin_key = config.get("builtin_key", "N/A")
            logger.info(f"   • {tool.name} ({tool.tool_type}, key: {builtin_key})")
            
    except Exception as e:
        logger.error(f"❌ [启动] 注册内置工具失败: {e}", exc_info=True)
        session.rollback()
    finally:
        session.close()


@app.on_event("startup")
async def startup() -> None:
    try:
        settings = get_settings()
        logger.info("数据目录: %s", settings.data_dir)
        logger.info("数据库路径: %s", settings.sqlite_path)
        logger.info("Chroma 目录: %s", settings.chroma_dir)
        
        # 验证 API Key
        if not settings.validate_api_key():
            logger.warning("⚠️ DeepSeek API Key 未配置或无效！")
            logger.warning("请设置环境变量 DEEPSEEK_API_KEY 或在 backend/.env 文件中配置")
            logger.warning("示例: DEEPSEEK_API_KEY=sk-your-real-api-key")
        else:
            logger.info("✅ DeepSeek API Key 已配置")
        
        ensure_directories(settings)
        init_engine(settings.sqlite_path)
        logger.info("✅ 数据库初始化成功")
        
        # 自动注册内置工具
        register_builtin_tools_on_startup()
        
        # 预加载嵌入模型（避免首次上传文件卡住）
        # 注意：已注释掉，因为模型加载可能占用大量内存，导致系统重启
        # 模型会在首次使用时按需加载
        # try:
        #     logger.info("🔄 预加载嵌入模型...")
        #     from .rag_service import get_embeddings
        #     embeddings = get_embeddings()
        #     test_emb = embeddings.embed_query("预热测试")
        #     logger.info(f"✅ 嵌入模型已加载 (维度: {len(test_emb)})")
        # except Exception as e:
        #     logger.warning(f"⚠️ 嵌入模型预加载失败: {e}")
            
    except Exception as exc:  # pragma: no cover
        logger.exception("启动初始化失败: %s", exc)
        raise


def get_db_session() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def invoke_deepseek(
    *,
    messages: List[Dict[str, str]],
    settings: Settings,
    model: str,
    temperature: float,
    max_tokens: Optional[int],
) -> tuple[str, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        response = await client.post(endpoint, json=payload, headers=headers)

    if response.status_code != 200:
        logger.error(
            "DeepSeek API error %s: %s", response.status_code, response.text
        )
        raise HTTPException(
            status_code=502,
            detail=f"DeepSeek API error {response.status_code}",
        )

    data = response.json()
    try:
        reply = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as error:
        logger.exception("Unexpected DeepSeek response: %s", data)
        raise HTTPException(
            status_code=502, detail="Unexpected DeepSeek response structure"
        ) from error
    return reply, data


def apply_rag_context(
    base_messages: List[Dict[str, str]],
    contexts: List[RetrievedContext],
) -> List[Dict[str, str]]:
    if not contexts:
        return base_messages

    context_parts: List[str] = []
    for idx, ctx in enumerate(contexts, start=1):
        doc_name = ctx.original_name or "未知文档"
        context_parts.append(
            f"【文档片段{idx}】\n来源：{doc_name}\n内容：\n{ctx.content}\n"
        )
    context_text = "".join(context_parts)
    system_prompt = (
        "你是一个智能助手，现在用户上传了一些文档到知识库。以下是与问题最相关的片段，"
        "请结合它们回答用户问题。\n"
        f"{context_text}\n"
        "【重要提示】\n"
        "1. 请直接引用上述内容作答。\n"
        "2. 内容足以回答时请详细阐述；不足时说明缺失信息。\n"
        "3. 可标注片段来源，避免编造。"
    )
    return base_messages[:-1] + [{"role": "system", "content": system_prompt}] + [
        base_messages[-1]
    ]


def select_tool_records(payload: ChatRequest, session: Session) -> List[ToolRecord]:
    if not payload.use_tools:
        return []
    available = list_tools(session, include_inactive=False)
    if not payload.tool_ids:
        return available
    tool_map = {tool.id: tool for tool in available}
    missing = [tool_id for tool_id in payload.tool_ids if tool_id not in tool_map]
    if missing:
        raise HTTPException(status_code=404, detail=f"未找到以下工具：{', '.join(missing)}")
    return [tool_map[tool_id] for tool_id in payload.tool_ids]


def prepare_agent_environment(
    payload: ChatRequest,
    settings: Settings,
    session: Session,
) -> tuple[
    List[Dict[str, str]],
    List[Dict[str, str]],
    List[RetrievedContext],
    List[ToolRecord],
]:
    base_messages = [message.model_dump() for message in payload.messages]
    if not base_messages:
        raise HTTPException(status_code=400, detail="messages 不能为空。")

    retrieved_contexts: List[RetrievedContext] = []
    if payload.use_knowledge_base:
        query = payload.messages[-1].content
        retrieved_contexts = retrieve_context(
            query=query, settings=settings, top_k=payload.top_k
        )
        if retrieved_contexts:
            base_messages = apply_rag_context(base_messages, retrieved_contexts)

    tool_records = select_tool_records(payload, session)
    llm_messages = list(base_messages)
    if tool_records:
        tool_prompt = build_tool_prompt(tool_records)
        llm_messages = [{"role": "system", "content": tool_prompt}] + llm_messages

    return base_messages, llm_messages, retrieved_contexts, tool_records


def build_context_snippets(
    retrieved_contexts: List[RetrievedContext],
) -> List[ContextSnippet]:
    return [
        ContextSnippet(
            document_id=ctx.document_id,
            original_name=ctx.original_name,
            content=ctx.content[:500],
        )
        for ctx in retrieved_contexts
    ]


def format_sse(event: str, data: Dict[str, Any]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> Dict[str, str]:
    _ = settings.deepseek_api_key
    return {"status": "ok"}


# ==================== 认证相关 API ====================

class UserRegister(BaseModel):
    """用户注册请求模型"""
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    """用户登录请求模型"""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Token 响应模型"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求模型"""
    refresh_token: str


@app.post("/api/auth/register", response_model=TokenResponse)
async def register(
    user_data: UserRegister,
    session: Session = Depends(get_db_session)
):
    """用户注册接口"""
    # 检查邮箱是否已被注册
    existing_user = session.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 检查用户名是否已被使用
    existing_username = session.query(User).filter(
        User.username == user_data.username
    ).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被使用"
        )
    
    # 验证密码长度
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码至少需要8位字符"
        )
    
    # 加密密码
    hashed_password = get_password_hash(user_data.password)
    
    # 创建新用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    # 保存到数据库
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    # 生成 JWT token
    access_token = create_access_token(data={"sub": new_user.id})
    refresh_token = create_refresh_token(data={"sub": new_user.id})
    
    logger.info(f"✅ 新用户注册成功: {user_data.email}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=new_user.id,
        username=new_user.username
    )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    session: Session = Depends(get_db_session)
):
    """用户登录接口"""
    user = authenticate_user(session, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    session.commit()
    
    # 生成 JWT token
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    logger.info(f"✅ 用户登录成功: {user_data.email}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        username=user.username
    )


@app.post("/api/auth/refresh")
async def refresh_token_endpoint(
    token_data: RefreshTokenRequest,
    session: Session = Depends(get_db_session)
):
    """刷新 Access Token 接口"""
    payload = verify_token(token_data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的刷新 token"
        )
    
    user_id = payload.get("sub")
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 生成新的 access token
    new_access_token = create_access_token(data={"sub": user.id})
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


# 定义 get_current_user 依赖（需要在这里定义以避免循环导入）
from .auth import oauth2_scheme

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_db_session)
) -> User:
    """获取当前登录用户（FastAPI 依赖注入）"""
    from .auth import verify_token
    
    payload = verify_token(token)
    user_id: str = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据：缺少用户ID",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 从数据库查询用户
    user = session.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    return user


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> ChatResponse:
    _, llm_messages, retrieved_contexts, tool_records = prepare_agent_environment(
        payload, settings, session
    )

    first_reply, first_data = await invoke_deepseek(
        messages=llm_messages,
        settings=settings,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )

    tool_results: List[ToolExecutionResult] = []
    final_reply = first_reply
    raw_payload: Dict[str, Any] = {"first_call": first_data}

    if tool_records:
        tool_call = parse_tool_call(first_reply)
        if tool_call:
            tool_id = tool_call.get("tool_id")
            arguments = tool_call.get("arguments", {})
            if not tool_id:
                raise HTTPException(status_code=400, detail="tool_call 缺少 tool_id。")
            matched_tool = next(
                (tool for tool in tool_records if tool.id == tool_id), None
            )
            if matched_tool is None:
                raise HTTPException(status_code=404, detail=f"工具 {tool_id} 不在可用列表中")

            result_text = execute_tool(
                tool=matched_tool,
                arguments=arguments if isinstance(arguments, dict) else {},
                settings=settings,
                session=session,
            )
            result_item = ToolExecutionResult(
                tool_id=matched_tool.id,
                tool_name=matched_tool.name,
                output=result_text,
            )
            tool_results.append(result_item)

            followup_messages = llm_messages + [
                {"role": "assistant", "content": first_reply},
                {
                    "role": "system",
                    "content": (
                        f"工具 {matched_tool.name} (ID: {matched_tool.id}) 已执行完成，输出如下：\n"
                        f"{result_text}\n请结合该结果回答用户问题。"
                    ),
                },
            ]
            final_reply, second_data = await invoke_deepseek(
                messages=followup_messages,
                settings=settings,
                model=payload.model,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
            )
            raw_payload["final"] = second_data
        else:
            raw_payload["final"] = first_data
    else:
        raw_payload["final"] = first_data

    contexts = build_context_snippets(retrieved_contexts)

    return ChatResponse(
        reply=final_reply,
        raw=raw_payload,
        contexts=contexts,
        tool_results=tool_results,
    )


@app.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    base_messages, llm_messages, retrieved_contexts, tool_records = (
        prepare_agent_environment(payload, settings, session)
    )
    contexts = build_context_snippets(retrieved_contexts)

    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            yield format_sse("status", {"stage": "started"})
            yield format_sse(
                "context",
                {"items": [snippet.model_dump() for snippet in contexts]},
            )

            first_reply, first_data = await invoke_deepseek(
                messages=llm_messages,
                settings=settings,
                model=payload.model,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
            )
            yield format_sse("assistant_draft", {"content": first_reply})

            tool_results: List[ToolExecutionResult] = []
            final_reply = first_reply
            raw_payload: Dict[str, Any] = {"first_call": first_data}

            if tool_records:
                tool_call = parse_tool_call(first_reply)
                if tool_call:
                    yield format_sse("tool_call", tool_call)
                    tool_id = tool_call.get("tool_id")
                    arguments = tool_call.get("arguments", {})
                    matched_tool = next(
                        (tool for tool in tool_records if tool.id == tool_id), None
                    )
                    if matched_tool is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"工具 {tool_id} 不在可用列表中",
                        )
                    result_text = execute_tool(
                        tool=matched_tool,
                        arguments=arguments if isinstance(arguments, dict) else {},
                        settings=settings,
                        session=session,
                    )
                    result_item = ToolExecutionResult(
                        tool_id=matched_tool.id,
                        tool_name=matched_tool.name,
                        output=result_text,
                    )
                    tool_results.append(result_item)
                    yield format_sse(
                        "tool_result", result_item.model_dump()
                    )

                    followup_messages = llm_messages + [
                        {"role": "assistant", "content": first_reply},
                        {
                            "role": "system",
                            "content": (
                                f"工具 {matched_tool.name} (ID: {matched_tool.id}) 已执行完成，输出如下：\n"
                                f"{result_text}\n请结合该结果回答用户问题。"
                            ),
                        },
                    ]
                    final_reply, second_data = await invoke_deepseek(
                        messages=followup_messages,
                        settings=settings,
                        model=payload.model,
                        temperature=payload.temperature,
                        max_tokens=payload.max_tokens,
                    )
                    raw_payload["final"] = second_data
                    yield format_sse(
                        "assistant_final", {"content": final_reply}
                    )
                else:
                    # 没有找到工具调用，first_reply 就是最终回复
                    raw_payload["final"] = first_data
                    yield format_sse(
                        "assistant_final", {"content": first_reply}
                    )
            else:
                # 没有启用工具，first_reply 就是最终回复
                raw_payload["final"] = first_data
                yield format_sse(
                    "assistant_final", {"content": first_reply}
                )

            yield format_sse(
                "completed",
                {
                    "reply": final_reply,
                    "contexts": [snippet.model_dump() for snippet in contexts],
                    "tool_results": [result.model_dump() for result in tool_results],
                    "raw": raw_payload,
                },
            )
        except HTTPException as http_error:
            yield format_sse(
                "error",
                {"message": http_error.detail, "status_code": http_error.status_code},
            )
        except Exception as exc:  # pragma: no cover - streaming fallback
            logger.exception("Streaming chat 出错: %s", exc)
            yield format_sse("error", {"message": str(exc)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/documents/upload", response_model=DocumentItem)
async def upload_document(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> DocumentItem:
    record = await ingest_document(file, settings=settings, session=session)
    return DocumentItem.model_validate(record)


@app.get("/documents", response_model=List[DocumentItem])
async def list_uploaded_documents(
    session: Session = Depends(get_db_session),
) -> List[DocumentItem]:
    records = list_documents(session)
    return [DocumentItem.model_validate(record) for record in records]


@app.delete("/documents/{document_id}")
async def remove_document(
    document_id: str,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> Dict[str, str]:
    delete_document(document_id=document_id, settings=settings, session=session)
    return {"status": "deleted"}


@app.get("/tools/builtin-options")
async def get_builtin_options() -> List[Dict[str, Any]]:
    return list_builtin_options()


@app.get("/tools", response_model=List[ToolResponse])
async def list_registered_tools(
    include_inactive: bool = False,
    session: Session = Depends(get_db_session),
) -> List[ToolResponse]:
    records = list_tools(session, include_inactive=include_inactive)
    return [serialize_tool(record) for record in records]


@app.post("/tools", response_model=ToolResponse)
async def create_tool(
    payload: ToolCreateRequest,
    session: Session = Depends(get_db_session),
) -> ToolResponse:
    validate_tool_config(payload.tool_type, payload.config)
    tool = ToolRecord(
        id=uuid.uuid4().hex,
        name=payload.name,
        description=payload.description,
        tool_type=payload.tool_type,
        config=json.dumps(payload.config, ensure_ascii=False),
        is_active=payload.is_active,
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return serialize_tool(tool)


@app.put("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    payload: ToolUpdateRequest,
    session: Session = Depends(get_db_session),
) -> ToolResponse:
    tool = get_tool_by_id(session, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="工具不存在。")

    if payload.name is not None:
        tool.name = payload.name
    if payload.description is not None:
        tool.description = payload.description
    if payload.tool_type is not None:
        tool.tool_type = payload.tool_type
    if payload.config is not None:
        validate_tool_config(tool.tool_type, payload.config)
        tool.config = json.dumps(payload.config, ensure_ascii=False)
    if payload.is_active is not None:
        tool.is_active = payload.is_active

    session.commit()
    session.refresh(tool)
    return serialize_tool(tool)


@app.delete("/tools/{tool_id}")
async def delete_tool(
    tool_id: str,
    session: Session = Depends(get_db_session),
) -> Dict[str, str]:
    tool = get_tool_by_id(session, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="工具不存在。")
    session.delete(tool)
    session.commit()
    return {"status": "deleted"}


@app.post("/tools/{tool_id}/execute", response_model=ToolExecuteResponse)
async def execute_tool_endpoint(
    tool_id: str,
    payload: ToolExecuteRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> ToolExecuteResponse:
    tool = get_tool_by_id(session, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="工具不存在。")

    result = execute_tool(
        tool=tool,
        arguments=payload.arguments,
        settings=settings,
        session=session,
    )
    return ToolExecuteResponse(tool_id=tool.id, tool_name=tool.name, output=result)


@app.get("/tool-logs", response_model=List[ToolLogItem])
async def get_tool_logs(
    limit: int = 50,
    session: Session = Depends(get_db_session),
) -> List[ToolLogItem]:
    logs = list_tool_logs(session, limit=limit)
    return [
        ToolLogItem(
            id=log.id,
            tool_id=log.tool_id,
            tool_name=log.tool_name,
            arguments=json.loads(log.arguments) if log.arguments else None,
            result_preview=log.result_preview,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at,
        )
        for log in logs
    ]


@app.post("/chat/agent", response_model=ChatResponse)
async def chat_with_langgraph_agent(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> ChatResponse:
    """
    使用 LangGraph Agent 处理对话
    
    特点：
    - 多步骤规划与执行
    - 智能工具选择
    - 状态持久化
    - 反思与优化
    - 长期记忆系统
    """
    logger.info("🤖 [LangGraph Agent] 开始处理请求")
    
    # 获取可用工具
    tool_records = select_tool_records(payload, session)
    
    # 获取或生成 session_id，并根据请求更新会话记忆配置
    session_id = payload.session_id or str(uuid.uuid4())
    current_config = get_session_config(session, session_id)
    share_memory_value = False
    if payload.share_memory is not None:
        share_memory_value = payload.share_memory
    elif payload.memory_mode == 'global':
        share_memory_value = True
    elif current_config:
        share_memory_value = current_config.share_memory
    update_session_config(
        session=session,
        session_id=session_id,
        share_memory=share_memory_value,
        user_id=payload.user_id,
    )
    
    # 运行 LangGraph Agent
    result = await run_agent(
        user_query=payload.messages[-1].content if payload.messages else "",
        settings=settings,
        session=session,
        tool_records=tool_records,
        use_knowledge_base=payload.use_knowledge_base,
        conversation_history=[msg.model_dump() for msg in payload.messages],
        session_id=session_id,
        user_id=payload.user_id,
    )
    
    # 构建响应
    contexts = [
        ContextSnippet(
            document_id=ctx.get("document_id"),
            original_name=ctx.get("original_name"),
            content=ctx.get("content", "")[:500]
        )
        for ctx in result.get("retrieved_contexts", [])
    ]
    
    tool_results = [
        ToolExecutionResult(
            tool_id=tr.get("tool_id", ""),
            tool_name=tr.get("tool_name", ""),
            output=tr.get("output", "")
        )
        for tr in result.get("tool_results", [])
    ]
    
    return ChatResponse(
        reply=result.get("final_answer", "抱歉，无法生成答案"),
        raw={
            "thoughts": result.get("thoughts", []),
            "observations": result.get("observations", []),
            "plan": result.get("plan", ""),
            "quality_score": result.get("quality_score", 0.0),
            "reflection": result.get("reflection", ""),
            "thread_id": result.get("thread_id", ""),
            "success": result.get("success", False),
        },
        contexts=contexts,
        tool_results=tool_results,
    )


@app.get("/agent/workflow/visualization")
async def get_workflow_visualization() -> Dict[str, Any]:
    """
    获取 LangGraph Agent 工作流的可视化表示（Mermaid 格式）
    """
    mermaid_graph = """
graph TD
    A[用户输入] --> B[🧠 规划器<br/>任务分析与规划]
    B --> C[🔀 路由器<br/>决策下一步]
    
    C -->|需要知识库| D[📚 知识库检索<br/>RAG检索]
    C -->|需要工具| E[🔧 工具执行器<br/>调用工具]
    C -->|信息充足| F[🤔 反思器<br/>质量评估]
    
    D --> C
    E --> C
    
    F -->|质量不足<br/>需要人工| G[👤 人工介入<br/>等待反馈]
    F -->|质量合格| H[✨ 合成器<br/>生成答案]
    
    G --> C
    
    H --> I[完成]
    
    style A fill:#667eea,stroke:#333,stroke-width:2px,color:#fff
    style I fill:#10a37f,stroke:#333,stroke-width:2px,color:#fff
    style B fill:#fff9e6,stroke:#ffc107,stroke-width:2px
    style C fill:#e6f7ff,stroke:#1890ff,stroke-width:2px
    style D fill:#f0f9ff,stroke:#10a37f,stroke-width:2px
    style E fill:#f0f9ff,stroke:#10a37f,stroke-width:2px
    style F fill:#fff0f6,stroke:#eb2f96,stroke-width:2px
    style G fill:#fff1f0,stroke:#ff4d4f,stroke-width:2px
    style H fill:#f6ffed,stroke:#52c41a,stroke-width:2px
"""
    
    return {
        "mermaid_code": mermaid_graph,
        "description": "LangGraph Agent 工作流图",
        "nodes": [
            {"id": "planner", "name": "规划器", "description": "分析用户问题，制定执行计划"},
            {"id": "router", "name": "路由器", "description": "根据当前状态决定下一步动作"},
            {"id": "knowledge_search", "name": "知识库检索", "description": "从向量数据库检索相关内容"},
            {"id": "tool_executor", "name": "工具执行器", "description": "智能选择并执行工具"},
            {"id": "reflector", "name": "反思器", "description": "评估当前进展，决定是否需要调整"},
            {"id": "synthesizer", "name": "合成器", "description": "综合所有信息生成最终答案"},
            {"id": "human_input", "name": "人工介入", "description": "暂停执行，等待人工反馈"}
        ]
    }


@app.post("/chat/agent/stream")
async def chat_with_langgraph_agent_stream(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """
    使用 LangGraph Agent 处理对话（流式）
    
    实时返回 Agent 的思考过程和执行步骤
    """
    logger.info("🌊 [LangGraph Agent Stream] 开始流式处理")
    
    tool_records = select_tool_records(payload, session)
    
    # 获取或生成 session_id
    session_id = payload.session_id or str(uuid.uuid4())
    
    # 🔒 根据前端请求设置会话的记忆配置
    from .database import get_session_config, SessionConfig
    session_config = get_session_config(session, session_id)
    
    # 确定是否共享记忆
    share_memory_value = False  # 默认：独立记忆
    if payload.share_memory is not None:
        # 如果前端显式指定，优先使用前端的值
        share_memory_value = payload.share_memory
    elif payload.memory_mode == 'global':
        # 如果前端指定了全局记忆模式
        share_memory_value = True
    elif session_config:
        # 使用已有的会话配置
        share_memory_value = session_config.share_memory
    
    # 创建或更新会话配置
    session_config = update_session_config(
        session=session,
        session_id=session_id,
        share_memory=share_memory_value,
        user_id=payload.user_id,
    )
    logger.info(f"🔒 会话 {session_id} 记忆模式: {'全局共享' if session_config.share_memory else '独立隔离'}")
    
    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            # 发送状态事件，包含 session_id 以便前端保存
            yield format_sse("status", {
                "stage": "started", 
                "mode": "langgraph_agent",
                "session_id": session_id
            })
            
            # 流式执行 LangGraph Agent
            async for event in stream_agent(
                user_query=payload.messages[-1].content if payload.messages else "",
                settings=settings,
                session=session,
                tool_records=tool_records,
                use_knowledge_base=payload.use_knowledge_base,
                conversation_history=[msg.model_dump() for msg in payload.messages],
                session_id=session_id,
                user_id=payload.user_id,
            ):
                event_type = event.get("event", "unknown")
                
                if event_type == "node_output":
                    # 节点执行输出
                    node_name = event.get("node", "")
                    node_data = event.get("data", {})
                    
                    # 发送节点开始事件
                    yield format_sse("agent_node", {
                        "node": node_name,
                        "status": "completed",
                        "data": node_data,
                        "timestamp": event.get("timestamp")
                    })
                    
                    # 如果有思考过程，发送思考事件
                    if "thoughts" in node_data and node_data["thoughts"]:
                        for thought in node_data["thoughts"]:
                            yield format_sse("agent_thought", {
                                "node": node_name,
                                "thought": thought,
                                "timestamp": event.get("timestamp")
                            })
                    
                    # 如果有观察结果，发送观察事件
                    if "observations" in node_data and node_data["observations"]:
                        for observation in node_data["observations"]:
                            yield format_sse("agent_observation", {
                                "node": node_name,
                                "observation": observation,
                                "timestamp": event.get("timestamp")
                            })
                    
                    # 如果有工具结果，发送工具事件
                    if "tool_results" in node_data and node_data["tool_results"]:
                        for tool_result in node_data["tool_results"]:
                            yield format_sse("tool_result", tool_result)
                    
                    # 如果有知识库检索结果
                    if "retrieved_contexts" in node_data and node_data["retrieved_contexts"]:
                        yield format_sse("context", {
                            "items": node_data["retrieved_contexts"]
                        })
                    
                    # 如果有最终答案
                    if "final_answer" in node_data and node_data["final_answer"]:
                        yield format_sse("assistant_final", {
                            "content": node_data["final_answer"]
                        })
                        logger.info(f"📤 已发送最终答案到前端，长度: {len(node_data['final_answer'])}")
                
                elif event_type == "completed":
                    # Agent 执行完成
                    yield format_sse("completed", {
                        "thread_id": event.get("thread_id"),
                        "timestamp": event.get("timestamp")
                    })
                    logger.info(f"📤 已发送完成事件到前端")
        
        except HTTPException as http_error:
            yield format_sse(
                "error",
                {"message": http_error.detail, "status_code": http_error.status_code},
            )
        except Exception as exc:
            logger.exception("LangGraph Agent streaming 出错: %s", exc)
            yield format_sse("error", {"message": str(exc)})
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


def serialize_tool(record: ToolRecord) -> ToolResponse:
    config = load_tool_config(record)
    return ToolResponse.model_validate(
        {
            "id": record.id,
            "name": record.name,
            "description": record.description,
            "tool_type": record.tool_type,
            "config": config,
            "is_active": record.is_active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


# ==================== Agent构建器API ====================

@app.post("/agents", response_model=AgentConfigResponse)
async def create_agent_config(
    payload: AgentConfigCreateRequest,
    session: Session = Depends(get_db_session),
) -> AgentConfigResponse:
    """创建自定义Agent配置"""
    agent = AgentConfig(
        id=uuid.uuid4().hex,
        name=payload.name,
        description=payload.description,
        config=json.dumps(payload.config, ensure_ascii=False),
        is_active=payload.is_active,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    
    return AgentConfigResponse.model_validate({
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "config": json.loads(agent.config),
        "is_active": agent.is_active,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    })


@app.get("/agents", response_model=List[AgentConfigResponse])
async def list_agent_configs_endpoint(
    include_inactive: bool = False,
    session: Session = Depends(get_db_session),
) -> List[AgentConfigResponse]:
    """列出所有Agent配置"""
    agents = list_agent_configs(session, include_inactive=include_inactive)
    return [
        AgentConfigResponse.model_validate({
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "config": json.loads(agent.config),
            "is_active": agent.is_active,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        })
        for agent in agents
    ]


@app.get("/agents/list")
async def list_agents_endpoint() -> List[Dict[str, Any]]:
    """获取所有可用的智能体列表（角色定义）"""
    return list_available_agents()


@app.get("/agents/{agent_id}", response_model=AgentConfigResponse)
async def get_agent_config(
    agent_id: str,
    session: Session = Depends(get_db_session),
) -> AgentConfigResponse:
    """获取Agent配置"""
    agent = get_agent_config_by_id(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent配置不存在")
    
    return AgentConfigResponse.model_validate({
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "config": json.loads(agent.config),
        "is_active": agent.is_active,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    })


# ==================== Prompt模板管理API ====================

@app.get("/prompts", response_model=List[PromptTemplateResponse])
async def list_prompt_templates_endpoint(
    agent_id: Optional[str] = None,
    include_inactive: bool = False,
    session: Session = Depends(get_db_session),
) -> List[PromptTemplateResponse]:
    """列出所有Prompt模板（可按智能体筛选）"""
    templates = list_prompt_templates(
        session, 
        agent_id=agent_id, 
        include_inactive=include_inactive
    )
    return [
        PromptTemplateResponse.model_validate({
            "id": template.id,
            "name": template.name,
            "agent_id": template.agent_id,
            "content": template.content,
            "description": template.description,
            "is_default": template.is_default,
            "is_active": template.is_active,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        })
        for template in templates
    ]


@app.get("/prompts/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: str,
    session: Session = Depends(get_db_session),
) -> PromptTemplateResponse:
    """获取单个Prompt模板"""
    template = get_prompt_template_by_id(session, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt模板不存在")
    
    return PromptTemplateResponse.model_validate({
        "id": template.id,
        "name": template.name,
        "agent_id": template.agent_id,
        "content": template.content,
        "description": template.description,
        "is_default": template.is_default,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    })


@app.get("/prompts/agent/{agent_id}", response_model=List[PromptTemplateResponse])
async def get_prompts_by_agent(
    agent_id: str,
    include_inactive: bool = False,
    session: Session = Depends(get_db_session),
) -> List[PromptTemplateResponse]:
    """获取指定智能体的所有Prompt模板"""
    templates = list_prompt_templates(
        session, 
        agent_id=agent_id, 
        include_inactive=include_inactive
    )
    return [
        PromptTemplateResponse.model_validate({
            "id": template.id,
            "name": template.name,
            "agent_id": template.agent_id,
            "content": template.content,
            "description": template.description,
            "is_default": template.is_default,
            "is_active": template.is_active,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        })
        for template in templates
    ]


@app.get("/prompts/agent/{agent_id}/active", response_model=PromptTemplateResponse)
async def get_active_prompt_for_agent_endpoint(
    agent_id: str,
    session: Session = Depends(get_db_session),
) -> PromptTemplateResponse:
    """获取指定智能体当前激活的Prompt模板"""
    template = get_active_prompt_for_agent(session, agent_id)
    if template is None:
        raise HTTPException(
            status_code=404, 
            detail=f"智能体 {agent_id} 没有激活的Prompt模板"
        )
    
    return PromptTemplateResponse.model_validate({
        "id": template.id,
        "name": template.name,
        "agent_id": template.agent_id,
        "content": template.content,
        "description": template.description,
        "is_default": template.is_default,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    })


@app.post("/prompts", response_model=PromptTemplateResponse)
async def create_prompt_template_endpoint(
    payload: PromptTemplateCreateRequest,
    session: Session = Depends(get_db_session),
) -> PromptTemplateResponse:
    """创建新的Prompt模板"""
    template = create_prompt_template(
        session=session,
        name=payload.name,
        agent_id=payload.agent_id,
        content=payload.content,
        description=payload.description,
        is_default=False,  # 用户创建的模板不是默认模板
    )
    
    return PromptTemplateResponse.model_validate({
        "id": template.id,
        "name": template.name,
        "agent_id": template.agent_id,
        "content": template.content,
        "description": template.description,
        "is_default": template.is_default,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    })


@app.put("/prompts/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template_endpoint(
    template_id: str,
    payload: PromptTemplateUpdateRequest,
    session: Session = Depends(get_db_session),
) -> PromptTemplateResponse:
    """更新Prompt模板"""
    template = update_prompt_template(
        session=session,
        template_id=template_id,
        name=payload.name,
        content=payload.content,
        description=payload.description,
        is_active=payload.is_active,
    )
    
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt模板不存在")
    
    return PromptTemplateResponse.model_validate({
        "id": template.id,
        "name": template.name,
        "agent_id": template.agent_id,
        "content": template.content,
        "description": template.description,
        "is_default": template.is_default,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    })


@app.post("/prompts/{template_id}/activate", response_model=PromptTemplateResponse)
async def activate_prompt_template_endpoint(
    template_id: str,
    session: Session = Depends(get_db_session),
) -> PromptTemplateResponse:
    """激活指定的Prompt模板（同时将同一智能体的其他模板设为非激活）"""
    template = get_prompt_template_by_id(session, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt模板不存在")
    
    activated_template = activate_prompt_template(
        session=session,
        template_id=template_id,
        agent_id=template.agent_id,
    )
    
    if activated_template is None:
        raise HTTPException(
            status_code=400, 
            detail="无法激活该模板，请检查模板ID和智能体ID是否匹配"
        )
    
    return PromptTemplateResponse.model_validate({
        "id": activated_template.id,
        "name": activated_template.name,
        "agent_id": activated_template.agent_id,
        "content": activated_template.content,
        "description": activated_template.description,
        "is_default": activated_template.is_default,
        "is_active": activated_template.is_active,
        "created_at": activated_template.created_at,
        "updated_at": activated_template.updated_at,
    })


@app.post("/prompts/{template_id}/deactivate", response_model=PromptTemplateResponse)
async def deactivate_prompt_template_endpoint(
    template_id: str,
    session: Session = Depends(get_db_session),
) -> PromptTemplateResponse:
    """停用指定的Prompt模板"""
    from .database import list_prompt_templates
    
    template = get_prompt_template_by_id(session, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt模板不存在")
    
    # 检查是否还有其他激活的模板（除了当前要停用的）
    all_templates = list_prompt_templates(
        session, 
        agent_id=template.agent_id, 
        include_inactive=True
    )
    other_active_templates = [
        t for t in all_templates 
        if t.id != template_id and t.is_active
    ]
    
    # 如果停用默认模板，需要确保至少有一个其他激活的模板
    if template.is_default:
        if not other_active_templates:
            raise HTTPException(
                status_code=400,
                detail="不能停用默认模板：该智能体没有其他激活的模板。请先激活另一个模板，或创建新模板后再停用默认模板。"
            )
    
    # 使用更新接口停用
    updated_template = update_prompt_template(
        session=session,
        template_id=template_id,
        name=None,
        content=None,
        description=None,
        is_active=False,
    )
    
    if updated_template is None:
        raise HTTPException(status_code=404, detail="Prompt模板不存在")
    
    return PromptTemplateResponse.model_validate({
        "id": updated_template.id,
        "name": updated_template.name,
        "agent_id": updated_template.agent_id,
        "content": updated_template.content,
        "description": updated_template.description,
        "is_default": updated_template.is_default,
        "is_active": updated_template.is_active,
        "created_at": updated_template.created_at,
        "updated_at": updated_template.updated_at,
    })


@app.delete("/prompts/{template_id}")
async def delete_prompt_template_endpoint(
    template_id: str,
    session: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """删除Prompt模板（不能删除默认模板）"""
    success = delete_prompt_template(session, template_id)
    if not success:
        template = get_prompt_template_by_id(session, template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Prompt模板不存在")
        if template.is_default:
            raise HTTPException(
                status_code=400, 
                detail="不能删除默认模板，默认模板是系统预设的"
            )
        raise HTTPException(status_code=400, detail="删除失败")
    
    return {"status": "deleted", "message": "Prompt模板已删除"}


@app.post("/prompts/init-defaults")
async def init_default_prompts(
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """初始化默认Prompt模板（将硬编码的prompt保存到数据库作为示例）"""
    from .agent_roles import get_default_prompts
    from .database import list_prompt_templates
    
    default_prompts = get_default_prompts()
    created_count = 0
    skipped_count = 0
    
    for prompt_data in default_prompts:
        # 检查是否已存在该智能体的默认模板
        existing_templates = list_prompt_templates(
            session, 
            agent_id=prompt_data["agent_id"], 
            include_inactive=True
        )
        has_default = any(t.is_default for t in existing_templates)
        
        if has_default:
            skipped_count += 1
            continue
        
        # 创建默认模板
        create_prompt_template(
            session=session,
            name=prompt_data["name"],
            agent_id=prompt_data["agent_id"],
            content=prompt_data["content"],
            description=prompt_data.get("description", "系统默认模板，作为示例参考"),
            is_default=True,  # 标记为默认模板
        )
        created_count += 1
    
    return {
        "status": "success",
        "created": created_count,
        "skipped": skipped_count,
        "message": f"初始化完成：创建 {created_count} 个默认模板，跳过 {skipped_count} 个已存在的模板"
    }


def validate_prompt_template(
    prompt: str,
    agent_id: str,
    available_placeholders: List[str],
    format_requirements: Dict[str, Any],
) -> Dict[str, Any]:
    """
    验证prompt模板
    
    Args:
        prompt: 待验证的prompt
        agent_id: 智能体ID
        available_placeholders: 可用的占位符列表
        format_requirements: 格式要求
    
    Returns:
        验证结果
    """
    import re
    
    issues = []
    warnings = []
    
    # 1. 检查占位符
    placeholders = re.findall(r'\{(\w+)\}', prompt)
    if placeholders:
        # 检查未定义的占位符
        undefined = [p for p in placeholders if p not in available_placeholders]
        if undefined:
            warnings.append(f"使用了未定义的占位符: {undefined}，这些占位符可能不会被正确替换")
    
    # 2. 检查格式要求
    if format_requirements:
        required_format = format_requirements.get("required_format")
        
        if required_format == "JSON":
            # 检查是否包含JSON格式要求
            if "JSON" not in prompt.upper() and "json" not in prompt.lower():
                issues.append("缺少JSON格式要求，分析专家/验证专家必须返回JSON格式")
            
            # 检查是否包含"只返回 JSON"的强调
            if "只返回" not in prompt and "只输出" not in prompt:
                warnings.append("建议在prompt末尾添加'只返回 JSON，不要其他解释。'的强调")
            
            # 检查是否包含JSON结构说明
            required_fields = format_requirements.get("required_fields", [])
            missing_fields = []
            for field in required_fields[:3]:  # 只检查前3个字段作为示例
                if field not in prompt:
                    missing_fields.append(field)
            
            if missing_fields and len(missing_fields) == 3:
                warnings.append(f"建议在prompt中明确说明JSON结构，包含字段：{', '.join(required_fields[:5])}...")
        
        elif required_format == "Markdown":
            if "Markdown" not in prompt and "markdown" not in prompt.lower():
                warnings.append("建议明确要求Markdown格式输出")
    
    # 3. 检查占位符格式（双花括号）
    double_braces = re.findall(r'\{\{(\w+)\}\}', prompt)
    if double_braces:
        warnings.append(f"发现双花括号占位符: {double_braces}，系统会自动转换为单花括号，但建议直接使用单花括号")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "placeholders_found": list(set(placeholders)),
        "placeholders_available": available_placeholders,
    }


@app.post("/prompts/generate")
async def generate_prompt_from_requirement(
    payload: PromptGenerateRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    根据用户需求自动生成Prompt模板
    
    用户只需用自然语言描述需求，系统会使用LLM生成结构化的prompt
    """
    from .graph_agent import invoke_llm
    from .agent_roles import list_available_agents
    
    # 获取智能体信息
    agents = list_available_agents()
    agent_info = next((a for a in agents if a["id"] == payload.agent_id), None)
    
    if not agent_info:
        raise HTTPException(status_code=404, detail=f"智能体 {payload.agent_id} 不存在")
    
    # 构建生成prompt的提示词
    style_note = f"\n- 参考风格：{payload.reference_style}" if payload.reference_style else ""
    format_note = f"\n- 输出格式：{payload.output_format}" if payload.output_format else ""
    
    # 根据智能体类型确定可用占位符和格式要求
    agent_placeholders = {
        "retrieval_specialist": ["user_query"],
        "analysis_specialist": ["user_query", "task_description", "analysis_context"],
        "summarization_specialist": ["user_query", "task_description", "full_context"],
        "verification_specialist": ["user_query", "task_description", "final_answer"],
    }
    
    format_requirements = {
        "analysis_specialist": {
            "required_format": "JSON",
            "required_fields": [
                "core_concepts", "key_facts", "key_data",
                "technical_principles", "relationships",
                "trends_insights", "critical_notes",
                "analysis_summary", "confidence_score"
            ],
            "json_structure": """{
  "core_concepts": [{"concept": "...", "explanation": "...", "importance": "high|medium|low"}],
  "key_facts": [{"fact": "...", "source": "...", "confidence": "high|medium|low"}],
  "key_data": [{"data_point": "...", "value": "...", "context": "..."}],
  "technical_principles": [{"principle": "...", "explanation": "...", "advantages": [], "limitations": []}],
  "relationships": [{"from": "...", "to": "...", "relationship_type": "...", "description": "..."}],
  "trends_insights": [{"trend": "...", "evidence": "...", "implications": "..."}],
  "critical_notes": [{"note_type": "...", "description": "..."}],
  "analysis_summary": "...",
  "confidence_score": 0.0-1.0
}"""
        },
        "verification_specialist": {
            "required_format": "JSON",
            "required_fields": [
                "accuracy_score", "completeness_score", "clarity_score",
                "relevance_score", "overall_score", "issues", "suggestions", "verdict"
            ],
            "json_structure": """{
  "accuracy_score": 0-10,
  "completeness_score": 0-10,
  "clarity_score": 0-10,
  "relevance_score": 0-10,
  "overall_score": 0-10,
  "issues": ["..."],
  "suggestions": ["..."],
  "verdict": "通过" 或 "需要改进"
}"""
        },
        "summarization_specialist": {
            "required_format": "Markdown",
            "note": "返回Markdown格式的文本报告，不需要JSON"
        }
    }
    
    available_placeholders = agent_placeholders.get(payload.agent_id, ["user_query", "task_description"])
    format_req = format_requirements.get(payload.agent_id, {})
    
    # 占位符描述映射
    placeholder_descriptions = {
        "user_query": "用户查询内容",
        "task_description": "当前任务描述",
        "analysis_context": "分析上下文（检索结果、待分析内容）",
        "full_context": "完整上下文（所有智能体的结果汇总）",
        "final_answer": "最终答案（用于验证）",
    }
    
    # 构建占位符说明
    placeholder_help = "\n".join([
        f"- {{{p}}} - {placeholder_descriptions.get(p, '占位符')}" 
        for p in available_placeholders
    ])
    
    # 构建格式要求说明
    format_help = ""
    if format_req:
        if format_req.get("required_format") == "JSON":
            format_help = f"""
## 输出格式要求（重要！）

**必须返回JSON格式**，结构必须包含以下字段：
{', '.join(format_req.get('required_fields', []))}

JSON结构示例：
{format_req.get('json_structure', '')}

**重要提示**：
- 必须在prompt中明确要求："以 JSON 格式输出结果："
- 必须在prompt末尾强调："只返回 JSON，不要其他解释。"
- JSON字段名必须与上述结构完全匹配
"""
        elif format_req.get("required_format") == "Markdown":
            format_help = """
## 输出格式要求

**返回Markdown格式的文本报告**，不需要JSON格式。
- 使用清晰的 Markdown 格式
- 合理的标题层级（# ## ###）
- 结构化组织内容
"""
    else:
        format_help = """
## 输出格式要求

根据智能体职责确定输出格式，确保格式清晰、结构化。
"""
    
    generation_prompt = f"""你是一个专业的Prompt工程师。请根据用户的需求，为智能体生成一个高质量的Prompt模板。

## 智能体信息
- 名称：{agent_info.get('name', '未知')}
- ID：{payload.agent_id}
- 描述：{agent_info.get('description', '无')}

## 用户需求
{payload.user_requirement}
{style_note}{format_note}

## 可用的占位符（必须使用单花括号）

{placeholder_help}

**占位符使用规则**：
1. 必须使用单花括号格式：{{variable}}，不要使用双花括号
2. 只能使用上述列出的占位符
3. 根据智能体类型选择合适的占位符
4. 不要使用未列出的占位符

{format_help}

## 生成要求
1. Prompt应该清晰、具体、可执行
2. 包含明确的角色定义、任务描述、输出要求
3. 使用上述列出的占位符以便动态替换
4. 如果用户需求不够具体，可以适当补充合理的假设
5. 确保Prompt符合该智能体的职责范围
6. 保持专业但易懂的语言风格
7. 如果智能体需要JSON格式，必须在prompt中明确要求并指定结构

## 输出格式
请直接输出生成的Prompt内容，不要包含任何解释、说明文字或代码块标记。Prompt应该可以直接使用。

现在请生成Prompt："""

    try:
        # 调用LLM生成prompt
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的Prompt工程师，擅长将用户需求转化为高质量的Prompt模板。你生成的Prompt应该结构清晰、指令明确、易于执行。"
            },
            {
                "role": "user",
                "content": generation_prompt
            }
        ]
        
        generated_prompt, _ = await invoke_llm(
            messages=messages,
            settings=settings,
            temperature=0.7,
        )
        
        # 清理生成的内容（移除可能的markdown代码块标记）
        generated_prompt = generated_prompt.strip()
        if generated_prompt.startswith("```"):
            # 移除代码块标记
            lines = generated_prompt.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            generated_prompt = "\n".join(lines).strip()
        
        # 验证生成的prompt
        validation_result = validate_prompt_template(
            prompt=generated_prompt,
            agent_id=payload.agent_id,
            available_placeholders=available_placeholders,
            format_requirements=format_req
        )
        
        # 生成建议的模板名称和描述
        name_suggestion = f"AI生成-{agent_info.get('name', '智能体')}"
        description_suggestion = f"根据需求自动生成：{payload.user_requirement[:50]}{'...' if len(payload.user_requirement) > 50 else ''}"
        
        return {
            "success": True,
            "generated_prompt": generated_prompt,
            "suggested_name": name_suggestion,
            "suggested_description": description_suggestion,
            "agent_id": payload.agent_id,
            "agent_name": agent_info.get('name', '未知'),
            "validation": validation_result,
        }
        
    except Exception as e:
        logger.error(f"生成Prompt失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"生成Prompt失败: {str(e)}"
        )


@app.post("/agents/{agent_id}/execute", response_model=ChatResponse)
async def execute_custom_agent_endpoint(
    agent_id: str,
    payload: AgentExecuteRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> ChatResponse:
    """执行自定义Agent"""
    agent_config = get_agent_config_by_id(session, agent_id)
    if agent_config is None:
        raise HTTPException(status_code=404, detail="Agent配置不存在")
    
    if not agent_config.is_active:
        raise HTTPException(status_code=400, detail="Agent配置未激活")
    
    tool_records = []
    if payload.use_tools:
        tool_records = list_tools(session, include_inactive=False)
    
    result = await execute_custom_agent(
        agent_config=agent_config,
        user_query=payload.messages[-1].content if payload.messages else "",
        settings=settings,
        session=session,
        tool_records=tool_records,
        conversation_history=[msg.model_dump() for msg in payload.messages],
    )
    
    contexts = [
        ContextSnippet(
            document_id=ctx.get("document_id"),
            original_name=ctx.get("original_name"),
            content=ctx.get("content", "")[:500]
        )
        for ctx in result.get("retrieved_contexts", [])
    ]
    
    tool_results = [
        ToolExecutionResult(
            tool_id=tr.get("tool_id", ""),
            tool_name=tr.get("tool_name", ""),
            output=tr.get("output", "")
        )
        for tr in result.get("tool_results", [])
    ]
    
    return ChatResponse(
        reply=result.get("final_answer", "执行完成"),
        raw={"success": result.get("success", False), "thread_id": result.get("thread_id")},
        contexts=contexts,
        tool_results=tool_results,
    )


@app.post("/agents/{agent_id}/execute/stream")
async def execute_custom_agent_stream(
    agent_id: str,
    payload: AgentExecuteRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """流式执行自定义Agent"""
    agent_config = get_agent_config_by_id(session, agent_id)
    if agent_config is None:
        raise HTTPException(status_code=404, detail="Agent配置不存在")
    
    if not agent_config.is_active:
        raise HTTPException(status_code=400, detail="Agent配置未激活")
    
    tool_records = []
    if payload.use_tools:
        tool_records = list_tools(session, include_inactive=False)
    
    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            yield format_sse("status", {"stage": "started", "mode": "custom_agent", "agent_name": agent_config.name})
            
            async for event in stream_custom_agent(
                agent_config=agent_config,
                user_query=payload.messages[-1].content if payload.messages else "",
                settings=settings,
                session=session,
                tool_records=tool_records,
                conversation_history=[msg.model_dump() for msg in payload.messages],
            ):
                event_type = event.get("event", "unknown")
                
                if event_type == "node_output":
                    node_name = event.get("node", "")
                    node_data = event.get("data", {})
                    
                    yield format_sse("agent_node", {
                        "node": node_name,
                        "status": "completed",
                        "data": node_data,
                    })
                    
                    if "thoughts" in node_data:
                        for thought in node_data.get("thoughts", []):
                            yield format_sse("agent_thought", {
                                "node": node_name,
                                "thought": thought,
                            })
                    
                    if "observations" in node_data:
                        for observation in node_data.get("observations", []):
                            yield format_sse("agent_observation", {
                                "node": node_name,
                                "observation": observation,
                            })
                    
                    if "tool_results" in node_data:
                        for tool_result in node_data.get("tool_results", []):
                            yield format_sse("tool_result", tool_result)
                    
                    if "final_answer" in node_data and node_data["final_answer"]:
                        yield format_sse("assistant_final", {
                            "content": node_data["final_answer"]
                        })
                
                elif event_type == "final_answer":
                    # 直接发送最终答案事件
                    yield format_sse("assistant_final", {
                        "content": event.get("content", "")
                    })
                
                elif event_type == "completed":
                    yield format_sse("completed", {
                        "thread_id": event.get("thread_id"),
                    })
        
        except Exception as e:
            logger.exception("自定义Agent流式执行失败: %s", e)
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/test-upload")
async def test_upload(files: List[UploadFile] = File(...)):
    """测试文件上传接口"""
    logger.info(f"🧪 [测试接口] 收到 {len(files)} 个文件")
    for idx, f in enumerate(files, 1):
        content = await f.read()
        logger.info(f"   文件 {idx}: {f.filename}, 大小: {len(content)} bytes")
    return {"status": "ok", "files": len(files)}


@app.post("/chat/agent/stream-with-files")
async def chat_with_files_stream(
    message: str = Form(""),
    use_knowledge_base: bool = Form(True),
    use_tools: bool = Form(True),
    session_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """
    支持文件上传的 Agent 对话（流式）- 真正的 RAG
    
    上传的文件会被解析、向量化并存储到知识库，然后基于文件内容回答问题
    """
    logger.info(f"=" * 80)
    logger.info(f"📁 [文件上传 API] 收到请求")
    logger.info(f"📝 消息: {message}")
    logger.info(f"📚 使用知识库: {use_knowledge_base}")
    logger.info(f"🔧 使用工具: {use_tools}")
    logger.info(f"📁 文件数量: {len(files)}")
    logger.info(f"🆔 会话ID: {session_id}")
    logger.info(f"👤 用户ID: {user_id}")
    for idx, f in enumerate(files, 1):
        logger.info(f"   文件 {idx}: {f.filename} ({f.content_type})")
    logger.info(f"=" * 80)
    
    # 获取或生成 session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"🆔 生成新的 session_id: {session_id}")
    
    file_processor = FileProcessor()
    processed_files = []
    
    # 处理每个上传的文件
    for upload_file in files:
        try:
            logger.info(f"📄 处理文件: {upload_file.filename}")
            
            # 读取文件内容
            file_content = await upload_file.read()
            
            # 保存文件
            file_path = file_processor.save_file(file_content, upload_file.filename)
            
            # 提取文本
            text_content = file_processor.extract_text(file_path)
            
            if text_content and not text_content.startswith("["):
                logger.info(f"📝 文本内容长度: {len(text_content)} 字符")
                
                try:
                    # 文本分块
                    logger.info(f"🔄 开始文本分块...")
                    chunks = chunk_text(text_content, chunk_size=500, overlap=50)
                    logger.info(f"📦 文本分块完成: {len(chunks)} 个块")
                except Exception as chunk_error:
                    logger.error(f"❌ 文本分块失败: {chunk_error}", exc_info=True)
                    processed_files.append({
                        "filename": upload_file.filename,
                        "error": f"文本分块失败: {str(chunk_error)}"
                    })
                    continue
                
                # 向量化并存储到知识库
                doc_id = f"file_{upload_file.filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                successful_chunks = 0
                logger.info(f"🔄 开始向量化存储到知识库...")
                
                for i, chunk in enumerate(chunks):
                    try:
                        chunk_metadata = {
                            "source": upload_file.filename,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "upload_time": datetime.now().isoformat()
                        }
                        
                        logger.debug(f"💾 向量化块 {i+1}/{len(chunks)}: {len(chunk)} 字符")
                        
                        ingest_text_chunk(
                            session=session,
                            settings=settings,
                            doc_id=f"{doc_id}_chunk_{i}",
                            content=chunk,
                            metadata=chunk_metadata
                        )
                        successful_chunks += 1
                        
                        if (i + 1) % 10 == 0:
                            logger.info(f"💾 已向量化 {i + 1}/{len(chunks)} 个块...")
                    except Exception as chunk_error:
                        logger.error(f"❌ 块 {i} 向量化失败: {chunk_error}", exc_info=True)
                
                logger.info(f"✅ 文件已向量化: {upload_file.filename}, 成功 {successful_chunks}/{len(chunks)} 个块")
                
                processed_files.append({
                    "filename": upload_file.filename,
                    "chunks": len(chunks),
                    "characters": len(text_content)
                })
            else:
                logger.warning(f"⚠️ 文件无法解析: {upload_file.filename}")
                processed_files.append({
                    "filename": upload_file.filename,
                    "error": text_content
                })
                
        except Exception as e:
            logger.error(f"❌ 文件处理失败 {upload_file.filename}: {e}", exc_info=True)
            processed_files.append({
                "filename": upload_file.filename,
                "error": str(e)
            })
    
    logger.info(f"📊 文件处理汇总: 总共 {len(files)} 个文件, 成功 {len([f for f in processed_files if 'error' not in f])} 个")
    
    # 构建用户查询
    user_query = message if message else "请分析这些文件的内容并总结关键信息"
    
    # 获取工具列表
    tool_records = list_tools(session)
    if not use_tools:
        tool_records = []
    
    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            # 发送文件处理结果
            yield format_sse("files_processed", {
                "files": processed_files,
                "total": len(files)
            })
            
            # 发送状态事件，包含 session_id 以便前端保存
            yield format_sse("status", {
                "stage": "started", 
                "mode": "langgraph_agent_with_files",
                "session_id": session_id
            })
            
            # 流式执行 LangGraph Agent（强制启用知识库）
            async for event in stream_agent(
                user_query=user_query,
                settings=settings,
                session=session,
                tool_records=tool_records,
                use_knowledge_base=True,  # 强制启用，因为文件已存入知识库
                conversation_history=[{"role": "user", "content": user_query}],
                session_id=session_id,
                user_id=user_id,
            ):
                event_type = event.get("event", "unknown")
                
                if event_type == "node_output":
                    node_name = event.get("node", "")
                    node_data = event.get("data", {})
                    
                    yield format_sse("agent_node", {
                        "node": node_name,
                        "status": "completed",
                        "data": node_data,
                        "timestamp": event.get("timestamp")
                    })
                    
                    if "thoughts" in node_data and node_data["thoughts"]:
                        for thought in node_data["thoughts"]:
                            yield format_sse("agent_thought", {
                                "node": node_name,
                                "thought": thought,
                                "timestamp": event.get("timestamp")
                            })
                    
                    if "observations" in node_data and node_data["observations"]:
                        for obs in node_data["observations"]:
                            yield format_sse("agent_observation", {
                                "node": node_name,
                                "observation": obs,
                                "timestamp": event.get("timestamp")
                            })
                    
                    if "tool_results" in node_data:
                        for tool_result in node_data["tool_results"]:
                            yield format_sse("tool_result", {
                                "tool_name": tool_result.get("tool_name"),
                                "output": tool_result.get("output"),
                                "timestamp": event.get("timestamp")
                            })
                    
                    if "contexts" in node_data and node_data["contexts"]:
                        yield format_sse("context", {
                            "items": node_data["contexts"],
                            "count": len(node_data["contexts"])
                        })
                    
                    if node_name == "synthesizer" and "final_answer" in node_data:
                        logger.info("📤 已发送最终答案到前端，长度: %d", len(node_data["final_answer"]))
                        yield format_sse("assistant_final", {
                            "content": node_data["final_answer"]
                        })
                
                elif event_type == "final_answer":
                    final_content = event.get("content", "")
                    yield format_sse("assistant_final", {
                        "content": final_content
                    })
                
                elif event_type == "error":
                    yield format_sse("error", {
                        "message": event.get("message", "Unknown error")
                    })
            
            logger.info("📤 已发送完成事件到前端")
            yield format_sse("completed", {
                "status": "success",
                "files_processed": len(processed_files)
            })
            
        except Exception as e:
            logger.error(f"❌ 流式处理错误: {e}", exc_info=True)
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


class ConversationMessage(BaseModel):
    """对话消息模型（包含可选的元数据）"""

    id: str
    user_id: Optional[str]
    session_id: str
    role: str
    content: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


@app.get("/conversation/{session_id}/history", response_model=List[ConversationMessage])
async def get_conversation_history_api(
    session_id: str,
    user_id: Optional[str] = None,
    limit: int = 20,
    session: Session = Depends(get_db_session),
) -> List[ConversationMessage]:
    """
    获取指定会话的对话历史
    """
    history = get_conversation_history(
        session=session,
        session_id=session_id,
        limit=limit,
        user_id=user_id,
    )

    messages: List[ConversationMessage] = []
    for msg in history:
        metadata: Optional[Dict[str, Any]] = None
        extra = getattr(msg, "extra_metadata", None)
        if extra:
            try:
                metadata = json.loads(extra)
            except Exception:
                metadata = None

        messages.append(
            ConversationMessage(
                id=msg.id,
                user_id=msg.user_id,
                session_id=msg.session_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                metadata=metadata,
            )
        )

    return messages


# ==================== 记忆系统 API ====================

class MemoryItem(BaseModel):
    """记忆项模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_id: Optional[str]
    session_id: Optional[str]
    memory_type: str
    content: str
    importance_score: int
    tags: Optional[list[str]] = None
    access_count: int
    last_accessed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class MemoryCreate(BaseModel):
    """创建记忆请求"""
    content: str
    memory_type: str  # fact/preference/event/relationship
    importance_score: int = 50
    tags: Optional[list[str]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    """更新记忆请求"""
    content: Optional[str] = None
    importance_score: Optional[int] = None
    tags: Optional[list[str]] = None


class SessionConfigModel(BaseModel):
    """会话配置模型"""
    model_config = ConfigDict(from_attributes=True)
    
    session_id: str
    user_id: Optional[str] = None
    share_memory: bool = True
    auto_extract: bool = True


class UserPreferencesModel(BaseModel):
    """用户偏好设置模型"""
    model_config = ConfigDict(from_attributes=True)
    
    user_id: str = "default"
    default_share_memory: bool = True
    default_auto_extract: bool = True


@app.get("/api/memories/search", response_model=List[MemoryItem])
async def search_memories_api(
    query: Optional[str] = None,
    memory_type: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 20,
    session: Session = Depends(get_db_session),
) -> List[MemoryItem]:
    """搜索记忆"""
    memories = search_memories(
        session=session,
        query=query,
        memory_type=memory_type,
        user_id=user_id,
        session_id=session_id,
        limit=limit,
    )
    
    # 解析 tags 和 metadata
    result = []
    for mem in memories:
        tags = None
        if mem.tags:
            try:
                tags = json.loads(mem.tags)
            except:
                pass
        
        result.append(MemoryItem(
            id=mem.id,
            user_id=mem.user_id,
            session_id=mem.session_id,
            memory_type=mem.memory_type,
            content=mem.content,
            importance_score=mem.importance_score,
            tags=tags,
            access_count=mem.access_count,
            last_accessed_at=mem.last_accessed_at,
            created_at=mem.created_at,
            updated_at=mem.updated_at,
        ))
    
    return result


@app.get("/api/memories/{memory_id}", response_model=MemoryItem)
async def get_memory_api(
    memory_id: str,
    session: Session = Depends(get_db_session),
) -> MemoryItem:
    """获取单条记忆"""
    memory = get_memory_by_id(session, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    
    tags = None
    if memory.tags:
        try:
            tags = json.loads(memory.tags)
        except:
            pass
    
    return MemoryItem(
        id=memory.id,
        user_id=memory.user_id,
        session_id=memory.session_id,
        memory_type=memory.memory_type,
        content=memory.content,
        importance_score=memory.importance_score,
        tags=tags,
        access_count=memory.access_count,
        last_accessed_at=memory.last_accessed_at,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@app.post("/api/memories", response_model=MemoryItem)
async def create_memory_api(
    memory_data: MemoryCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> MemoryItem:
    """创建新记忆"""
    from .memory_service import add_memory_to_vectorstore
    
    memory = create_memory(
        session=session,
        content=memory_data.content,
        memory_type=memory_data.memory_type,
        importance_score=memory_data.importance_score,
        user_id=memory_data.user_id,
        session_id=memory_data.session_id,
        tags=memory_data.tags,
    )
    
    # 向量化
    add_memory_to_vectorstore(
        memory_id=memory.id,
        content=memory.content,
        memory_type=memory.memory_type,
        user_id=memory.user_id,
        session_id=memory.session_id,
        settings=settings,
    )
    
    tags = None
    if memory.tags:
        try:
            tags = json.loads(memory.tags)
        except:
            pass
    
    return MemoryItem(
        id=memory.id,
        user_id=memory.user_id,
        session_id=memory.session_id,
        memory_type=memory.memory_type,
        content=memory.content,
        importance_score=memory.importance_score,
        tags=tags,
        access_count=memory.access_count,
        last_accessed_at=memory.last_accessed_at,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@app.put("/api/memories/{memory_id}", response_model=MemoryItem)
async def update_memory_api(
    memory_id: str,
    memory_data: MemoryUpdate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> MemoryItem:
    """更新记忆"""
    from .memory_service import update_memory_in_vectorstore
    
    memory = update_memory(
        session=session,
        memory_id=memory_id,
        content=memory_data.content,
        importance_score=memory_data.importance_score,
        tags=memory_data.tags,
    )
    
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    
    # 如果内容更新，需要更新向量
    if memory_data.content:
        update_memory_in_vectorstore(
            memory_id=memory.id,
            content=memory.content,
            memory_type=memory.memory_type,
            user_id=memory.user_id,
            session_id=memory.session_id,
            settings=settings,
        )
    
    tags = None
    if memory.tags:
        try:
            tags = json.loads(memory.tags)
        except:
            pass
    
    return MemoryItem(
        id=memory.id,
        user_id=memory.user_id,
        session_id=memory.session_id,
        memory_type=memory.memory_type,
        content=memory.content,
        importance_score=memory.importance_score,
        tags=tags,
        access_count=memory.access_count,
        last_accessed_at=memory.last_accessed_at,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@app.delete("/api/memories/{memory_id}")
async def delete_memory_api(
    memory_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """删除记忆"""
    success = delete_memory_complete(session, memory_id, settings)
    
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在")
    
    return {"success": True, "message": "记忆已删除"}


@app.delete("/api/memories/batch")
async def delete_memories_batch_api(
    memory_ids: List[str],
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """批量删除记忆"""
    from .memory_service import delete_memory_from_vectorstore
    
    # 删除向量
    for memory_id in memory_ids:
        delete_memory_from_vectorstore(memory_id, settings)
    
    # 删除数据库记录
    count = delete_memories_batch(session, memory_ids)
    
    return {"success": True, "deleted_count": count}


@app.get("/api/sessions/{session_id}/config", response_model=SessionConfigModel)
async def get_session_config_api(
    session_id: str,
    session: Session = Depends(get_db_session),
) -> SessionConfigModel:
    """获取会话配置"""
    config = get_session_config(session, session_id)
    
    if not config:
        # 创建默认配置
        config = update_session_config(
            session=session,
            session_id=session_id,
            share_memory=True,
            auto_extract=True,
        )
    
    return SessionConfigModel.model_validate(config)


@app.put("/api/sessions/{session_id}/config", response_model=SessionConfigModel)
async def update_session_config_api(
    session_id: str,
    config_data: SessionConfigModel,
    session: Session = Depends(get_db_session),
) -> SessionConfigModel:
    """更新会话配置"""
    config = update_session_config(
        session=session,
        session_id=session_id,
        share_memory=config_data.share_memory,
        auto_extract=config_data.auto_extract,
        user_id=config_data.user_id,
    )
    
    return SessionConfigModel.model_validate(config)


@app.post("/api/memories/extract")
async def extract_memories_api(
    conversation_text: str,
    session_id: str,
    user_id: Optional[str] = None,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """手动触发记忆提取"""
    memories = await extract_memories_from_conversation(
        conversation_text=conversation_text,
        settings=settings,
        session_id=session_id,
        user_id=user_id,
    )
    
    return {
        "success": True,
        "extracted_count": len(memories),
        "memories": memories,
    }


@app.post("/api/memories/reindex")
async def reindex_memories_api(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    重新索引所有记忆到向量库
    修复旧记忆的 metadata 格式问题
    """
    from .memory_service import add_memory_to_vectorstore
    
    try:
        # 获取所有记忆
        all_memories = search_memories(session=session, limit=10000)
        
        reindexed_count = 0
        failed_count = 0
        
        for memory in all_memories:
            try:
                # 重新添加到向量库（使用新的 metadata 格式）
                add_memory_to_vectorstore(
                    memory_id=memory.id,
                    content=memory.content,
                    memory_type=memory.memory_type,
                    user_id=memory.user_id,
                    session_id=memory.session_id,
                    settings=settings,
                )
                reindexed_count += 1
            except Exception as e:
                logger.error(f"重新索引记忆 {memory.id} 失败: {e}")
                failed_count += 1
        
        logger.info(f"✅ 记忆重新索引完成：成功={reindexed_count}, 失败={failed_count}")
        
        return {
            "success": True,
            "reindexed_count": reindexed_count,
            "failed_count": failed_count,
            "total_memories": len(all_memories),
        }
    
    except Exception as e:
        logger.error(f"记忆重新索引失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重新索引失败: {str(e)}")


@app.post("/api/memories/deduplicate")
async def deduplicate_memories_api(
    threshold: float = 0.7,
    dry_run: bool = False,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    清理重复的记忆
    
    Args:
        threshold: 相似度阈值（0-1），默认 0.7
        dry_run: 仅检测不删除，默认 False
    """
    from .memory_service import (
        calculate_text_similarity,
        calculate_jaccard_similarity,
        delete_memory_complete,
    )
    
    try:
        # 获取所有记忆
        all_memories = search_memories(session=session, limit=10000)
        
        duplicates = []
        processed = set()
        
        # 按类型分组
        by_type = {}
        for mem in all_memories:
            if mem.memory_type not in by_type:
                by_type[mem.memory_type] = []
            by_type[mem.memory_type].append(mem)
        
        # 检测每个类型中的重复
        for memory_type, memories in by_type.items():
            for i, mem1 in enumerate(memories):
                if mem1.id in processed:
                    continue
                
                for mem2 in memories[i+1:]:
                    if mem2.id in processed:
                        continue
                    
                    # 计算相似度
                    text_sim = calculate_text_similarity(mem1.content, mem2.content)
                    jaccard_sim = calculate_jaccard_similarity(mem1.content, mem2.content)
                    combined_sim = text_sim * 0.6 + jaccard_sim * 0.4
                    
                    if combined_sim >= threshold:
                        # 保留较早创建的或访问次数更多的
                        if mem1.access_count >= mem2.access_count:
                            keep, remove = mem1, mem2
                        else:
                            keep, remove = mem2, mem1
                        
                        duplicates.append({
                            "keep_id": keep.id,
                            "keep_content": keep.content[:100],
                            "keep_access_count": keep.access_count,
                            "remove_id": remove.id,
                            "remove_content": remove.content[:100],
                            "similarity": round(combined_sim, 3)
                        })
                        
                        processed.add(remove.id)
        
        # 删除重复记忆
        deleted_count = 0
        if not dry_run:
            for dup in duplicates:
                try:
                    delete_memory_complete(session, dup["remove_id"], settings)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"删除重复记忆 {dup['remove_id']} 失败: {e}")
        
        result = {
            "success": True,
            "total_memories": len(all_memories),
            "duplicates_found": len(duplicates),
            "deleted_count": deleted_count if not dry_run else 0,
            "dry_run": dry_run,
            "duplicates": duplicates[:20],  # 只返回前20个
        }
        
        if dry_run:
            result["message"] = f"检测到 {len(duplicates)} 对重复记忆，使用 dry_run=false 来删除"
        else:
            result["message"] = f"成功删除 {deleted_count} 条重复记忆"
        
        logger.info(f"✅ 记忆去重完成：找到 {len(duplicates)} 对，删除 {deleted_count} 条")
        
        return result
    
    except Exception as e:
        logger.error(f"记忆去重失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"去重失败: {str(e)}")


# ==================== 用户偏好设置 API ====================

@app.get("/api/preferences", response_model=UserPreferencesModel)
async def get_preferences_api(
    user_id: str = "default",
    session: Session = Depends(get_db_session),
) -> UserPreferencesModel:
    """获取用户偏好设置"""
    prefs = get_user_preferences(session, user_id)
    
    if not prefs:
        # 创建默认偏好
        prefs = update_user_preferences(
            session=session,
            user_id=user_id,
            default_share_memory=True,
            default_auto_extract=True,
        )
    
    return UserPreferencesModel.model_validate(prefs)


@app.put("/api/preferences", response_model=UserPreferencesModel)
async def update_preferences_api(
    prefs_data: UserPreferencesModel,
    session: Session = Depends(get_db_session),
) -> UserPreferencesModel:
    """
    更新用户偏好设置
    修改后，所有新建的会话都将使用这些默认设置
    """
    prefs = update_user_preferences(
        session=session,
        user_id=prefs_data.user_id,
        default_share_memory=prefs_data.default_share_memory,
        default_auto_extract=prefs_data.default_auto_extract,
    )
    
    logger.info(
        f"✅ 用户偏好已更新: user_id={prefs_data.user_id}, "
        f"share_memory={prefs_data.default_share_memory}, "
        f"auto_extract={prefs_data.default_auto_extract}"
    )
    
    return UserPreferencesModel.model_validate(prefs)


# ==================== 会话管理 API ====================

class ConversationSession(BaseModel):
    """会话摘要信息"""
    model_config = ConfigDict(from_attributes=True)
    
    session_id: str
    title: str
    message_count: int
    first_message_time: Optional[str]
    last_message_time: Optional[str]
    preview: str


@app.get("/conversations", response_model=List[ConversationSession])
async def list_conversations(
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_db_session),
) -> List[ConversationSession]:
    """
    列出所有会话列表（按时间排序）
    """
    sessions = list_conversation_sessions(
        session=session,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    
    return [ConversationSession.model_validate(s) for s in sessions]


@app.get("/conversations/search", response_model=List[ConversationSession])
async def search_conversations(
    q: str,
    user_id: Optional[str] = None,
    limit: int = 20,
    session: Session = Depends(get_db_session),
) -> List[ConversationSession]:
    """
    搜索会话（基于对话内容）
    """
    sessions = search_conversation_sessions(
        session=session,
        query=q,
        user_id=user_id,
        limit=limit,
    )
    
    return [ConversationSession.model_validate(s) for s in sessions]


@app.delete("/conversation/{session_id}")
async def delete_conversation_api(
    session_id: str,
    user_id: Optional[str] = None,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    删除整个会话
    """
    count = delete_conversation_session(
        session=session,
        session_id=session_id,
        user_id=user_id,
    )
    
    return {
        "success": True,
        "deleted_count": count,
        "session_id": session_id,
    }


@app.delete("/conversation/message/{message_id}")
async def delete_message_api(
    message_id: str,
    user_id: Optional[str] = None,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    删除单条消息
    """
    success = delete_conversation_message(
        session=session,
        message_id=message_id,
        user_id=user_id,
    )
    
    return {
        "success": success,
        "message_id": message_id,
    }


# ==================== 多智能体系统 API ====================

class MultiAgentChatRequest(BaseModel):
    """多智能体对话请求"""
    messages: List[Message]
    use_knowledge_base: bool = Field(default=True, description="是否使用知识库")
    use_tools: bool = Field(default=True, description="是否使用工具")
    execution_mode: str = Field(default="sequential", description="执行模式：sequential 或 parallel")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    # 记忆控制字段
    memory_mode: Optional[str] = Field(
        default="session", description="记忆模式：'global'（全局记忆）或 'session'（独立记忆）"
    )
    share_memory: Optional[bool] = Field(
        default=None, description="是否共享记忆（显式控制，优先级最高）"
    )


class MultiAgentChatResponse(BaseModel):
    """多智能体对话响应"""
    reply: str
    orchestrator_plan: str
    sub_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    agent_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    thoughts: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    quality_score: float = 0.0
    thread_id: str
    session_id: str


@app.post("/chat/multi-agent", response_model=MultiAgentChatResponse)
async def chat_with_multi_agent(
    payload: MultiAgentChatRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> MultiAgentChatResponse:
    """
    使用多智能体系统处理对话
    
    特点：
    - 多个专家智能体协作
    - 任务自动分解
    - 并行/串行执行
    - 结果智能汇总
    """
    logger.info("🤖🤖🤖 [多智能体系统] 开始处理请求")
    
    # 导入多智能体模块
    from .multi_agent import run_multi_agent
    
    # 获取可用工具
    tool_records = []
    if payload.use_tools:
        tool_records = list_tools(session, include_inactive=False)
    
    # 获取或生成 session_id，并根据请求更新会话记忆配置
    session_id = payload.session_id or str(uuid.uuid4())
    current_config = get_session_config(session, session_id)
    share_memory_value = False
    if payload.share_memory is not None:
        share_memory_value = payload.share_memory
    elif payload.memory_mode == 'global':
        share_memory_value = True
    elif current_config:
        share_memory_value = current_config.share_memory
    update_session_config(
        session=session,
        session_id=session_id,
        share_memory=share_memory_value,
        user_id=payload.user_id,
    )
    
    # 运行多智能体系统
    result = await run_multi_agent(
        user_query=payload.messages[-1].content if payload.messages else "",
        settings=settings,
        session=session,
        tool_records=tool_records,
        use_knowledge_base=payload.use_knowledge_base,
        conversation_history=[msg.model_dump() for msg in payload.messages],
        session_id=session_id,
        user_id=payload.user_id,
        execution_mode=payload.execution_mode,
    )
    
    return MultiAgentChatResponse(
        reply=result.get("final_answer", "未能生成答案"),
        orchestrator_plan=result.get("orchestrator_plan", ""),
        sub_tasks=result.get("sub_tasks", []),
        agent_results=result.get("agent_results", {}),
        thoughts=result.get("thoughts", []),
        observations=result.get("observations", []),
        quality_score=result.get("quality_score", 0.0),
        thread_id=result.get("thread_id", ""),
        session_id=result.get("session_id", ""),
    )


@app.post("/chat/multi-agent/stream")
async def chat_with_multi_agent_stream(
    payload: MultiAgentChatRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """
    使用多智能体系统处理对话（流式）
    
    实时返回各智能体的执行过程
    """
    logger.info("🌊🤖🤖🤖 [多智能体系统-流式] 开始处理")
    
    from .multi_agent import stream_multi_agent
    
    tool_records = []
    if payload.use_tools:
        tool_records = list_tools(session, include_inactive=False)
    
    session_id = payload.session_id or str(uuid.uuid4())
    
    # 🔒 根据前端请求设置会话的记忆配置
    from .database import get_session_config, SessionConfig
    session_config = get_session_config(session, session_id)
    
    # 确定是否共享记忆
    share_memory_value = False  # 默认：独立记忆
    if payload.share_memory is not None:
        share_memory_value = payload.share_memory
    elif payload.memory_mode == 'global':
        share_memory_value = True
    elif session_config:
        share_memory_value = session_config.share_memory
    
    # 创建或更新会话配置
    session_config = update_session_config(
        session=session,
        session_id=session_id,
        share_memory=share_memory_value,
        user_id=payload.user_id,
    )
    logger.info(f"🔒 多智能体会话 {session_id} 记忆模式: {'全局共享' if session_config.share_memory else '独立隔离'}")
    
    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            yield format_sse("status", {"stage": "started", "mode": "multi_agent"})
            
            # 流式执行多智能体系统
            async for event in stream_multi_agent(
                user_query=payload.messages[-1].content if payload.messages else "",
                settings=settings,
                session=session,
                tool_records=tool_records,
                use_knowledge_base=payload.use_knowledge_base,
                conversation_history=[msg.model_dump() for msg in payload.messages],
                session_id=session_id,
                user_id=payload.user_id,
                execution_mode=payload.execution_mode,
            ):
                event_type = event.get("event", "unknown")
                
                # 协调器事件
                if event_type == "orchestrator_plan":
                    yield format_sse("orchestrator_plan", {
                        "plan": event.get("data", {}).get("orchestrator_plan", ""),
                        "timestamp": event.get("timestamp"),
                    })
                
                # 智能体执行事件
                elif event_type == "agent_execution":
                    node_name = event.get("node", "")
                    node_data = event.get("data", {})
                    
                    yield format_sse("agent_execution", {
                        "agent": node_name,
                        "data": node_data,
                        "timestamp": event.get("timestamp"),
                    })
                    
                    # 如果有最终答案，发送
                    if "final_answer" in node_data and node_data["final_answer"]:
                        yield format_sse("assistant_final", {
                            "content": node_data["final_answer"],
                        })
                        logger.info(f"📤 多智能体模式：已发送最终答案，长度: {len(node_data['final_answer'])}")
                
                # 完成事件
                elif event_type == "completed":
                    yield format_sse("completed", {
                        "thread_id": event.get("thread_id"),
                        "timestamp": event.get("timestamp"),
                    })
            
        except Exception as e:
            logger.error(f"多智能体系统流式执行失败: {e}", exc_info=True)
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/multi-agent/agents")
async def list_multi_agent_agents() -> List[Dict[str, Any]]:
    """
    列出所有可用的智能体
    """
    from .agent_roles import list_available_agents
    return list_available_agents()
