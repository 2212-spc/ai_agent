#!/usr/bin/env python3
"""
彻底删除agent_chat.html中剩余的大块注释代码
"""

def remove_large_commented_block():
    filename = 'agent_chat.html'
    
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"原文件行数: {len(lines)}")
    
    # 找到要删除的块的起始和结束行
    start_marker = "    <!-- ========================================"
    end_marker = "    <!-- ========== 结束：重复的内联JavaScript代码块 #1 ========== -->"
    
    start_line = -1
    end_line = -1
    
    for i, line in enumerate(lines):
        if start_marker in line and start_line == -1:
            start_line = i
            print(f"找到开始标记在第 {i+1} 行")
        if end_marker in line:
            end_line = i
            print(f"找到结束标记在第 {i+1} 行")
            break
    
    if start_line != -1 and end_line != -1:
        # 删除从start_line到end_line的所有行（包括结束标记）
        new_lines = lines[:start_line] + lines[end_line+1:]
        
        deleted_lines = end_line - start_line + 1
        print(f"✅ 删除了 {deleted_lines} 行注释代码")
        
        # 保存文件
        with open(filename, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"新文件行数: {len(new_lines)}")
        print(f"文件大小减少: {len(lines) - len(new_lines)} 行")
        print(f"✅ 清理完成！")
    else:
        print(f"⚠️  未找到完整的注释块标记")
        if start_line == -1:
            print("   - 未找到开始标记")
        if end_line == -1:
            print("   - 未找到结束标记")

if __name__ == '__main__':
    remove_large_commented_block()
