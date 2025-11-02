# 🤖 AI Agent - 智能对话助手

一个功能强大的 AI Agent 平台，集成了 RAG（检索增强生成）、MCP 工具调用、上网搜索等能力，提供类似 ChatGPT 和 Coze 的专业级用户界面。

![](https://img.shields.io/badge/Python-3.10-blue)
![](https://img.shields.io/badge/FastAPI-0.110-green)
![](https://img.shields.io/badge/DeepSeek-API-orange)

---

## ✨ 核心功能

### 🎨 现代化界面
- ✅ **注册登录系统** - 完整的用户注册和登录功能（演示模式）
- ✅ **ChatGPT 风格界面** - 三栏布局，左侧边栏 + 主聊天区 + 右侧上下文面板
- ✅ **流式响应** - 实时打字机效果，体验流畅
- ✅ **对话历史** - 自动保存，支持多会话切换
- ✅ **响应式设计** - 完美支持桌面端和移动端
- ✅ **LangGraph Agent 界面** - 实时展示 Agent 执行过程，包括规划、路由、工具调用等

### 💬 对话能力
- ✅ **Markdown 渲染** - 支持标题、列表、表格、引用等
- ✅ **数学公式** - LaTeX 公式完美渲染（$...$ 和 $$...$$）
- ✅ **代码高亮** - 语法高亮 + 一键复制
- ✅ **上下文管理** - 多轮对话，智能记忆

### 📚 RAG 知识库
- ✅ **文档上传** - 支持 PDF 文件上传（拖拽上传）
- ✅ **向量检索** - 基于 ChromaDB 的语义搜索
- ✅ **智能分块** - 自动文档分块，保留上下文
- ✅ **文档管理** - 查看、删除已上传文档

### 🌐 上网能力（新增）
- ✅ **网页搜索** - DuckDuckGo 搜索引擎，获取最新信息
- ✅ **网页内容提取** - Jina Reader 自动提取网页正文（Markdown 格式）
- ✅ **天气查询** - 实时天气信息，支持全球城市

### 🔧 工具系统
- ✅ **笔记记录** - 自动保存总结和笔记
- ✅ **知识库检索** - 语义搜索已上传文档
- ✅ **结构图绘制** - Mermaid 流程图、架构图、思维导图（LLM 智能生成）
- ✅ **自定义工具** - 支持添加 HTTP GET 工具

### 🤖 LangGraph Agent（新增）
- ✅ **多步骤规划** - 智能分析任务，生成执行计划
- ✅ **智能路由** - 根据执行状态动态决策下一步动作
- ✅ **工具调用** - 自动调用搜索、绘图、笔记等工具
- ✅ **状态管理** - 完整的执行状态跟踪和持久化
- ✅ **流式执行** - 实时展示 Agent 的思考过程和执行步骤
- ✅ **智能思维导图** - 基于搜索结果使用 LLM 生成高质量思维导图

### 🛠️ 自定义Agent构建器（最新）
- ✅ **可视化构建** - 拖拽节点创建自定义Agent工作流
- ✅ **多种节点类型** - 规划器、知识库检索、工具执行器、条件判断、LLM调用、合成器等
- ✅ **灵活连接** - 支持拖拽连接和双击连接两种方式
- ✅ **节点配置** - 可视化配置每个节点的参数和提示词
- ✅ **示例模板** - 内置天气助手、搜索总结等示例模板
- ✅ **性能优化** - 流畅的拖拽体验，硬件加速渲染
- ✅ **保存与测试** - 一键保存Agent配置，即时测试执行效果

---

## 🚀 快速开始

### 前置要求
- Python 3.10 或更高版本
- pip 或 conda 包管理器
- DeepSeek API Key（[获取地址](https://platform.deepseek.com/)）

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd ai_agent
```

### 2. 创建虚拟环境（推荐）

**使用 Conda:**
```bash
conda create -n ai-agent python=3.10 -y
conda activate ai-agent
```

**或使用 venv:**
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

> ⏱️ **注意**：首次安装会下载嵌入模型（sentence-transformers），大约需要 5-10 分钟，请耐心等待。

### 4. 配置环境变量

**Windows (PowerShell):**
```powershell
$env:DEEPSEEK_API_KEY = "sk-your-api-key-here"
```

**Linux/Mac:**
```bash
export DEEPSEEK_API_KEY="sk-your-api-key-here"
```

> 💡 **提示**：如需永久保存，可以创建 `.env` 文件或添加到系统环境变量。

### 5. 启动后端服务

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

或使用 PowerShell 脚本（Windows）:
```powershell
cd backend
.\重启增强版服务器.ps1
```

看到以下输出表示启动成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 6. 打开前端界面

在浏览器中打开：
- **登录页面**：`frontend/login.html`
- **注册页面**：`frontend/register.html`（或从登录页点击注册链接）
- **聊天界面**：`frontend/chat.html`（登录后自动跳转）
- **LangGraph Agent 界面**：`frontend/agent_chat.html`（登录后自动跳转）

或者使用 Live Server（VS Code 插件）打开 `frontend/login.html`

### 使用Agent构建器
1. 登录后，点击右上角的 🛠️ 按钮打开Agent构建器
2. 从左侧拖拽节点到画布，或点击节点类型快速添加
3. 点击节点进行配置，设置提示词、选择工具等
4. 连接节点：从输出端口拖拽到输入端口，或双击两个节点
5. 点击 **保存** 保存Agent配置，点击 **测试** 立即测试
6. 查看 **AGENT_BUILDER_EXAMPLE.md** 了解详细使用教程

---

## 📖 使用指南

### 登录系统
1. 打开 `frontend/login.html`
2. **首次使用**：点击"立即注册"，填写用户名、邮箱和密码创建账号
3. **已有账号**：输入邮箱和密码登录
4. 登录后自动跳转到 LangGraph Agent 界面
5. 支持"记住我"功能，下次访问自动登录

### 文档上传
1. 点击聊天界面右上角的 📁 按钮
2. 点击或拖拽上传 PDF 文件
3. 等待上传和索引完成
4. AI 会自动从上传的文档中检索相关信息

### 启用功能
- **🧠 知识库增强**：勾选后 AI 会从已上传文档中检索相关内容
- **🔧 启用工具**：勾选后 AI 可以调用工具（搜索、笔记、天气等）

### 查看上下文
点击右上角的 📊 按钮展开侧边面板，实时查看：
- 📚 检索到的知识片段
- 🔧 工具调用结果

### 使用上网功能

**搜索信息：**
```
帮我搜索一下 2024 年人工智能的最新发展趋势
```

**搜索并生成思维导图：**
```
帮我搜索人工智能的最新进展，总结关键点并画个思维导图
```
系统会：
1. 先执行网络搜索
2. 使用 LLM 分析搜索结果
3. 生成结构化的思维导图（Mermaid 格式）

**读取网页：**
```
请帮我总结这个网页的内容：https://example.com/article
```

**查询天气：**
```
北京今天天气怎么样？
```

**复杂任务示例：**
```
查询北京明天的天气，如果会下雨就写个笔记提醒我带伞
```
系统会自动：
1. 查询天气
2. 判断是否下雨
3. 如果需要，创建提醒笔记

---

## 📁 项目结构

```
ai_agent/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── main.py            # FastAPI 应用入口
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库模型
│   │   ├── rag_service.py     # RAG 检索服务
│   │   ├── tool_service.py    # 工具服务（含上网功能）
│   │   ├── graph_agent.py      # LangGraph Agent 核心逻辑
│   │   └── agent_builder.py   # Agent构建器后端逻辑
│   ├── data/
│   │   ├── uploads/           # 上传的文档
│   │   ├── notes/             # AI 生成的笔记
│   │   ├── diagrams/          # 生成的图表
│   │   ├── chroma/            # 向量数据库
│   │   └── agent.db           # SQLite 数据库
│   ├── requirements.txt       # Python 依赖
│   └── 重启增强版服务器.ps1   # 启动脚本（Windows）
│
├── frontend/                   # 前端界面
│   ├── login.html             # 登录页面
│   ├── register.html          # 注册页面
│   ├── chat.html              # 传统聊天界面
│   └── agent_chat.html        # LangGraph Agent 界面（推荐，包含构建器）
│
├── AGENT_BUILDER_EXAMPLE.md   # Agent构建器使用教程
└── README.md                   # 本文件
```

---

## 🛠 技术栈

### 后端
- **FastAPI** - 高性能 Web 框架
- **DeepSeek API** - 大语言模型
- **LangGraph** - Agent 工作流编排框架
- **LangChain** - LLM 应用开发框架
- **ChromaDB** - 向量数据库
- **Sentence Transformers** - 文本嵌入模型
- **SQLite** - 关系数据库
- **BeautifulSoup** - 网页解析
- **httpx** - HTTP 客户端
- **rank-bm25** - BM25 关键词检索

### 前端
- **原生 HTML/CSS/JavaScript** - 无框架依赖
- **Marked.js** - Markdown 渲染
- **KaTeX** - 数学公式渲染
- **Highlight.js** - 代码高亮

### 第三方服务
- **DuckDuckGo** - 网页搜索
- **Jina Reader** - 网页内容提取
- **wttr.in** - 天气 API

---

## 🔧 API 接口文档

服务启动后访问：`http://localhost:8000/docs`

### 主要接口

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/chat/stream` | 流式对话（推荐） |
| POST | `/chat` | 普通对话 |
| POST | `/chat/agent/stream` | LangGraph Agent 流式执行（推荐） |
| POST | `/chat/agent` | LangGraph Agent 执行 |
| POST | `/agents` | 创建自定义Agent配置 |
| GET | `/agents` | 列出所有Agent配置 |
| GET | `/agents/{id}` | 获取Agent配置详情 |
| POST | `/agents/{id}/execute` | 执行自定义Agent |
| POST | `/agents/{id}/execute/stream` | 流式执行自定义Agent |
| POST | `/documents/upload` | 上传文档 |
| GET | `/documents` | 列出文档 |
| DELETE | `/documents/{id}` | 删除文档 |
| GET | `/tools` | 列出工具 |
| POST | `/tools` | 添加工具 |
| GET | `/tool-logs` | 工具执行日志 |

---

## 🎯 内置工具列表

### 知识管理
- **write_note** - 保存笔记到本地
- **list_knowledge_docs** - 列出知识库文档
- **search_knowledge** - 搜索知识库

### 可视化
- **draw_diagram** - 绘制 Mermaid 结构图（支持流程图、思维导图等）
  - 支持基于搜索结果智能生成思维导图
  - 使用 LLM 分析内容，生成结构化图表

### 上网功能
- **web_search** - 网页搜索（DuckDuckGo）
- **fetch_webpage** - 获取网页内容（Jina Reader）
- **get_weather** - 天气查询（wttr.in）

---

## 💡 使用技巧

### 1. 优化搜索结果
```
搜索关键词时要具体，例如：
✅ "2024年 GPT-4 最新功能更新"
❌ "GPT"
```

### 2. 知识库使用
```
上传文档后：
✅ "根据我的文档，总结机器学习的核心概念"
✅ "文档中提到的实验结果是什么？"
```

### 3. 工具组合使用
```
✅ "搜索最新的 AI 新闻，并总结保存为笔记"
✅ "查询北京天气，如果下雨提醒我带伞"
```

---

## 🐛 常见问题

### Q: 首次安装很慢？
A: 正常现象，需要下载嵌入模型（约 500MB）和依赖包，请耐心等待。

### Q: 数学公式不显示？
A: 确保网络畅通，KaTeX 库需要从 CDN 加载。可以按 F12 查看控制台错误。

### Q: 搜索功能不可用？
A: 检查网络连接，确保可以访问 DuckDuckGo。部分地区可能需要代理。

### Q: DeepSeek API 调用失败？
A: 检查：
1. API Key 是否正确设置
2. 是否有剩余额度
3. 网络是否畅通

### Q: 上传文档失败？
A: 确保：
1. 文件格式为 PDF
2. 文件大小合理（< 100MB）
3. 文件未加密

---

## 📝 开发计划

### 已完成 ✅
- [x] 基础对话功能
- [x] RAG 知识库
- [x] 工具调用系统
- [x] 流式响应
- [x] 现代化 UI
- [x] Markdown 渲染
- [x] 数学公式支持
- [x] 上网搜索功能
- [x] LangGraph Agent 工作流
- [x] 用户注册登录系统
- [x] 智能思维导图生成（基于 LLM）
- [x] 任务执行顺序优化
- [x] Agent 执行过程可视化
- [x] **自定义Agent构建器** - 可视化拖拽创建Agent工作流
- [x] **节点类型扩展** - 支持延迟、变量、循环等高级节点
- [x] **性能优化** - 流畅的拖拽体验，硬件加速渲染

### 计划中 🚧
- [ ] Agent配置导入/导出（JSON格式）
- [ ] Agent版本管理和历史记录
- [ ] 更多节点类型（API调用、数据库查询等）
- [ ] 条件分支的可视化配置
- [ ] 真实用户认证系统（后端 API）
- [ ] 多 Agent 协作
- [ ] Prompt 模板管理
- [ ] 长期记忆系统
- [ ] 数据库连接器
- [ ] 语音输入/输出
- [ ] 文件上传支持更多格式（PPT、Excel 等）

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

本项目仅供学习和研究使用。

---

## 🙏 致谢

- [DeepSeek](https://www.deepseek.com/) - 提供强大的 LLM 服务
- [FastAPI](https://fastapi.tiangolo.com/) - 优秀的 Python Web 框架
- [ChromaDB](https://www.trychroma.com/) - 向量数据库
- [Jina AI](https://jina.ai/) - 网页内容提取服务

---

## 📧 联系方式

如有问题或建议，欢迎通过 Issue 联系。

---

**⭐ 如果这个项目对你有帮助，请给一个 Star！**
