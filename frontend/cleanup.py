#!/usr/bin/env python3
"""
清理agent_chat.html中的注释代码块
删除已经迁移到模块化JS文件中的重复代码
"""

def cleanup_agent_chat():
    filename = 'agent_chat.html'
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"原文件大小: {len(content)} 字符")
    
    # 查找并删除第一个大块
    # 从 "<!--script>" 到 "</script-->" 和结束注释
    marker1_start = "<!--script>\n        // ========== 画布管理器 =========="
    marker1_end = "    </script-->\n    <!-- ========== 结束：重复的内联JavaScript代码块 #1 ========== -->"
    
    start_idx = content.find(marker1_start)
    end_idx = content.find(marker1_end)
    
    if start_idx != -1 and end_idx != -1:
        # 删除这个块，替换为简短说明
        before = content[:start_idx]
        after = content[end_idx + len(marker1_end):]
        content = before + after
        print(f"✅ 删除第一个代码块 ({end_idx - start_idx} 字符)")
    else:
        print("⚠️  未找到第一个代码块的完整标记")
    
    # 查找并删除第二个块
    marker2_start = "    <!-- ========================================\n         ⚠️ 已禁用：重复的内联JavaScript代码块 #2"
    marker2_end = "    </script-->\n    <!-- ========== 结束：重复的内联JavaScript代码块 #2 ========== -->"
    
    start_idx = content.find(marker2_start)
    end_idx = content.find(marker2_end)
    
    if start_idx != -1 and end_idx != -1:
        before = content[:start_idx]
        after = content[end_idx + len(marker2_end):]
        content = before + after
        print(f"✅ 删除第二个代码块 ({end_idx - start_idx} 字符)")
    else:
        print("⚠️  未找到第二个代码块的完整标记")
    
    # 保存清理后的文件
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n新文件大小: {len(content)} 字符")
    print(f"✅ 清理完成！文件已更新：{filename}")
    
    # 统计行数
    lines = content.count('\n')
    print(f"新文件行数: {lines}")

if __name__ == '__main__':
    cleanup_agent_chat()
