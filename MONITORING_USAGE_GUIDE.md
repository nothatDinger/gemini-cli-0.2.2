# 🔍 Gemini CLI 监控功能使用指南

## 快速开始

### 1. 启用监控功能

```bash
# 方式一：使用 --debug 参数（推荐）
echo "你的查询" | proxy_use node bundle/gemini.js --debug

# 方式二：设置环境变量
export DEBUG=1
echo "你的查询" | proxy_use node bundle/gemini.js
```

### 2. 实时监控输出

启用debug模式后，你会看到彩色的实时监控信息：

```
[监控] 2025-09-05T06:43:35.206Z 🚀 LLM调用开始: gemini-2.5-pro (ID: llm-stream-xxx, Prompt: xxx)
[监控] 2025-09-05T06:43:42.980Z ✅ LLM调用完成: gemini-2.5-pro (ID: llm-stream-xxx) - 耗时: 7772ms (11870 tokens)
[监控] 2025-09-05T06:43:44.363Z 🔧 工具调用开始: run_shell_command (ID: tool-xxx, Call: call-xxx)
[监控] 2025-09-05T06:43:45.000Z ⚡ 工具执行开始: run_shell_command (ID: tool-xxx)
[监控] 2025-09-05T06:43:46.200Z ✅ 工具调用完成: run_shell_command (ID: tool-xxx) - 总耗时: 1200ms (执行: 800ms)
```

**状态图标说明：**
- 🚀 开始
- ✅ 成功完成
- ❌ 失败
- ⏹️ 取消
- ⚡ 工具执行开始

## 监控数据分析

### 自动分析脚本

使用提供的分析脚本：

```bash
# 分析当前目录的 trace.jsonl
python3 analyze_monitoring.py

# 分析指定的日志文件
python3 analyze_monitoring.py /path/to/trace.jsonl
```

**分析结果示例：**
```
🔍 Gemini CLI 监控数据分析
==================================================

📊 LLM调用统计:
------------------------------
总调用次数: 4
成功完成: 2
失败次数: 1
平均响应时间: 6272ms
最快响应: 4773ms
最慢响应: 7772ms
总Token消耗: 23614
平均Token: 11807

🤖 按模型统计:
  gemini-2.5-pro: 4次

🔧 工具调用统计:
------------------------------
总调用次数: 0
成功完成: 0
失败次数: 0

⏰ 时间线分析:
------------------------------
  06:43:44 🚀 LLM调用开始 (gemini-2.5-pro)
  06:43:49 ✅ LLM调用完成 (gemini-2.5-pro) - 4773ms, 11744 tokens
  06:43:49 🚀 LLM调用开始 (gemini-2.5-pro)
  06:43:51 ❌ LLM调用失败 (gemini-2.5-pro)
```

### 手动查看原始数据

```bash
# 查看所有监控事件
cat trace.jsonl

# 查看最后几条记录
tail -5 trace.jsonl

# 格式化JSON输出（需要安装jq）
cat trace.jsonl | jq .

# 只查看LLM调用事件
grep '"type":"llm_call"' trace.jsonl | jq .

# 只查看工具调用事件
grep '"type":"tool_call"' trace.jsonl | jq .
```

## 监控数据结构

### LLM调用事件

```json
{
  "timestamp": "2025-09-05T06:43:35.206Z",
  "type": "llm_call",
  "event": "start|end|error",
  "data": {
    "id": "llm-stream-5f67b14826485-1757054615205",
    "model": "gemini-2.5-pro",
    "promptId": "5f67b14826485",
    "startTime": 1757054615206,
    "endTime": 1757054622978,
    "duration": 7772,
    "status": "started|completed|error",
    "inputTokens": 11375,
    "outputTokens": 25,
    "totalTokens": 11870,
    "requestText": "...",
    "responseText": "...",
    "error": "错误信息"
  }
}
```

### 工具调用事件

```json
{
  "timestamp": "2025-09-05T06:43:44.124Z",
  "type": "tool_call",
  "event": "start|end|error",
  "data": {
    "id": "tool-call-456-1725516000000",
    "toolName": "run_shell_command",
    "callId": "call-456",
    "promptId": "prompt-123",
    "startTime": 1725516000000,
    "endTime": 1725516001200,
    "duration": 1200,
    "status": "started|validating|awaiting_approval|scheduled|executing|completed|error|cancelled",
    "args": {"command": "ls -la"},
    "result": "命令执行结果",
    "executionStartTime": 1725516000400,
    "executionDuration": 800,
    "error": "错误信息"
  }
}
```

## 高级用法

### 1. 自定义监控脚本

```bash
# 创建自定义分析脚本
cat > my_analysis.py << 'EOF'
import json
import sys

def analyze_performance():
    with open('trace.jsonl', 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    # 计算平均响应时间
    llm_durations = []
    for event in events:
        if event['type'] == 'llm_call' and event['event'] == 'end':
            llm_durations.append(event['data']['duration'])
    
    if llm_durations:
        avg_duration = sum(llm_durations) / len(llm_durations)
        print(f"平均LLM响应时间: {avg_duration:.0f}ms")

if __name__ == '__main__':
    analyze_performance()
EOF

python3 my_analysis.py
```

### 2. 实时监控

```bash
# 实时查看新的监控事件
tail -f trace.jsonl | while read line; do
    echo "$line" | jq .
done
```

### 3. 性能警告

```bash
# 监控响应时间超过5秒的LLM调用
cat trace.jsonl | jq -r 'select(.type=="llm_call" and .event=="end" and .data.duration > 5000) | "⚠️  慢查询: \(.data.duration)ms - \(.data.model)"'
```

## 监控最佳实践

### 1. 定期清理日志
```bash
# 备份并清理旧日志
mv trace.jsonl trace_backup_$(date +%Y%m%d).jsonl
touch trace.jsonl
```

### 2. 监控告警
```bash
# 检查是否有失败的调用
if grep -q '"event":"error"' trace.jsonl; then
    echo "⚠️  发现失败的调用，请检查日志"
fi
```

### 3. 性能基准
```bash
# 建立性能基准
python3 analyze_monitoring.py > performance_baseline.txt
echo "基准数据已保存到 performance_baseline.txt"
```

## 故障排除

### 常见问题

1. **没有监控输出**
   ```bash
   # 确保使用了 --debug 参数
   echo "测试" | proxy_use node bundle/gemini.js --debug
   ```

2. **trace.jsonl文件为空**
   ```bash
   # 检查文件权限
   ls -la trace.jsonl
   
   # 确保监控服务已初始化
   grep "Initialize monitoring" 日志输出
   ```

3. **分析脚本报错**
   ```bash
   # 检查Python环境
   python3 --version
   
   # 检查JSON格式
   cat trace.jsonl | head -1 | python3 -m json.tool
   ```

## 配置选项

监控功能目前支持以下配置：

- **控制台输出**: 通过 `--debug` 参数启用
- **文件输出**: 自动写入 `trace.jsonl`
- **输出格式**: JSONL (每行一个JSON对象)

## 示例工作流

```bash
# 1. 启动监控会话
echo "分析这个项目的代码结构" | proxy_use node bundle/gemini.js --debug

# 2. 查看实时数据分析
python3 analyze_monitoring.py

# 3. 导出性能报告
python3 analyze_monitoring.py > performance_report_$(date +%Y%m%d).txt

# 4. 清理旧数据
mv trace.jsonl archive/trace_$(date +%Y%m%d_%H%M%S).jsonl
touch trace.jsonl
```

---

## 监控指标说明

| 指标 | 说明 | 单位 |
|------|------|------|
| 响应时间 | 从请求发送到收到完整响应的时间 | 毫秒(ms) |
| Token消耗 | 输入+输出的总Token数量 | 个 |
| 成功率 | 成功调用数/总调用数 | 百分比 |
| 执行时间 | 工具实际执行时间（不含等待时间） | 毫秒(ms) |

通过这些监控数据，你可以：
- 📈 优化查询以减少Token消耗
- ⚡ 识别性能瓶颈
- 🔍 调试失败的调用
- 📊 生成使用报告
