#!/usr/bin/env python3
"""
批量提取所有HTML文件的内联JavaScript到独立JS文件
"""
import os
import re
from pathlib import Path

# HTML文件列表
HTML_FILES = [
    'conversation_history.html',
    'conversation_settings.html',
    'knowledge_base.html',
    'login.html',
    'prompt_management.html',
    'register.html'
]

def extract_js_from_html(html_file):
    """提取HTML文件中的JavaScript"""
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有<script>标签（不包括src引用）
    script_pattern = r'<script>(.*?)</script>'
    scripts = re.findall(script_pattern, content, re.DOTALL)
    
    if not scripts:
        print(f"  ⚠️  {html_file} 没有内联JavaScript")
        return None
    
    # 合并所有JavaScript
    js_content = '\n\n'.join(scripts)
    
    # 生成JS文件名
    base_name = Path(html_file).stem
    js_file = f'js/pages/{base_name}.js'
    
    # 创建目录
    os.makedirs('js/pages', exist_ok=True)
    
    # 写入JS文件
    with open(js_file, 'w', encoding='utf-8') as f:
        f.write(f"/* JavaScript extracted from {html_file} */\n\n")
        f.write(js_content)
    
    print(f"  ✅ JS已提取到: {js_file}")
    print(f"     大小: {len(js_content)} 字符")
    
    # 移除HTML中的<script>标签并添加外部引用
    new_content = re.sub(script_pattern, '', content, flags=re.DOTALL)
    
    # 在</body>前添加script标签
    script_tag = f'    <script src="{js_file}"></script>\n'
    new_content = new_content.replace('</body>', f'{script_tag}</body>')
    
    # 写回HTML文件
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  ✅ {html_file} 已更新")
    
    return js_file

def main():
    print("🚀 开始批量提取JavaScript...")
    print()
    
    total_js_size = 0
    
    for html_file in HTML_FILES:
        if not os.path.exists(html_file):
            print(f"⚠️  {html_file} 不存在，跳过")
            continue
        
        print(f"📄 处理: {html_file}")
        result = extract_js_from_html(html_file)
        
        if result:
            # 统计大小
            with open(result, 'r', encoding='utf-8') as f:
                total_js_size += len(f.read())
        
        print()
    
    print(f"🎉 所有文件处理完成！")
    print(f"📊 总计提取 JavaScript: {total_js_size:,} 字符")

if __name__ == '__main__':
    main()
