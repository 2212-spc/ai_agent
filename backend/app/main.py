from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Literal

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
from .database import AgentConfig, get_agent_config_by_id, list_agent_configs


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
        try:
            logger.info("🔄 预加载嵌入模型...")
            from .rag_service import get_embeddings
            embeddings = get_embeddings()
            test_emb = embeddings.embed_query("预热测试")
            logger.info(f"✅ 嵌入模型已加载 (维度: {len(test_emb)})")
        except Exception as e:
            logger.warning(f"⚠️ 嵌入模型预加载失败: {e}")
            
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
    """
    logger.info("🤖 [LangGraph Agent] 开始处理请求")
    
    # 获取可用工具
    tool_records = select_tool_records(payload, session)
    
    # 运行 LangGraph Agent
    result = await run_agent(
        user_query=payload.messages[-1].content if payload.messages else "",
        settings=settings,
        session=session,
        tool_records=tool_records,
        use_knowledge_base=payload.use_knowledge_base,
        conversation_history=[msg.model_dump() for msg in payload.messages],
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
    
    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            yield format_sse("status", {"stage": "started", "mode": "langgraph_agent"})
            
            # 流式执行 LangGraph Agent
            async for event in stream_agent(
                user_query=payload.messages[-1].content if payload.messages else "",
                settings=settings,
                session=session,
                tool_records=tool_records,
                use_knowledge_base=payload.use_knowledge_base,
                conversation_history=[msg.model_dump() for msg in payload.messages],
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
    for idx, f in enumerate(files, 1):
        logger.info(f"   文件 {idx}: {f.filename} ({f.content_type})")
    logger.info(f"=" * 80)
    
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
            
            yield format_sse("status", {"stage": "started", "mode": "langgraph_agent_with_files"})
            
            # 流式执行 LangGraph Agent（强制启用知识库）
            async for event in stream_agent(
                user_query=user_query,
                settings=settings,
                session=session,
                tool_records=tool_records,
                use_knowledge_base=True,  # 强制启用，因为文件已存入知识库
                conversation_history=[{"role": "user", "content": user_query}],
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
                    yield format_sse("assistant_final", {
                        "content": event.get("content", "")
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
