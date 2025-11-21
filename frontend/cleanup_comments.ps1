# PowerShell脚本：清理agent_chat.html中的注释代码块
# 作用：删除已注释的重复JavaScript代码，减少文件大小
# 创建时间：2024-11-22

$file = "agent_chat.html"
$backup = "agent_chat.html.before_cleanup"

# 备份原文件
Copy-Item $file $backup

# 读取文件内容
$content = Get-Content $file -Raw

# 定义要删除的注释块的起始和结束标记
$pattern1_start = '<!-- 重复的内联JavaScript代码块已删除'
$pattern1_end = '<!-- ========== 结束：重复的内联JavaScript代码块 #1 ========== -->'

$pattern2_start = '<!-- ========================================'
$pattern2_end = '<!-- ========== 结束：重复的内联JavaScript代码块 #2 ========== -->'

# 使用正则表达式删除第一个大块（保留简短说明）
$regex1 = [regex]::Escape($pattern1_start) + '[\s\S]*?' + [regex]::Escape($pattern1_end)
$content = $content -replace $regex1, @"
<!-- 重复的内联JavaScript代码块已删除（原3228-6968行，约3740行）
         这些代码已迁移至模块化JS文件：js/canvasManager.js, js/chatManager.js, js/ui-interactions.js -->
"@

# 删除第二个块
$regex2 = '<!-- ========================================\s+⚠️ 已禁用：重复的内联JavaScript代码块 #2[\s\S]*?<!-- ========== 结束：重复的内联JavaScript代码块 #2 ========== -->'
$content = $content -replace $regex2, '<!-- 重复的InputValidator代码块已删除，已迁移至js/utils.js -->'

# 保存清理后的文件
$content | Set-Content $file -NoNewline

# 统计信息
$originalLines = (Get-Content $backup).Count
$newLines = (Get-Content $file).Count
$removed = $originalLines - $newLines

Write-Host "✅ 清理完成！" -ForegroundColor Green
Write-Host "原文件行数: $originalLines" -ForegroundColor Yellow
Write-Host "新文件行数: $newLines" -ForegroundColor Yellow  
Write-Host "删除行数: $removed" -ForegroundColor Cyan
Write-Host ""
Write-Host "备份文件已保存为: $backup" -ForegroundColor Gray
Write-Host ""
Write-Host "如果一切正常，可以删除备份文件：" -ForegroundColor Gray
Write-Host "Remove-Item $backup" -ForegroundColor Gray
