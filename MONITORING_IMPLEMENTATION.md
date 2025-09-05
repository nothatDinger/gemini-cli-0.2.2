# Gemini CLI 监控功能实现

## 概述

我已经成功为gemini-cli实现了全面的LLM调用和工具执行监控功能。这个功能可以实时跟踪所有LLM请求的发出、响应时间以及所有工具调用（脚本执行）的起止时间。

## 实现的功能

### 1. 监控服务 (MonitoringService)

创建了一个单例监控服务 (`packages/core/src/utils/monitoring.ts`)，提供以下功能：

- **LLM调用监控**：
  - 跟踪请求开始时间
  - 记录响应时间
  - 监控Token使用情况查看
  
  - 记录请求和响应内容（可选）
  - 错误跟踪

- **工具调用监控**：
  - 跟踪工具调用的完整生命周期（验证→调度→执行→完成）
  - 记录工具执行的起止时间
  - 分别跟踪总耗时和实际执行耗时
  - 监控工具执行状态变化

### 2. 监控数据结构

```typescript
interface LLMCallMetrics {
  id: string;
  model: string;
  promptId: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'started' | 'completed' | 'error';
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  // ...
}

interface ToolCallMetrics {
  id: string;
  toolName: string;
  callId: string;
  promptId: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'started' | 'validating' | 'awaiting_approval' | 'scheduled' | 'executing' | 'completed' | 'error' | 'cancelled';
  executionStartTime?: number;
  executionDuration?: number;
  // ...
}
```

### 3. 集成点

#### LLM调用监控
增强了 `LoggingContentGenerator` (`packages/core/src/core/loggingContentGenerator.ts`)：
- 在 `generateContent()` 和 `generateContentStream()` 方法中添加监控
- 为每个LLM调用生成唯一ID
- 跟踪开始/结束时间和Token消耗

#### 工具调用监控
增强了 `CoreToolScheduler` (`packages/core/src/core/coreToolScheduler.ts`)：
- 为每个工具调用添加监控ID
- 跟踪工具调用状态变化（验证→调度→执行→完成）
- 记录执行开始时间和总耗时

#### CLI集成
更新了非交互式CLI (`packages/cli/src/nonInteractiveCli.ts`)：
- 在CLI启动时初始化监控服务
- 在CLI结束时打印监控总结（debug模式）

## 监控输出示例

### 控制台输出（Debug模式）
```
[监控] 2025-09-05T06:37:48.123Z 🚀 LLM调用开始: gemini-1.5-flash (ID: llm-prompt-123-1725516000000, Prompt: prompt-123)
[监控] 2025-09-05T06:37:48.124Z 🔧 工具调用开始: run_shell_command (ID: tool-call-456-1725516000000, Call: call-456)
[监控] 2025-09-05T06:37:48.125Z ⚡ 工具执行开始: run_shell_command (ID: tool-call-456-1725516000000)
[监控] 2025-09-05T06:37:49.200Z ✅ 工具调用完成: run_shell_command (ID: tool-call-456-1725516000000) - 总耗时: 1075ms (执行: 500ms)
[监控] 2025-09-05T06:37:50.300Z ✅ LLM调用完成: gemini-1.5-flash (ID: llm-prompt-123-1725516000000) - 耗时: 2177ms (1250 tokens)
```

### JSONL日志文件 (`trace.jsonl`)
```json
{"timestamp":"2025-09-05T06:37:48.123Z","type":"llm_call","event":"start","data":{"id":"llm-prompt-123-1725516000000","model":"gemini-1.5-flash","promptId":"prompt-123","startTime":1725516000000,"status":"started"}}
{"timestamp":"2025-09-05T06:37:48.124Z","type":"tool_call","event":"start","data":{"id":"tool-call-456-1725516000000","toolName":"run_shell_command","callId":"call-456","promptId":"prompt-123","startTime":1725516000000,"status":"started"}}
{"timestamp":"2025-09-05T06:37:50.300Z","type":"llm_call","event":"end","data":{"id":"llm-prompt-123-1725516000000","model":"gemini-1.5-flash","promptId":"prompt-123","startTime":1725516000000,"endTime":1725516002300,"duration":2177,"status":"completed","inputTokens":850,"outputTokens":400,"totalTokens":1250}}
```

### 监控总结
```
📊 监控总结:
LLM调用: 3次
工具调用: 5次
LLM平均响应时间: 1845ms
LLM总Token消耗: 4250
工具平均执行时间: 892ms
```

## 核心特性

1. **实时监控**：在LLM调用和工具执行的各个阶段实时记录
2. **详细指标**：包括时间、Token使用、状态变化等
3. **多输出格式**：控制台输出（带表情符号）+ JSONL日志文件
4. **零干扰**：监控功能不影响原有流程
5. **可配置**：根据debug模式决定是否显示详细输出

## 如何使用

1. **启用Debug模式**查看实时监控：
   ```bash
   echo "创建一个hello.txt文件" | gemini-cli --debug
   ```

2. **查看监控日志**：
   ```bash
   cat trace.jsonl
   ```

3. **在代码中使用监控服务**：
   ```typescript
   import { monitoringService } from '@google/gemini-cli-core';
   
   // 初始化（CLI中自动完成）
   monitoringService.initialize(config);
   
   // 获取监控数据
   const metrics = monitoringService.getAllMetrics();
   
   // 打印总结
   monitoringService.printSummary();
   ```

## 文件修改清单

1. **新增文件**：
   - `packages/core/src/utils/monitoring.ts` - 监控服务实现

2. **修改文件**：
   - `packages/core/src/core/loggingContentGenerator.ts` - 添加LLM监控
   - `packages/core/src/core/coreToolScheduler.ts` - 添加工具监控
   - `packages/cli/src/nonInteractiveCli.ts` - CLI集成
   - `packages/core/src/index.ts` - 导出监控服务

## 技术实现亮点

1. **单例模式**：确保全局统一的监控服务
2. **类型安全**：完整的TypeScript类型定义
3. **状态跟踪**：详细跟踪工具调用的完整生命周期
4. **异步友好**：支持流式LLM响应的监控
5. **错误处理**：监控过程中的错误不会影响主流程
6. **内存管理**：提供清理方法避免内存泄漏

这个监控功能为gemini-cli提供了全面的性能洞察，帮助用户了解LLM调用和工具执行的详细情况，对于调试、性能优化和使用分析都非常有价值。
