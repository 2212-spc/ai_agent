#!/usr/bin/env python3
"""
批量提取所有HTML文件的内联CSS和JS到独立文件
"""
import os
import re
from pathlib import Path

# HTML文件列表（除了agent_chat.html已经处理过）
HTML_FILES = [
    'conversation_history.html',
    'conversation_settings.html',
    'knowledge_base.html',
    'login.html',
    'prompt_management.html',
    'register.html'
]

def extract_css_from_html(html_file):
    """提取HTML文件中的CSS"""
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有<style>标签
    style_pattern = r'<style>(.*?)</style>'
    styles = re.findall(style_pattern, content, re.DOTALL)
    
    if not styles:
        print(f"  ⚠️  {html_file} 没有内联CSS")
        return None
    
    # 合并所有CSS
    css_content = '\n\n'.join(styles)
    
    # 生成CSS文件名
    base_name = Path(html_file).stem
    css_file = f'css/pages/{base_name}.css'
    
    # 创建目录
    os.makedirs('css/pages', exist_ok=True)
    
    # 写入CSS文件
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(f"/* CSS extracted from {html_file} */\n\n")
        f.write(css_content)
    
    print(f"  ✅ CSS已提取到: {css_file}")
    
    # 移除HTML中的<style>标签并添加link
    new_content = re.sub(style_pattern, '', content, flags=re.DOTALL)
    
    # 在</head>前添加link标签
    link_tag = f'    <link rel="stylesheet" href="{css_file}">\n'
    new_content = new_content.replace('</head>', f'{link_tag}</head>')
    
    # 写回HTML文件
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  ✅ {html_file} 已更新")
    
    return css_file

def main():
    print("🚀 开始批量提取CSS...")
    print()
    
    for html_file in HTML_FILES:
        if not os.path.exists(html_file):
            print(f"⚠️  {html_file} 不存在，跳过")
            continue
        
        print(f"📄 处理: {html_file}")
        extract_css_from_html(html_file)
        print()
    
    print("🎉 所有文件处理完成！")

if __name__ == '__main__':
    main()
