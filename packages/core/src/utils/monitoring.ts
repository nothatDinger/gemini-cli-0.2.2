/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type { Config } from '../config/config.js';

export interface LLMCallMetrics {
  id: string;
  model: string;
  promptId: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'started' | 'completed' | 'error';
  error?: string;
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  requestText?: string;
  responseText?: string;
}

export interface ToolCallMetrics {
  id: string;
  toolName: string;
  callId: string;
  promptId: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'started' | 'validating' | 'awaiting_approval' | 'scheduled' | 'executing' | 'completed' | 'error' | 'cancelled';
  error?: string;
  args?: Record<string, unknown>;
  result?: string;
  resultDisplay?: string;
  responseParts?: any[]; // 完整的工具响应部分
  executionStartTime?: number;
  executionEndTime?: number;
  executionDuration?: number;
  // 用户确认相关时间追踪
  awaitingApprovalStartTime?: number;
  awaitingApprovalEndTime?: number;
  awaitingApprovalDuration?: number;
  pureExecutionDuration?: number; // 纯执行时间（不包含等待确认）
}

export interface UserConfirmationMetrics {
  id: string;
  toolCallId: string;
  toolName: string;
  callId: string;
  promptId: string;
  confirmationType: string; // 'edit', 'execute', 'delete', etc.
  timestamp: number;
  waitingDuration?: number;
}

export interface EmbeddingCallMetrics {
  id: string;
  model: string;
  promptId: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'started' | 'completed' | 'error';
  error?: string;
  textCount: number; // 输入文本数量
  vectorDimensions?: number; // 向量维度
  requestTexts?: string[]; // 输入文本内容（可选，用于调试）
}

export interface MonitoringEvent {
  timestamp: string;
  type: 'llm_call' | 'tool_call' | 'user_confirmation' | 'embedding_call';
  event: 'completed' | 'error' | 'cancelled' | 'approval_requested' | 'approval_granted' | 'approval_denied' | 'modification_requested';
  data: LLMCallMetrics | ToolCallMetrics | UserConfirmationMetrics | EmbeddingCallMetrics;
}

export class MonitoringService {
  private static instance: MonitoringService;
  private llmCalls = new Map<string, LLMCallMetrics>();
  private toolCalls = new Map<string, ToolCallMetrics>();
  private embeddingCalls = new Map<string, EmbeddingCallMetrics>();
  private events: MonitoringEvent[] = [];
  private enableConsoleOutput = false;
  private enableFileOutput = false;
  private outputFile?: string;

  private constructor() {}

  public static getInstance(): MonitoringService {
    if (!MonitoringService.instance) {
      MonitoringService.instance = new MonitoringService();
    }
    return MonitoringService.instance;
  }

  public initialize(config: Config): void {
    this.enableConsoleOutput = config.getDebugMode();
    this.enableFileOutput = true;
    this.outputFile = config.getMonitorOutput() || 'trace.jsonl';
  }

  public startLLMCall(id: string, model: string, promptId: string, requestText?: string): void {
    const metrics: LLMCallMetrics = {
      id,
      model,
      promptId,
      startTime: Date.now(),
      status: 'started',
      requestText,
    };

    // 融合模式：只在内存中保存数据，不记录start事件到文件
    this.llmCalls.set(id, metrics);
    this.logToConsole(`🚀 LLM调用开始: ${model} (ID: ${id}, Prompt: ${promptId})`);
  }

  public endLLMCall(
    id: string,
    status: 'completed' | 'error',
    error?: string,
    inputTokens?: number,
    outputTokens?: number,
    totalTokens?: number,
    responseText?: string
  ): void {
    const metrics = this.llmCalls.get(id);
    if (!metrics) return;

    const endTime = Date.now();
    const updatedMetrics: LLMCallMetrics = {
      ...metrics,
      endTime,
      duration: endTime - metrics.startTime,
      status,
      error,
      inputTokens,
      outputTokens,
      totalTokens,
      responseText,
    };

    this.llmCalls.set(id, updatedMetrics);
    // 融合模式：记录完整事件（包含start+end信息）
    this.recordEvent('llm_call', status === 'completed' ? 'completed' : 'error', updatedMetrics);
    
    const durationText = updatedMetrics.duration ? `${updatedMetrics.duration}ms` : 'unknown';
    const tokenText = totalTokens ? ` (${totalTokens} tokens)` : '';
    const statusIcon = status === 'completed' ? '✅' : '❌';
    
    this.logToConsole(`${statusIcon} LLM调用${status === 'completed' ? '完成' : '失败'}: ${metrics.model} (ID: ${id}) - 耗时: ${durationText}${tokenText}`);
  }

  public startToolCall(
    id: string,
    toolName: string,
    callId: string,
    promptId: string,
    args?: Record<string, unknown>
  ): void {
    const metrics: ToolCallMetrics = {
      id,
      toolName,
      callId,
      promptId,
      startTime: Date.now(),
      status: 'started',
      args,
    };

    // 融合模式：只在内存中保存数据，不记录start事件到文件
    this.toolCalls.set(id, metrics);
    this.logToConsole(`🔧 工具调用开始: ${toolName} (ID: ${id}, Call: ${callId})`);
  }

  public updateToolCallStatus(
    id: string,
    status: ToolCallMetrics['status'],
    executionStartTime?: number
  ): void {
    const metrics = this.toolCalls.get(id);
    if (!metrics) return;

    const now = Date.now();
    const updatedMetrics: ToolCallMetrics = {
      ...metrics,
      status,
    };

    // 记录等待确认开始时间
    if (status === 'awaiting_approval') {
      updatedMetrics.awaitingApprovalStartTime = now;
      this.logToConsole(`⏳ 等待用户确认: ${metrics.toolName} (ID: ${id})`);
      
      // 记录确认请求事件
      const confirmationMetrics: UserConfirmationMetrics = {
        id: `confirmation-${id}-${now}`,
        toolCallId: id,
        toolName: metrics.toolName,
        callId: metrics.callId,
        promptId: metrics.promptId,
        confirmationType: 'unknown', // 可以根据需要从工具类型推断
        timestamp: now,
      };
      this.recordEvent('user_confirmation', 'approval_requested', confirmationMetrics);
    }
    
    // 记录等待确认结束时间（从awaiting_approval转到executing）
    if (metrics.status === 'awaiting_approval' && status === 'executing') {
      if (metrics.awaitingApprovalStartTime) {
        updatedMetrics.awaitingApprovalEndTime = now;
        updatedMetrics.awaitingApprovalDuration = now - metrics.awaitingApprovalStartTime;
        this.logToConsole(`✅ 用户确认完成: ${metrics.toolName} (ID: ${id}) - 等待时间: ${updatedMetrics.awaitingApprovalDuration}ms`);
        
        // 记录确认授权事件
        const confirmationMetrics: UserConfirmationMetrics = {
          id: `confirmation-granted-${id}-${now}`,
          toolCallId: id,
          toolName: metrics.toolName,
          callId: metrics.callId,
          promptId: metrics.promptId,
          confirmationType: 'unknown',
          timestamp: now,
          waitingDuration: updatedMetrics.awaitingApprovalDuration,
        };
        this.recordEvent('user_confirmation', 'approval_granted', confirmationMetrics);
      }
    }

    if (status === 'executing' && executionStartTime) {
      updatedMetrics.executionStartTime = executionStartTime;
      this.logToConsole(`⚡ 工具执行开始: ${metrics.toolName} (ID: ${id})`);
    }

    this.toolCalls.set(id, updatedMetrics);
  }

  public endToolCall(
    id: string,
    status: 'completed' | 'error' | 'cancelled',
    error?: string,
    result?: string,
    resultDisplay?: string,
    responseParts?: any[]
  ): void {
    const metrics = this.toolCalls.get(id);
    if (!metrics) return;

    const endTime = Date.now();
    const updatedMetrics: ToolCallMetrics = {
      ...metrics,
      endTime,
      duration: endTime - metrics.startTime,
      status,
      error,
      result,
      resultDisplay,
      responseParts,
    };

    if (metrics.executionStartTime) {
      updatedMetrics.executionEndTime = endTime;
      updatedMetrics.executionDuration = endTime - metrics.executionStartTime;
    }

    // 计算纯执行时间（排除等待确认时间）
    let pureExecutionDuration = updatedMetrics.duration || 0;
    if (updatedMetrics.awaitingApprovalDuration) {
      pureExecutionDuration = pureExecutionDuration - updatedMetrics.awaitingApprovalDuration;
    }
    updatedMetrics.pureExecutionDuration = pureExecutionDuration;

    this.toolCalls.set(id, updatedMetrics);
    
    // 融合模式：记录完整事件（包含start+end信息）
    const eventType = status === 'completed' ? 'completed' : 
                     status === 'cancelled' ? 'cancelled' : 'error';
    
    this.recordEvent('tool_call', eventType, updatedMetrics);
    
    const totalDuration = updatedMetrics.duration ? `${updatedMetrics.duration}ms` : 'unknown';
    const pureExecDuration = updatedMetrics.pureExecutionDuration ? ` | 纯执行: ${updatedMetrics.pureExecutionDuration}ms` : '';
    const waitingTime = updatedMetrics.awaitingApprovalDuration ? ` | 等待确认: ${updatedMetrics.awaitingApprovalDuration}ms` : '';
    const statusIcon = status === 'completed' ? '✅' : status === 'cancelled' ? '⏹️' : '❌';
    const statusText = status === 'completed' ? '完成' : status === 'cancelled' ? '取消' : '失败';
    
    // 显示结果预览（前100个字符）
    let resultPreview = '';
    if (status === 'completed' && updatedMetrics.result) {
      const preview = updatedMetrics.result.length > 100 
        ? updatedMetrics.result.substring(0, 100) + '...' 
        : updatedMetrics.result;
      resultPreview = ` | 结果: ${preview}`;
    } else if (status === 'error' && error) {
      resultPreview = ` | 错误: ${error}`;
    }
    
    this.logToConsole(`${statusIcon} 工具调用${statusText}: ${metrics.toolName} (ID: ${id}) - 总耗时: ${totalDuration}${pureExecDuration}${waitingTime}${resultPreview}`);
  }

  public startEmbeddingCall(
    id: string,
    model: string,
    promptId: string,
    textCount: number,
    requestTexts?: string[]
  ): void {
    const metrics: EmbeddingCallMetrics = {
      id,
      model,
      promptId,
      startTime: Date.now(),
      status: 'started',
      textCount,
      requestTexts,
    };

    // 融合模式：只在内存中保存数据，不记录start事件到文件
    this.embeddingCalls.set(id, metrics);
    this.logToConsole(`🔗 Embedding调用开始: ${model} (ID: ${id}, 文本数量: ${textCount})`);
  }

  public endEmbeddingCall(
    id: string,
    status: 'completed' | 'error',
    error?: string,
    vectorDimensions?: number
  ): void {
    const metrics = this.embeddingCalls.get(id);
    if (!metrics) return;

    const endTime = Date.now();
    const updatedMetrics: EmbeddingCallMetrics = {
      ...metrics,
      endTime,
      duration: endTime - metrics.startTime,
      status,
      error,
      vectorDimensions,
    };

    this.embeddingCalls.set(id, updatedMetrics);
    // 融合模式：记录完整事件（包含start+end信息）
    this.recordEvent('embedding_call', status === 'completed' ? 'completed' : 'error', updatedMetrics);
    
    const durationText = updatedMetrics.duration ? `${updatedMetrics.duration}ms` : 'unknown';
    const vectorText = vectorDimensions ? ` (向量维度: ${vectorDimensions})` : '';
    const statusIcon = status === 'completed' ? '✅' : '❌';
    
    this.logToConsole(`${statusIcon} Embedding调用${status === 'completed' ? '完成' : '失败'}: ${metrics.model} (ID: ${id}) - 耗时: ${durationText}${vectorText}`);
  }

  private recordEvent(type: MonitoringEvent['type'], event: MonitoringEvent['event'], data: LLMCallMetrics | ToolCallMetrics | UserConfirmationMetrics | EmbeddingCallMetrics): void {
    const monitoringEvent: MonitoringEvent = {
      timestamp: new Date().toISOString(),
      type,
      event,
      data,
    };

    this.events.push(monitoringEvent);
    this.writeToFile(monitoringEvent);
  }

  private logToConsole(message: string): void {
    if (this.enableConsoleOutput) {
      console.log(`[监控] ${new Date().toISOString()} ${message}`);
    }
  }


  private isJsonString(text: string): boolean {
    /**
     * 判断字符串是否可能是JSON
     */
    const trimmed = text.trim();
    return (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
           (trimmed.startsWith('[') && trimmed.endsWith(']'));
  }

  private writeToFile(event: MonitoringEvent): void {
    if (!this.enableFileOutput || !this.outputFile) return;

    try {
      const fs = require('fs');
      
      // 直接替换原始数据中的JSON字符串字段为解析后的内容
      const processedData = this.processDataForStorage(event.data);
      const enhancedEvent = {
        ...event,
        data: processedData
      };
      
      const line = JSON.stringify(enhancedEvent) + '\n';
      fs.appendFileSync(this.outputFile, line, 'utf8');
    } catch (error) {
      // Silently ignore file write errors to avoid disrupting the main flow
    }
  }

  private processDataForStorage(data: any): any {
    /**
     * 处理数据用于存储，将JSON字符串字段替换为解析后的对象
     */
    if (typeof data !== 'object' || data === null) {
      return data;
    }

    if (Array.isArray(data)) {
      return data.map(item => this.processDataForStorage(item));
    }

    const processed: any = {};
    for (const [key, value] of Object.entries(data)) {
      if (typeof value === 'string' && this.isJsonString(value)) {
        try {
          // 尝试解析JSON字符串，成功则替换为解析后的对象
          const parsedValue = JSON.parse(value);
          processed[key] = this.processDataForStorage(parsedValue); // 递归处理
        } catch {
          // 解析失败则保持原始字符串
          processed[key] = value;
        }
      } else if (typeof value === 'object') {
        processed[key] = this.processDataForStorage(value);
      } else {
        processed[key] = value;
      }
    }
    return processed;
  }

  public getLLMCallMetrics(id: string): LLMCallMetrics | undefined {
    return this.llmCalls.get(id);
  }

  public getToolCallMetrics(id: string): ToolCallMetrics | undefined {
    return this.toolCalls.get(id);
  }

  public getEmbeddingCallMetrics(id: string): EmbeddingCallMetrics | undefined {
    return this.embeddingCalls.get(id);
  }

  public getAllMetrics(): { llmCalls: LLMCallMetrics[]; toolCalls: ToolCallMetrics[]; embeddingCalls: EmbeddingCallMetrics[] } {
    return {
      llmCalls: Array.from(this.llmCalls.values()),
      toolCalls: Array.from(this.toolCalls.values()),
      embeddingCalls: Array.from(this.embeddingCalls.values()),
    };
  }

  public getEvents(): MonitoringEvent[] {
    return [...this.events];
  }

  public clearMetrics(): void {
    this.llmCalls.clear();
    this.toolCalls.clear();
    this.embeddingCalls.clear();
    this.events.length = 0;
  }

  public printSummary(): void {
    const llmCalls = Array.from(this.llmCalls.values());
    const toolCalls = Array.from(this.toolCalls.values());
    const embeddingCalls = Array.from(this.embeddingCalls.values());

    console.log('\n📊 监控总结:');
    console.log(`LLM调用: ${llmCalls.length}次`);
    console.log(`工具调用: ${toolCalls.length}次`);
    console.log(`Embedding调用: ${embeddingCalls.length}次`);

    const completedLLMCalls = llmCalls.filter(c => c.status === 'completed');
    if (completedLLMCalls.length > 0) {
      const avgDuration = completedLLMCalls.reduce((sum, c) => sum + (c.duration || 0), 0) / completedLLMCalls.length;
      const totalTokens = completedLLMCalls.reduce((sum, c) => sum + (c.totalTokens || 0), 0);
      console.log(`LLM平均响应时间: ${avgDuration.toFixed(0)}ms`);
      console.log(`LLM总Token消耗: ${totalTokens}`);
    }

    const completedToolCalls = toolCalls.filter(c => c.status === 'completed');
    if (completedToolCalls.length > 0) {
      const avgDuration = completedToolCalls.reduce((sum, c) => sum + (c.duration || 0), 0) / completedToolCalls.length;
      console.log(`工具平均执行时间: ${avgDuration.toFixed(0)}ms`);
    }

    const completedEmbeddingCalls = embeddingCalls.filter(c => c.status === 'completed');
    if (completedEmbeddingCalls.length > 0) {
      const avgDuration = completedEmbeddingCalls.reduce((sum, c) => sum + (c.duration || 0), 0) / completedEmbeddingCalls.length;
      const totalTexts = completedEmbeddingCalls.reduce((sum, c) => sum + c.textCount, 0);
      console.log(`Embedding平均响应时间: ${avgDuration.toFixed(0)}ms`);
      console.log(`Embedding总文本数量: ${totalTexts}`);
    }
    console.log('');
  }
}

// Export a singleton instance
export const monitoringService = MonitoringService.getInstance();
