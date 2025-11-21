#!/usr/bin/env python3
"""
从agent_chat.html提取内联CSS到独立文件
作用：减少HTML文件大小，提高可维护性
创建时间：2024-11-22
"""

import re
from datetime import datetime

def extract_inline_css(html_file='agent_chat.html'):
    print(f"🔍 开始提取 {html_file} 中的内联CSS...")
    
    # 读取HTML文件
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    print(f"📊 原文件大小: {original_size:,} 字符")
    
    # 查找所有<style>标签及其内容
    style_pattern = r'<style>(.*?)</style>'
    styles = re.findall(style_pattern, content, re.DOTALL)
    
    if not styles:
        print("⚠️  未找到<style>标签")
        return
    
    print(f"✅ 找到 {len(styles)} 个<style>块")
    
    # 统计提取的CSS大小
    total_css_size = sum(len(s) for s in styles)
    print(f"📝 CSS总大小: {total_css_size:,} 字符")
    
    # 合并所有CSS
    header = f"""/* ============================================
   Agent Chat Page Styles
   从 agent_chat.html 提取的内联CSS
   提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
   ============================================ */

"""
    
    all_css = header + '\n\n'.join(styles)
    
    # 创建css/pages目录
    import os
    os.makedirs('css/pages', exist_ok=True)
    
    # 保存CSS到新文件
    css_file = 'css/pages/agent-chat.css'
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(all_css)
    
    css_lines = all_css.count('\n')
    print(f"✅ CSS已提取到: {css_file}")
    print(f"   文件行数: {css_lines}")
    
    # 从HTML中移除所有<style>标签
    new_html = re.sub(
        r'\s*<style>.*?</style>\s*',
        '\n',
        content,
        flags=re.DOTALL
    )
    
    # 检查是否已经有agent-chat.css的链接
    if 'css/pages/agent-chat.css' not in new_html:
        # 在第一个</head>前添加CSS链接
        # 确保在其他CSS之后加载
        css_link = '    <link rel="stylesheet" href="css/pages/agent-chat.css">\n'
        new_html = new_html.replace('</head>', css_link + '</head>', 1)
        print("✅ 已添加CSS链接到HTML")
    
    # 保存修改后的HTML
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    new_size = len(new_html)
    reduction = original_size - new_size
    percentage = (reduction / original_size) * 100
    
    print(f"\n📊 HTML文件优化结果:")
    print(f"   原大小: {original_size:,} 字符")
    print(f"   新大小: {new_size:,} 字符")
    print(f"   减少: {reduction:,} 字符 ({percentage:.1f}%)")
    
    new_lines = new_html.count('\n')
    print(f"   新行数: {new_lines}")
    
    print(f"\n🎉 CSS提取完成！")
    print(f"\n⚠️  请在浏览器中测试页面，确保样式正常！")

if __name__ == '__main__':
    extract_inline_css()
