from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Literal

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
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


def ensure_directories(settings: Settings) -> None:
    for path in (settings.data_dir, settings.chroma_dir, settings.sqlite_path.parent):
        Path(path).mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup() -> None:
    try:
        settings = get_settings()
        logger.info("数据目录: %s", settings.data_dir)
        logger.info("数据库路径: %s", settings.sqlite_path)
        logger.info("Chroma 目录: %s", settings.chroma_dir)
        ensure_directories(settings)
        init_engine(settings.sqlite_path)
        logger.info("数据库初始化成功")
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
