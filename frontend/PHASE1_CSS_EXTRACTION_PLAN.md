# Phase 1.2: CSS提取计划

## 🎯 目标
将agent_chat.html中的内联CSS提取到独立文件，减少HTML文件体积

## 📊 当前CSS结构分析

### 现有CSS文件
```
css/
├── variables.css (143行) - CSS变量定义 ✅
├── base.css (146行) - 基础样式 ✅  
├── components.css (458行) - 组件样式 ✅
├── responsive.css (358行) - 响应式 ✅
└── common.css (116行) - 通用样式 ✅
```

### agent_chat.html中的内联CSS
预估约 **2000-2500行** 内联CSS需要提取

## 🔧 提取策略

### Step 1: 创建页面专属样式文件
```
css/pages/
└── agent-chat.css  # 所有agent_chat.html的专属样式
```

### Step 2: CSS分类提取

#### 类别1：布局样式
- `.container`
- `.main-content`
- `.sidebar`
- `.agent-timeline`

#### 类别2：组件样式
- `.message` / `.user-message` / `.agent-message`
- `.input-container`
- `.builder-panel`
- `.modal`

#### 类别3：动画和过渡
- `@keyframes`
- `transition` 相关

#### 类别4：响应式媒体查询
- `@media` 查询

### Step 3: 执行提取

```python
# extract_css.py
import re

def extract_inline_css(html_file):
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有<style>标签
    style_pattern = r'<style>(.*?)</style>'
    styles = re.findall(style_pattern, content, re.DOTALL)
    
    # 合并所有样式
    all_css = '\n\n'.join(styles)
    
    # 保存到新文件
    with open('css/pages/agent-chat.css', 'w', encoding='utf-8') as f:
        f.write('/* Agent Chat Page Styles */\n')
        f.write('/* 从agent_chat.html提取 */\n')
        f.write('/* 提取时间：2024-11-22 */\n\n')
        f.write(all_css)
    
    # 从HTML中移除<style>标签，替换为link
    new_html = re.sub(
        style_pattern,
        '',
        content,
        flags=re.DOTALL
    )
    
    # 在<head>中添加新的CSS链接
    new_html = new_html.replace(
        '</head>',
        '    <link rel="stylesheet" href="css/pages/agent-chat.css">\n</head>'
    )
    
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    print(f"✅ CSS已提取到 css/pages/agent-chat.css")
    print(f"✅ HTML文件已更新")

if __name__ == '__main__':
    extract_inline_css('agent_chat.html')
```

## ✅ 预期成果

### 文件大小变化
| 文件 | 提取前 | 提取后 | 减少 |
|-----|-------|-------|------|
| agent_chat.html | ~250KB | ~100KB | ↓ 60% |
| css/pages/agent-chat.css | 0KB | ~80KB | - |

### 行数变化
| 文件 | 提取前 | 提取后 | 减少 |
|-----|-------|-------|------|
| agent_chat.html | 7170行 | ~4500行 | ↓ 37% |

## 🧪 测试清单

提取后需要测试：
- [ ] 页面布局正常
- [ ] 所有组件样式正确
- [ ] 响应式布局工作
- [ ] 主题切换正常
- [ ] 动画效果正常
- [ ] 无CSS加载错误

## 📝 注意事项

1. **保持CSS变量引用**
   - 确保agent-chat.css在variables.css之后加载
   
2. **避免样式冲突**
   - 检查是否有与common.css、components.css的重复定义
   
3. **优化CSS顺序**
   ```html
   <link rel="stylesheet" href="css/variables.css">
   <link rel="stylesheet" href="css/base.css">
   <link rel="stylesheet" href="common.css">
   <link rel="stylesheet" href="css/components.css">
   <link rel="stylesheet" href="css/pages/agent-chat.css">
   <link rel="stylesheet" href="css/responsive.css">
   ```

## 🚀 执行命令

```bash
cd frontend

# 创建目录
mkdir -p css/pages

# 运行提取脚本
python extract_css.py

# 验证文件
cat css/pages/agent-chat.css | wc -l

# 测试
# 在浏览器中打开agent_chat.html
# 检查样式是否正常
```

---
创建时间：2024-11-22
阶段：Phase 1.2
