#!/usr/bin/env python3
"""
Gemini CLI 监控数据分析脚本
"""

import json
import sys
from datetime import datetime
from collections import defaultdict

def parse_timestamp(ts):
    """解析ISO时间戳"""
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))

def analyze_trace_file(filename='trace.jsonl'):
    """分析trace.jsonl文件"""
    print("🔍 Gemini CLI 监控数据分析")
    print("=" * 50)
    
    llm_calls = []
    tool_calls = []
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    if event['type'] == 'llm_call':
                        llm_calls.append(event)
                    elif event['type'] == 'tool_call':
                        tool_calls.append(event)
    except FileNotFoundError:
        print(f"❌ 文件 {filename} 不存在")
        return
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析错误: {e}")
        return
    
    # 分析LLM调用
    print("\n📊 LLM调用统计:")
    print("-" * 30)
    
    llm_start_events = [e for e in llm_calls if e['event'] == 'start']
    llm_end_events = [e for e in llm_calls if e['event'] == 'end']
    llm_error_events = [e for e in llm_calls if e['event'] == 'error']
    
    print(f"总调用次数: {len(llm_start_events)}")
    print(f"成功完成: {len(llm_end_events)}")
    print(f"失败次数: {len(llm_error_events)}")
    
    if llm_end_events:
        durations = [e['data']['duration'] for e in llm_end_events if 'duration' in e['data']]
        tokens = [e['data']['totalTokens'] for e in llm_end_events if 'totalTokens' in e['data']]
        
        if durations:
            print(f"平均响应时间: {sum(durations)/len(durations):.0f}ms")
            print(f"最快响应: {min(durations):.0f}ms")
            print(f"最慢响应: {max(durations):.0f}ms")
        
        if tokens:
            print(f"总Token消耗: {sum(tokens)}")
            print(f"平均Token: {sum(tokens)/len(tokens):.0f}")
    
    # 按模型统计
    models = defaultdict(int)
    for event in llm_start_events:
        model = event['data'].get('model', 'unknown')
        models[model] += 1
    
    print("\n🤖 按模型统计:")
    for model, count in models.items():
        print(f"  {model}: {count}次")
    
    # 分析工具调用
    print("\n🔧 工具调用统计:")
    print("-" * 30)
    
    tool_start_events = [e for e in tool_calls if e['event'] == 'start']
    tool_end_events = [e for e in tool_calls if e['event'] == 'end']
    tool_error_events = [e for e in tool_calls if e['event'] == 'error']
    
    print(f"总调用次数: {len(tool_start_events)}")
    print(f"成功完成: {len(tool_end_events)}")
    print(f"失败次数: {len(tool_error_events)}")
    
    if tool_end_events:
        durations = [e['data']['duration'] for e in tool_end_events if 'duration' in e['data']]
        if durations:
            print(f"平均执行时间: {sum(durations)/len(durations):.0f}ms")
    
    # 按工具统计
    tools = defaultdict(int)
    for event in tool_start_events:
        tool_name = event['data'].get('toolName', 'unknown')
        tools[tool_name] += 1
    
    if tools:
        print("\n🛠️ 按工具统计:")
        for tool, count in tools.items():
            print(f"  {tool}: {count}次")
    
    # 显示工具调用结果详情
    if tool_end_events:
        print("\n📄 工具调用结果详情:")
        print("-" * 50)
        for event in tool_end_events[:5]:  # 只显示前5个
            data = event['data']
            tool_name = data.get('toolName', 'unknown')
            duration = data.get('duration', 0)
            pure_execution = data.get('pureExecutionDuration', duration)
            approval_duration = data.get('awaitingApprovalDuration', 0)
            result = data.get('result', '')
            result_display = data.get('resultDisplay', '')
            
            time_breakdown = f"耗时: {duration}ms"
            if approval_duration > 0:
                time_breakdown += f" (纯执行: {pure_execution}ms, 等待确认: {approval_duration}ms)"
            
            print(f"\n🔧 {tool_name} ({time_breakdown})")
            
            # 显示结果摘要
            if result_display:
                display_preview = result_display[:200] + '...' if len(result_display) > 200 else result_display
                print(f"   摘要: {display_preview}")
            
            # 显示完整结果的预览
            if result and result != result_display:
                result_preview = result[:300] + '...' if len(result) > 300 else result
                print(f"   详细结果: {result_preview}")
        
        if len(tool_end_events) > 5:
            print(f"\n  ... 还有 {len(tool_end_events) - 5} 个工具调用结果")
    
    # 用户确认统计
    all_events = llm_calls + tool_calls  # 先定义all_events
    approval_events = [e for e in all_events if e.get('type') == 'user_confirmation']
    approval_requests = [e for e in approval_events if e.get('event') == 'approval_requested']
    approval_grants = [e for e in approval_events if e.get('event') == 'approval_granted']
    
    if approval_requests or any(data.get('awaitingApprovalDuration', 0) > 0 for data in [e['data'] for e in tool_end_events]):
        print("\n⏳ 用户确认统计:")
        print("-" * 30)
        
        approval_durations = [e['data'].get('awaitingApprovalDuration', 0) for e in tool_end_events 
                             if e['data'].get('awaitingApprovalDuration', 0) > 0]
        
        if approval_durations:
            print(f"需要确认的工具调用: {len(approval_durations)}次")
            print(f"平均等待时间: {sum(approval_durations)/len(approval_durations):.0f}ms")
            print(f"最长等待时间: {max(approval_durations)}ms")
            print(f"最短等待时间: {min(approval_durations)}ms")
            print(f"总等待时间: {sum(approval_durations)}ms")
            
            # 按工具类型统计确认时间
            approval_by_tool = defaultdict(list)
            for event in tool_end_events:
                data = event['data']
                approval_time = data.get('awaitingApprovalDuration', 0)
                if approval_time > 0:
                    tool_name = data.get('toolName', 'unknown')
                    approval_by_tool[tool_name].append(approval_time)
            
            if approval_by_tool:
                print("\n🛠️ 按工具确认时间统计:")
                for tool, times in approval_by_tool.items():
                    avg_time = sum(times) / len(times)
                    print(f"  {tool}: 平均 {avg_time:.0f}ms ({len(times)}次)")
    
    # 时间线分析
    print("\n⏰ 时间线分析:")
    print("-" * 30)
    
    all_events.sort(key=lambda x: x['timestamp'])
    
    for event in all_events[-5:]:  # 显示最后5个事件
        timestamp = parse_timestamp(event['timestamp'])
        event_type = event['type']
        event_name = event['event']
        
        if event_type == 'llm_call':
            model = event['data'].get('model', 'unknown')
            if event_name == 'start':
                print(f"  {timestamp.strftime('%H:%M:%S')} 🚀 LLM调用开始 ({model})")
            elif event_name == 'end':
                duration = event['data'].get('duration', 0)
                tokens = event['data'].get('totalTokens', 0)
                print(f"  {timestamp.strftime('%H:%M:%S')} ✅ LLM调用完成 ({model}) - {duration}ms, {tokens} tokens")
            elif event_name == 'error':
                print(f"  {timestamp.strftime('%H:%M:%S')} ❌ LLM调用失败 ({model})")
        
        elif event_type == 'tool_call':
            tool_name = event['data'].get('toolName', 'unknown')
            if event_name == 'start':
                print(f"  {timestamp.strftime('%H:%M:%S')} 🔧 工具调用开始 ({tool_name})")
            elif event_name == 'end':
                duration = event['data'].get('duration', 0)
                print(f"  {timestamp.strftime('%H:%M:%S')} ✅ 工具调用完成 ({tool_name}) - {duration}ms")
            elif event_name == 'error':
                print(f"  {timestamp.strftime('%H:%M:%S')} ❌ 工具调用失败 ({tool_name})")

if __name__ == '__main__':
    filename = sys.argv[1] if len(sys.argv) > 1 else 'trace.jsonl'
    analyze_trace_file(filename)
