// API 配置
// 支持环境变量配置，便于 Docker 部署

// 获取 API Base URL
// 优先级：环境变量 > 默认值
const getApiBaseUrl = () => {
  // Vite 环境变量
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  
  // 生产环境：使用相对路径（通过 nginx 代理）
  if (import.meta.env.PROD) {
    return '/api';
  }
  
  // 开发环境：直接连接后端
  return 'http://127.0.0.1:8000';
};

export const API_BASE_URL = getApiBaseUrl();

// 导出配置对象
export default {
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 分钟超时（适合长时间的 AI 响应）
  headers: {
    'Content-Type': 'application/json',
  },
};

