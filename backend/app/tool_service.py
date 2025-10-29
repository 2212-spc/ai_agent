from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Callable, List

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import Settings
from .database import ToolExecutionLog, ToolRecord
from .rag_service import retrieve_context as rag_retrieve_context, list_documents as rag_list_documents


class ToolExecutionError(Exception):
    """Raised when executing a tool fails."""


@dataclass
class BuiltinToolDefinition:
    key: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any], Settings, Session], str]


def _slugify_filename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "-", filename).strip("-")
    if not sanitized:
        raise ToolExecutionError("文件名仅允许字母、数字、下划线、点或中划线。")
    return sanitized


def _handle_write_note(args: Dict[str, Any], settings: Settings, session: Session) -> str:  # noqa: ARG001
    filename = args.get("filename")
    content = args.get("content")
    if not filename or not isinstance(filename, str):
        raise ToolExecutionError("缺少 filename 字段。")
    if not content or not isinstance(content, str):
        raise ToolExecutionError("缺少 content 字段。")
    safe_name = _slugify_filename(filename)
    notes_dir = settings.data_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    target = notes_dir / safe_name
    target.write_text(content, encoding="utf-8")
    return f"已创建/覆盖笔记 {target} ，长度 {len(content)} 个字符。"


def _handle_list_documents(args: Dict[str, Any], settings: Settings, session: Session) -> str:  # noqa: ARG001
    records = rag_list_documents(session)
    if not records:
        return "知识库当前为空。"
    lines = []
    for record in records:
        lines.append(
            f"- {record.original_name} (ID: {record.id}, 片段: {record.chunk_count})"
        )
    return "知识库文档列表：\n" + "\n".join(lines[:20])


def _handle_search_knowledge(args: Dict[str, Any], settings: Settings, session: Session) -> str:  # noqa: ARG001
    query = args.get("query")
    if not query or not isinstance(query, str):
        raise ToolExecutionError("缺少 query 字段。")
    top_k = args.get("top_k", 3)
    try:
        top_k_int = int(top_k)
    except (TypeError, ValueError):
        top_k_int = 3
    snippets = rag_retrieve_context(query=query, settings=settings, top_k=top_k_int)
    if not snippets:
        return "未在知识库中检索到相关内容。"
    lines = []
    for idx, snippet in enumerate(snippets, start=1):
        name = snippet.original_name or "未知来源"
        lines.append(f"[{idx}] {name}\n{snippet.content}")
    return "检索到以下片段：\n" + "\n\n".join(lines)


def _handle_draw_diagram(args: Dict[str, Any], settings: Settings, session: Session) -> str:  # noqa: ARG001
    filename = args.get("filename")
    diagram_code = args.get("diagram_code")
    diagram_type = args.get("diagram_type", "flowchart")
    
    if not filename or not isinstance(filename, str):
        raise ToolExecutionError("缺少 filename 字段。")
    if not diagram_code or not isinstance(diagram_code, str):
        raise ToolExecutionError("缺少 diagram_code 字段。")
    
    safe_name = _slugify_filename(filename)
    if not safe_name.endswith(".md"):
        safe_name = safe_name.rsplit(".", 1)[0] + ".md" if "." in safe_name else safe_name + ".md"
    
    diagrams_dir = settings.data_dir / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    target = diagrams_dir / safe_name
    
    # 生成完整的 Markdown 内容
    content = f"""# 结构图：{safe_name.rsplit('.', 1)[0]}

## Mermaid 图表

```mermaid
{diagram_code}
```

---

**说明：**
- 使用支持 Mermaid 的编辑器查看（如 Typora、VS Code、在线编辑器）
- 在线查看：https://mermaid.live/
- 图表类型：{diagram_type}
"""
    
    target.write_text(content, encoding="utf-8")
    return f"已创建结构图文件 {target}，包含 {len(diagram_code)} 字符的 Mermaid 代码。可使用 Typora 或访问 https://mermaid.live/ 查看。"


def _handle_web_search(args: Dict[str, Any], settings: Settings, session: Session) -> str:  # noqa: ARG001
    """网页搜索工具 - 使用 DuckDuckGo"""
    query = args.get("query")
    num_results = args.get("num_results", 5)
    
    if not query or not isinstance(query, str):
        raise ToolExecutionError("缺少 query 字段。")
    
    try:
        num_results = int(num_results)
        if num_results < 1 or num_results > 10:
            num_results = 5
    except (TypeError, ValueError):
        num_results = 5
    
    try:
        # 使用 DuckDuckGo HTML 版本
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.post(url, data=params, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            for idx, result in enumerate(soup.select('.result')[:num_results], 1):
                title_elem = result.select_one('.result__a')
                snippet_elem = result.select_one('.result__snippet')
                url_elem = result.select_one('.result__url')
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = url_elem.get_text(strip=True) if url_elem else "无链接"
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else "无摘要"
                    
                    results.append(
                        f"[{idx}] {title}\n"
                        f"    🔗 {link}\n"
                        f"    📄 {snippet}"
                    )
            
            if not results:
                return f"❌ 未找到关于 '{query}' 的搜索结果。建议尝试其他关键词。"
            
            return f"🔍 搜索结果（关键词: {query}）：\n\n" + "\n\n".join(results)
            
    except httpx.TimeoutException:
        raise ToolExecutionError("搜索请求超时，请稍后重试。")
    except httpx.HTTPError as e:
        raise ToolExecutionError(f"搜索服务暂时不可用: {str(e)}")
    except Exception as e:
        raise ToolExecutionError(f"搜索失败: {str(e)}")


def _handle_fetch_webpage(args: Dict[str, Any], settings: Settings, session: Session) -> str:  # noqa: ARG001
    """获取网页内容 - 使用 Jina Reader"""
    url = args.get("url")
    
    if not url or not isinstance(url, str):
        raise ToolExecutionError("缺少 url 字段。")
    
    # 验证 URL 格式
    if not url.startswith(("http://", "https://")):
        raise ToolExecutionError("URL 必须以 http:// 或 https:// 开头。")
    
    try:
        # 使用 Jina Reader API - 自动转换为 Markdown
        jina_url = f"https://r.jina.ai/{url}"
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(jina_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Return-Format": "markdown"
            })
            response.raise_for_status()
            
            content = response.text.strip()
            
            # 限制长度避免 token 过多
            max_length = 8000
            if len(content) > max_length:
                content = content[:max_length] + "\n\n...(内容过长，已截断)"
            
            if not content:
                return f"⚠️ 网页 {url} 的内容为空或无法提取。"
            
            return f"📄 网页内容（{url}）：\n\n{content}"
            
    except httpx.TimeoutException:
        raise ToolExecutionError("网页加载超时（30秒），请尝试其他网页或稍后重试。")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ToolExecutionError(f"网页不存在 (404): {url}")
        elif e.response.status_code == 403:
            raise ToolExecutionError(f"网页禁止访问 (403): {url}")
        else:
            raise ToolExecutionError(f"HTTP 错误 ({e.response.status_code}): {url}")
    except httpx.HTTPError as e:
        raise ToolExecutionError(f"网络请求失败: {str(e)}")
    except Exception as e:
        raise ToolExecutionError(f"获取网页内容失败: {str(e)}")


def _handle_get_weather(args: Dict[str, Any], settings: Settings, session: Session) -> str:  # noqa: ARG001
    """天气查询工具 - 使用 wttr.in"""
    city = args.get("city")
    
    if not city or not isinstance(city, str):
        raise ToolExecutionError("缺少 city 字段。")
    
    try:
        # 使用 wttr.in - 免费天气 API，支持中英文城市名
        url = f"https://wttr.in/{city}?format=j1&lang=zh"
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # 提取当前天气信息
            current = data['current_condition'][0]
            
            # 提取中文描述
            weather_desc = current.get('lang_zh', [{}])[0].get('value', current.get('weatherDesc', [{}])[0].get('value', '未知'))
            
            # 格式化输出
            result = (
                f"🌤️ {city} 实时天气：\n\n"
                f"🌡️ 温度: {current['temp_C']}°C\n"
                f"🤚 体感温度: {current['FeelsLikeC']}°C\n"
                f"☁️ 天气: {weather_desc}\n"
                f"💧 湿度: {current['humidity']}%\n"
                f"💨 风速: {current['windspeedKmph']} km/h\n"
                f"🧭 风向: {current.get('winddir16Point', 'N/A')}\n"
                f"👁️ 能见度: {current['visibility']} km\n"
                f"🌡️ 气压: {current['pressure']} mb"
            )
            
            # 添加今天的预报信息
            if 'weather' in data and len(data['weather']) > 0:
                today = data['weather'][0]
                result += (
                    f"\n\n📅 今日预报：\n"
                    f"🌅 最高温度: {today['maxtempC']}°C\n"
                    f"🌃 最低温度: {today['mintempC']}°C\n"
                    f"🌞 日出: {today['astronomy'][0]['sunrise']}\n"
                    f"🌙 日落: {today['astronomy'][0]['sunset']}"
                )
            
            return result
            
    except httpx.TimeoutException:
        raise ToolExecutionError("天气查询超时，请稍后重试。")
    except httpx.HTTPError as e:
        raise ToolExecutionError(f"天气服务暂时不可用: {str(e)}")
    except (KeyError, IndexError) as e:
        raise ToolExecutionError(f"天气数据解析失败，请检查城市名称是否正确: {str(e)}")
    except Exception as e:
        raise ToolExecutionError(f"天气查询失败: {str(e)}")


BUILTIN_TOOLS: Dict[str, BuiltinToolDefinition] = {
    "write_note": BuiltinToolDefinition(
        key="write_note",
        name="写入笔记文件",
        description="在 data/notes 目录下创建或覆盖笔记文件，可用于记录总结或执行结果。",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "目标文件名，例如 summary.txt",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文本内容。",
                },
            },
            "required": ["filename", "content"],
        },
        handler=_handle_write_note,
    ),
    "list_knowledge_docs": BuiltinToolDefinition(
        key="list_knowledge_docs",
        name="列出知识库文档",
        description="查看当前知识库中已登记的文档及其片段数量。",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_list_documents,
    ),
    "search_knowledge": BuiltinToolDefinition(
        key="search_knowledge",
        name="知识库关键词检索",
        description="按语义检索知识库片段，返回最相关的几段文本。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要检索的问题或关键词。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回片段数量（默认 3，最大 10）。",
                },
            },
            "required": ["query"],
        },
        handler=_handle_search_knowledge,
    ),
    "draw_diagram": BuiltinToolDefinition(
        key="draw_diagram",
        name="绘制结构图",
        description="使用 Mermaid 语法绘制流程图、架构图、时序图等结构图，保存为 Markdown 文件。支持 flowchart、sequence、class、state 等多种图表类型。",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "目标文件名，例如 architecture.md",
                },
                "diagram_code": {
                    "type": "string",
                    "description": "Mermaid 语法的图表代码，例如 'flowchart TD\\n    A[开始] --> B[处理]'",
                },
                "diagram_type": {
                    "type": "string",
                    "description": "图表类型说明（可选），例如 'flowchart'、'sequence'、'class diagram' 等",
                },
            },
            "required": ["filename", "diagram_code"],
        },
        handler=_handle_draw_diagram,
    ),
    "web_search": BuiltinToolDefinition(
        key="web_search",
        name="网页搜索",
        description="在互联网上搜索信息。输入搜索关键词，返回相关网页的标题、链接和摘要。适合查找最新信息、新闻、技术文档等。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题，例如 '2024年人工智能发展趋势'",
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量（1-10，默认5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=_handle_web_search,
    ),
    "fetch_webpage": BuiltinToolDefinition(
        key="fetch_webpage",
        name="获取网页内容",
        description="读取指定网页的完整内容（Markdown格式）。适合深入阅读某个网页的详细信息。注意：会消耗较多 token。",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "完整的网页 URL，例如 'https://example.com/article'",
                },
            },
            "required": ["url"],
        },
        handler=_handle_fetch_webpage,
    ),
    "get_weather": BuiltinToolDefinition(
        key="get_weather",
        name="天气查询",
        description="查询指定城市的实时天气情况，包括温度、湿度、风速等信息。支持中英文城市名。",
        input_schema={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称（中文或英文），例如 'Beijing'、'北京'、'New York'",
                },
            },
            "required": ["city"],
        },
        handler=_handle_get_weather,
    ),
}


def list_builtin_options() -> List[Dict[str, Any]]:
    """Return builtin tool descriptors for UI usage."""
    return [
        {
            "key": tool.key,
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in BUILTIN_TOOLS.values()
    ]


def validate_tool_config(tool_type: str, config: Dict[str, Any]) -> None:
    """Validate tool configuration according to type."""
    if tool_type == "builtin":
        builtin_key = config.get("builtin_key")
        if not builtin_key:
            raise HTTPException(status_code=422, detail="builtin 类型必须提供 builtin_key。")
        if builtin_key not in BUILTIN_TOOLS:
            raise HTTPException(status_code=422, detail="未知的 builtin_key。")
    elif tool_type == "http_get":
        base_url = config.get("base_url")
        if not base_url or not isinstance(base_url, str):
            raise HTTPException(status_code=422, detail="http_get 工具需要 base_url。")
    else:
        raise HTTPException(status_code=422, detail=f"暂不支持的工具类型: {tool_type}")


def record_tool_log(
    session: Session,
    tool: ToolRecord,
    arguments: Dict[str, Any],
    result: str | None,
    success: bool,
    error_message: str | None = None,
) -> None:
    """Persist a tool execution log entry."""
    log = ToolExecutionLog(
        id=uuid.uuid4().hex,
        tool_id=tool.id,
        tool_name=tool.name,
        arguments=json.dumps(arguments, ensure_ascii=False),
        result_preview=(result or "")[:500],
        success=success,
        error_message=error_message,
    )
    session.add(log)
    session.commit()


def execute_tool(
    tool: ToolRecord,
    arguments: Dict[str, Any],
    settings: Settings,
    session: Session,
) -> str:
    """Execute a tool and log the outcome."""
    config = json.loads(tool.config)
    arguments = arguments or {}
    if tool.tool_type == "builtin":
        builtin_key = config["builtin_key"]
        definition = BUILTIN_TOOLS[builtin_key]
        try:
            result = definition.handler(arguments, settings, session)
            record_tool_log(session, tool, arguments, result, success=True)
            return result
        except ToolExecutionError as error:
            record_tool_log(
                session, tool, arguments, result=None, success=False, error_message=str(error)
            )
            raise HTTPException(status_code=400, detail=str(error)) from error
    elif tool.tool_type == "http_get":
        base_url = config["base_url"].rstrip("/")
        path = arguments.get("path", "")
        params = arguments.get("params")
        if params is not None and not isinstance(params, dict):
            raise HTTPException(status_code=422, detail="params 必须是对象。")
        url = f"{base_url}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, params=params)
            response.raise_for_status()
            text = response.text[:1000]
            record_tool_log(session, tool, arguments, text, success=True)
            return f"GET {url} 成功（HTTP {response.status_code}）：\n{text}"
        except httpx.HTTPError as error:
            record_tool_log(
                session,
                tool,
                arguments,
                result=None,
                success=False,
                error_message=str(error),
            )
            raise HTTPException(status_code=502, detail=f"HTTP 工具调用失败：{error}") from error
    else:
        raise HTTPException(status_code=422, detail=f"未知工具类型：{tool.tool_type}")


def build_tool_prompt(tool_records: List[ToolRecord]) -> str:
    """Assemble a natural language instruction describing available tools."""
    lines = [
        "你可以使用以下 MCP 工具。需要调用时，请输出：",
        "<tool_call>{\"tool_id\": \"工具ID\", \"arguments\": {键值对}}</tool_call>",
        "如果无需调用，请直接回答用户问题。",
        "",
    ]
    for record in tool_records:
        config = json.loads(record.config)
        schema_desc = ""
        if record.tool_type == "builtin":
            builtin = BUILTIN_TOOLS.get(config.get("builtin_key", ""))
            if builtin:
                schema_desc = json.dumps(builtin.input_schema, ensure_ascii=False)
        elif record.tool_type == "http_get":
            schema_desc = json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "追加在 base_url 之后的路径"},
                        "params": {"type": "object", "description": "可选的查询参数对象"},
                    },
                },
                ensure_ascii=False,
            )
        lines.append(
            f"- 工具ID: {record.id}\n  名称: {record.name}\n  类型: {record.tool_type}\n"
            f"  描述: {record.description}\n  参数Schema: {schema_desc}"
        )
    return "\n".join(lines)


def parse_tool_call(response_text: str) -> Dict[str, Any] | None:
    """Extract tool call JSON payload from model response."""
    match = re.search(r"<tool_call>(.*?)</tool_call>", response_text, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1).strip())
        if not isinstance(payload, dict):
            return None
        return payload
    except json.JSONDecodeError:
        return None


def load_tool_config(tool: ToolRecord) -> Dict[str, Any]:
    """Return the JSON config for a tool."""
    return json.loads(tool.config)
