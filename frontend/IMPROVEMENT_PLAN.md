# 前端项目改进计划

## 第一阶段：工程化基础设施（1-2周）

### 1. 初始化现代前端项目结构
```bash
frontend/
├── src/
│   ├── assets/          # 静态资源
│   ├── components/      # 通用组件
│   ├── pages/           # 页面组件
│   ├── services/        # API服务
│   ├── stores/          # 状态管理
│   ├── utils/           # 工具函数
│   ├── router/          # 路由配置
│   └── main.js          # 入口文件
├── public/              # 公共资源
├── tests/               # 测试文件
├── .eslintrc.js         # ESLint配置
├── .prettierrc          # Prettier配置
├── vite.config.js       # Vite配置
├── package.json         # 依赖管理
└── README.md            # 项目文档
```

### 2. 引入核心技术栈
- **框架**: React 18 + TypeScript
- **构建工具**: Vite 5
- **路由**: React Router v6
- **状态管理**: Zustand
- **UI组件库**: Ant Design 5 或 Arco Design
- **样式方案**: TailwindCSS + CSS Modules
- **请求库**: Axios + React Query
- **图表**: ECharts 或 Recharts

### 3. 配置开发环境
```json
// package.json 示例
{
  "name": "ai-agent-frontend",
  "version": "2.0.0",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx",
    "format": "prettier --write .",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.4.0",
    "antd": "^5.11.0",
    "@ant-design/icons": "^5.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "eslint": "^8.54.0",
    "prettier": "^3.1.0"
  }
}
```

## 第二阶段：重构核心功能（2-3周）

### 1. 组件化改造
将现有页面拆分为可复用组件：

```typescript
// 示例：聊天组件
// src/components/Chat/ChatMessage.tsx
interface ChatMessageProps {
  message: Message;
  isUser: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, isUser }) => {
  return (
    <div className={`message ${isUser ? 'user' : 'assistant'}`}>
      <Avatar src={isUser ? userAvatar : aiAvatar} />
      <div className="message-content">
        <ReactMarkdown>{message.content}</ReactMarkdown>
      </div>
    </div>
  );
};
```

### 2. API服务层封装
```typescript
// src/services/api.ts
import axios from 'axios';
import { useQuery, useMutation } from '@tanstack/react-query';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
});

// 请求拦截器
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Chat API
export const chatAPI = {
  sendMessage: (data: SendMessageDto) => 
    api.post('/chat/agent/stream', data),
  
  getHistory: (sessionId: string) => 
    api.get(`/chat/history/${sessionId}`),
};

// React Query Hooks
export const useSendMessage = () => {
  return useMutation({
    mutationFn: chatAPI.sendMessage,
  });
};
```

### 3. 状态管理
```typescript
// src/stores/chat.store.ts
import { create } from 'zustand';

interface ChatStore {
  messages: Message[];
  sessionId: string | null;
  isLoading: boolean;
  
  addMessage: (message: Message) => void;
  setSessionId: (id: string) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  sessionId: null,
  isLoading: false,
  
  addMessage: (message) => 
    set((state) => ({ messages: [...state.messages, message] })),
  
  setSessionId: (id) => 
    set({ sessionId: id }),
  
  clearMessages: () => 
    set({ messages: [] }),
}));
```

## 第三阶段：性能优化与用户体验（1-2周）

### 1. 性能优化措施
- **代码分割**: 使用 React.lazy 和 Suspense
- **虚拟列表**: 处理长列表（react-window）
- **图片懒加载**: Intersection Observer API
- **缓存策略**: React Query 的缓存机制
- **Web Worker**: 处理复杂计算

### 2. 用户体验提升
- **骨架屏**: 加载状态优化
- **错误边界**: 优雅的错误处理
- **动画过渡**: Framer Motion
- **暗黑模式**: 完善主题系统
- **国际化**: i18n 支持

### 3. 实时通信优化
```typescript
// 使用 EventSource 处理 SSE
class SSEClient {
  private eventSource: EventSource | null = null;
  
  connect(url: string, onMessage: (data: any) => void) {
    this.eventSource = new EventSource(url);
    
    this.eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };
    
    this.eventSource.onerror = () => {
      this.reconnect(url, onMessage);
    };
  }
  
  private reconnect(url: string, onMessage: (data: any) => void) {
    setTimeout(() => this.connect(url, onMessage), 3000);
  }
}
```

## 第四阶段：质量保证（1周）

### 1. 测试体系
```typescript
// 单元测试示例
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatInput } from './ChatInput';

describe('ChatInput', () => {
  it('should send message on enter key', () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} />);
    
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    
    expect(onSend).toHaveBeenCalledWith('Hello');
  });
});
```

### 2. CI/CD 配置
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run lint
      - run: npm run test
      - run: npm run build
```

## 第五阶段：部署与监控（3-5天）

### 1. Docker化部署
```dockerfile
# Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
```

### 2. 监控与日志
- **错误监控**: Sentry
- **性能监控**: Google Analytics / Umami
- **日志收集**: LogRocket

## 实施优先级

### 🔴 高优先级（立即实施）
1. 搭建 Vite + React + TypeScript 基础架构
2. 迁移核心聊天功能
3. 实现 API 服务层
4. 配置 ESLint + Prettier

### 🟡 中优先级（第二阶段）
1. 完成所有页面迁移
2. 实现状态管理
3. 添加单元测试
4. 优化性能

### 🟢 低优先级（后续改进）
1. 国际化支持
2. PWA 功能
3. 高级动画效果
4. A/B 测试框架

## 预期收益

- **开发效率提升 300%**：热更新、组件复用、TypeScript 类型检查
- **性能提升 200%**：虚拟DOM、代码分割、缓存优化
- **维护成本降低 70%**：模块化、测试覆盖、代码规范
- **用户体验提升**：响应速度快、交互流畅、错误处理优雅

## 时间线
- 第1-2周：基础设施搭建
- 第3-5周：核心功能迁移
- 第6-7周：性能优化
- 第8周：测试与部署

## 技术支持资源
- [React 官方文档](https://react.dev)
- [Vite 官方文档](https://vitejs.dev)
- [TypeScript 手册](https://www.typescriptlang.org/docs/)
- [Ant Design 组件库](https://ant.design)
