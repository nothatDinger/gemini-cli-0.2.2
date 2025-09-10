#!/usr/bin/env python3
"""
Gemini CLI 监控数据甘特图生成器
从trace.jsonl文件读取监控数据，生成交互式甘特图
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import argparse

class GanttChartGenerator:
    def __init__(self, trace_file: str = "trace.jsonl"):
        self.trace_file = trace_file
        self.events: List[Dict[str, Any]] = []
        self.llm_calls: Dict[str, Dict[str, Any]] = {}
        self.tool_calls: Dict[str, Dict[str, Any]] = {}
        self.embedding_calls: Dict[str, Dict[str, Any]] = {}
        self.user_confirmations: Dict[str, Dict[str, Any]] = {}
        
    def load_trace_data(self) -> bool:
        """加载trace数据"""
        try:
            with open(self.trace_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        self.events.append(event)
                        
                        # 处理事件数据
                        if event['type'] == 'llm_call':
                            self._process_llm_event(event)
                        elif event['type'] == 'tool_call':
                            self._process_tool_event(event)
                        elif event['type'] == 'embedding_call':
                            self._process_embedding_event(event)
                        elif event['type'] == 'user_confirmation':
                            self._process_user_confirmation_event(event)
                            
                    except json.JSONDecodeError as e:
                        print(f"警告：第{line_num}行JSON格式错误: {e}", file=sys.stderr)
                        continue
                        
            return len(self.events) > 0
            
        except FileNotFoundError:
            print(f"错误：找不到文件 '{self.trace_file}'", file=sys.stderr)
            return False
        except Exception as e:
            print(f"错误：读取文件时发生异常: {e}", file=sys.stderr)
            return False
    
    def _process_llm_event(self, event: Dict[str, Any]) -> None:
        """处理LLM调用事件"""
        data = event['data']
        call_id = data['id']
        
        if call_id not in self.llm_calls:
            self.llm_calls[call_id] = {
                'id': call_id,
                'model': data['model'],
                'promptId': data.get('promptId', ''),
                'status': data['status'],
                'start_time': None,
                'end_time': None,
                'duration': None,
                'tokens': data.get('totalTokens', 0),
                'error': data.get('error', ''),
                'request_text': '',
                'response_text': '',
                'events': []
            }
        
        # 更新调用信息
        call_info = self.llm_calls[call_id]
        call_info['events'].append(event)
        call_info['status'] = data['status']
        
        # 融合模式：只处理completed和error事件，包含所有信息
        if event['event'] in ['completed', 'error']:
            # 设置时间信息
            call_info['start_time'] = data['startTime']
            call_info['end_time'] = data.get('endTime', data['startTime'])
            call_info['duration'] = data.get('duration', 0)
            call_info['tokens'] = data.get('totalTokens', 0)
            
            # 保存请求文本
            if 'requestText' in data:
                request_data = data['requestText']
                if isinstance(request_data, (dict, list)):
                    call_info['request_text'] = json.dumps(request_data)
                else:
                    call_info['request_text'] = str(request_data)
            
            # 保存响应文本
            if 'responseText' in data:
                response_data = data['responseText']
                if isinstance(response_data, (dict, list)):
                    call_info['response_text'] = json.dumps(response_data)
                else:
                    call_info['response_text'] = str(response_data)
            
            # 保存错误信息
            if data.get('error'):
                call_info['error'] = data['error']
    
    def _process_tool_event(self, event: Dict[str, Any]) -> None:
        """处理工具调用事件"""
        data = event['data']
        call_id = data['id']
        
        if call_id not in self.tool_calls:
            self.tool_calls[call_id] = {
                'id': call_id,
                'toolName': data['toolName'],
                'callId': data.get('callId', ''),
                'promptId': data.get('promptId', ''),
                'status': data['status'],
                'start_time': None,
                'end_time': None,
                'execution_start_time': None,
                'execution_end_time': None,
                'duration': None,
                'execution_duration': None,
                'args': data.get('args', {}),
                'error': data.get('error', ''),
                'events': []
            }
        
        # 更新调用信息
        call_info = self.tool_calls[call_id]
        call_info['events'].append(event)
        call_info['status'] = data['status']
        
        # 融合模式：只处理completed、cancelled和error事件，包含所有信息
        if event['event'] in ['completed', 'cancelled', 'error']:
            # 设置时间和基础信息
            call_info['start_time'] = data['startTime']
            call_info['end_time'] = data.get('endTime', data['startTime'])
            call_info['duration'] = data.get('duration', 0)
            call_info['args'] = data.get('args', {})
            
            # 执行时间相关信息
            call_info['execution_start_time'] = data.get('executionStartTime')
            call_info['execution_end_time'] = data.get('executionEndTime')
            call_info['execution_duration'] = data.get('executionDuration', data.get('pureExecutionDuration', 0))
            
            # 错误信息
            if data.get('error'):
                call_info['error'] = data['error']
    
    def _process_embedding_event(self, event: Dict[str, Any]) -> None:
        """处理Embedding调用事件"""
        data = event['data']
        call_id = data['id']
        
        if call_id not in self.embedding_calls:
            self.embedding_calls[call_id] = {
                'id': call_id,
                'model': data['model'],
                'promptId': data.get('promptId', ''),
                'status': data['status'],
                'start_time': None,
                'end_time': None,
                'duration': None,
                'textCount': data.get('textCount', 0),
                'vectorDimensions': data.get('vectorDimensions'),
                'requestTexts': data.get('requestTexts', []),
                'error': None,
                'events': []
            }
        
        call_info = self.embedding_calls[call_id]
        call_info['events'].append(event)
        call_info['status'] = data['status']
        
        # 融合模式：只处理completed和error事件，包含所有信息
        if event['event'] in ['completed', 'error']:
            # 设置时间和基础信息
            call_info['start_time'] = data['startTime']
            call_info['end_time'] = data.get('endTime', data['startTime'])
            call_info['duration'] = data.get('duration', 0)
            
            # Embedding特有信息
            call_info['textCount'] = data.get('textCount', 0)
            call_info['requestTexts'] = data.get('requestTexts', [])
            call_info['vectorDimensions'] = data.get('vectorDimensions')
            
            # 错误信息
            if data.get('error'):
                call_info['error'] = data['error']
    
    def _process_user_confirmation_event(self, event: Dict[str, Any]) -> None:
        """处理用户确认事件"""
        data = event['data']
        confirmation_id = data['id']
        tool_call_id = data['toolCallId']
        
        # 记录用户确认事件
        self.user_confirmations[confirmation_id] = {
            'id': confirmation_id,
            'toolCallId': tool_call_id,
            'toolName': data['toolName'],
            'confirmationType': data['confirmationType'],
            'timestamp': data['timestamp'],
            'event': event['event'],  # approval_requested, approval_granted, approval_denied
            'callId': data.get('callId', ''),
            'promptId': data.get('promptId', '')
        }
        
        # 将确认信息关联到对应的工具调用
        if tool_call_id in self.tool_calls:
            if 'confirmations' not in self.tool_calls[tool_call_id]:
                self.tool_calls[tool_call_id]['confirmations'] = []
            self.tool_calls[tool_call_id]['confirmations'].append(self.user_confirmations[confirmation_id])
    
    def _timestamp_to_datetime(self, timestamp: int) -> datetime:
        """将时间戳转换为datetime对象"""
        return datetime.fromtimestamp(timestamp / 1000.0)
    
    def _get_status_color(self, status: str, is_tool: bool = False, is_embedding: bool = False) -> str:
        """根据状态获取颜色"""
        if is_embedding:
            # Embedding调用使用绿色系列
            color_map = {
                'started': '#E0FFE0',       # 浅绿色
                'completed': '#00CED1',     # 深绿松石色
                'error': '#FF6347',         # 番茄红
            }
        elif is_tool:
            color_map = {
                'started': '#FFE4B5',      # 浅橙色
                'validating': '#FFA500',    # 橙色
                'awaiting_approval': '#FF8C00',  # 深橙色
                'scheduled': '#FF6347',     # 番茄红
                'executing': '#FF4500',     # 橙红色
                'completed': '#32CD32',     # 绿色
                'error': '#FF0000',         # 红色
                'cancelled': '#FF0000'      # 红色
            }
        else:
            # LLM调用使用蓝色系列
            color_map = {
                'started': '#ADD8E6',       # 浅蓝色
                'completed': '#1E90FF',     # 道奇蓝
                'error': '#FF0000'          # 红色
            }
        return color_map.get(status, '#CCCCCC')
    
    def _analyze_missing_events(self) -> None:
        """分析可能遗漏的事件"""
        # 统计LLM调用中包含functionCall的数量
        llm_with_function_calls = 0
        for llm_call in self.llm_calls.values():
            response_text = llm_call.get('response_text', '')
            if isinstance(response_text, str) and 'functionCall' in response_text:
                llm_with_function_calls += 1
        
        tool_calls_count = len(self.tool_calls)
        
        if llm_with_function_calls > tool_calls_count:
            missing_count = llm_with_function_calls - tool_calls_count
            print(f"⚠️ 检测到数据不一致:")
            print(f"   LLM调用包含函数调用: {llm_with_function_calls}个")
            print(f"   记录的工具调用事件: {tool_calls_count}个")
            print(f"   可能遗漏的工具调用: {missing_count}个")
            print("   这可能由于工具调用失败、取消或监控系统问题导致")
    
    def create_gantt_chart(self) -> go.Figure:
        """创建甘特图"""
        # 检测可能遗漏的事件
        self._analyze_missing_events()
        
        fig = go.Figure()
        
        # 计算时间范围
        all_times = []
        for call in list(self.llm_calls.values()) + list(self.tool_calls.values()) + list(self.embedding_calls.values()):
            if call['start_time']:
                all_times.append(call['start_time'])
            if call['end_time']:
                all_times.append(call['end_time'])
        
        if not all_times:
            print("警告：没有找到有效的时间数据", file=sys.stderr)
            return fig
        
        min_time = min(all_times)
        max_time = max(all_times)
        
        # 准备甘特图数据
        gantt_data = []
        y_position = 0
        
        # 添加LLM调用
        for call_id, call in self.llm_calls.items():
            if not call['start_time'] or not call['end_time']:
                continue
                
            start_dt = self._timestamp_to_datetime(call['start_time'])
            end_dt = self._timestamp_to_datetime(call['end_time'])
            
            # 构建显示文本
            model_short = call['model'].replace('gemini-', '')
            duration_ms = call['duration'] or 0
            tokens = call['tokens']
            
            # 辅助函数：过滤thoughtSignature字段
            def filter_thought_signature(data):
                if isinstance(data, dict):
                    filtered = {}
                    for key, value in data.items():
                        if key != 'thoughtSignature':
                            if isinstance(value, (dict, list)):
                                filtered[key] = filter_thought_signature(value)
                            else:
                                filtered[key] = value
                    return filtered
                elif isinstance(data, list):
                    return [filter_thought_signature(item) for item in data]
                else:
                    return data
            
            # 辅助函数：完整文本显示，保持原始格式并进行HTML转义
            def text_with_wrapping(text: str, line_length: int = 60) -> str:
                if not text:
                    return "无"
                
                # 首先进行HTML转义，防止特殊字符破坏HTML结构
                import html
                text = html.escape(str(text))
                
                # 将原始换行符转换为HTML换行
                text = text.replace('\n', '<br>')
                # 对于非常长的行，按指定长度进行软换行
                lines = []
                for line in text.split('<br>'):
                    if len(line) <= line_length:
                        lines.append(line)
                    else:
                        # 对超长行进行智能换行
                        words = line.split()
                        current_line = ""
                        for word in words:
                            if len(current_line + " " + word) <= line_length:
                                if current_line:
                                    current_line += " " + word
                                else:
                                    current_line = word
                            else:
                                if current_line:
                                    lines.append(current_line)
                                current_line = word
                        if current_line:
                            lines.append(current_line)
                
                return "<br>".join(lines)  # 显示所有行，不限制行数
            
            # 提取并简化request和response信息
            request_preview = ""
            response_preview = ""
            
            if call['request_text']:
                # 处理请求文本，只提取最新的用户输入（避免显示累积的对话历史）
                try:
                    if isinstance(call['request_text'], str):
                        request_data = json.loads(call['request_text'])
                    else:
                        request_data = call['request_text']
                    
                    if isinstance(request_data, list) and len(request_data) > 0:
                        # 只查找最后一个用户输入（最新的请求）
                        latest_user_text = ""
                        for item in reversed(request_data):  # 从后往前查找
                            if item.get('role') == 'user' and 'parts' in item:
                                for part in item['parts']:
                                    if 'text' in part:
                                        latest_user_text = part['text']
                                        break
                                if latest_user_text:
                                    break
                        request_preview = text_with_wrapping(latest_user_text, 60)
                    else:
                        request_preview = text_with_wrapping(str(request_data), 60)
                except:
                    request_preview = text_with_wrapping(str(call['request_text']), 60)
            
            if call['response_text']:
                # 处理响应文本（现在可能已经是解析后的JSON对象）
                try:
                    if isinstance(call['response_text'], str):
                        response_data = json.loads(call['response_text'])
                    else:
                        response_data = call['response_text']
                    
                    # 过滤掉thoughtSignature字段
                    response_data = filter_thought_signature(response_data)
                    
                    if isinstance(response_data, dict):
                        # 尝试提取candidates中的文本
                        if 'candidates' in response_data:
                            candidates = response_data['candidates']
                            if isinstance(candidates, list) and len(candidates) > 0:
                                candidate = candidates[0]
                                if 'content' in candidate:
                                    content = candidate['content']
                                    if 'parts' in content:
                                        for part in content['parts']:
                                            if 'text' in part:
                                                text_content = part['text']
                                                # 处理flash-lite模型的特殊响应格式（text字段可能是对象）
                                                if isinstance(text_content, dict):
                                                    # 提取对象中的第一个值作为文本内容
                                                    if text_content:
                                                        first_key = list(text_content.keys())[0]
                                                        response_preview = text_with_wrapping(str(text_content[first_key]), 60)
                                                else:
                                                    response_preview = text_with_wrapping(str(text_content), 60)
                                                break
                        if not response_preview:
                            response_preview = text_with_wrapping(str(response_data), 60)
                    else:
                        response_preview = text_with_wrapping(str(response_data), 60)
                except:
                    response_preview = text_with_wrapping(str(call['response_text']), 60)

            task_name = f"🤖 LLM-{model_short}"
            # 使用换行显示长文本内容
            hover_text = (
                f"<b>LLM-{model_short}</b><br>"
                f"状态: {call['status']} | 耗时: {duration_ms}ms<br>"
                f"Tokens: {tokens}<br>"
                f"<br><b>最新请求:</b><br>{request_preview}<br>"
                f"<br><b>响应:</b><br>{response_preview}"
            )
            
            if call['error']:
                error_text = text_with_wrapping(call['error'], 60)
                hover_text += f"<br><br><b>错误:</b><br>{error_text}"
            
            gantt_data.append({
                'Task': task_name,
                'Start': start_dt,
                'Finish': end_dt,
                'Duration': duration_ms,
                'Type': 'LLM',
                'Status': call['status'],
                'Y': y_position,
                'Hover': hover_text,
                'Color': self._get_status_color(call['status'], False)
            })
            y_position += 1
        
        # 添加工具调用
        for call_id, call in self.tool_calls.items():
            if not call['start_time'] or not call['end_time']:
                continue
                
            start_dt = self._timestamp_to_datetime(call['start_time'])
            end_dt = self._timestamp_to_datetime(call['end_time'])
            
            # 工具名称缩写
            tool_name = call['toolName']
            tool_short = tool_name.replace('_', ' ').title()
            
            duration_ms = call['duration'] or 0
            exec_duration_ms = call['execution_duration'] or 0
            
            task_name = f"🔧 {tool_short}"
            
            # 辅助函数：完整文本显示，保持原始格式并进行HTML转义（与LLM调用保持一致）
            def text_with_wrapping(text: str, line_length: int = 60) -> str:
                if not text:
                    return "无"
                
                # 首先进行HTML转义，防止特殊字符破坏HTML结构
                import html
                text = html.escape(str(text))
                
                # 将原始换行符转换为HTML换行
                text = text.replace('\n', '<br>')
                # 对于非常长的行，按指定长度进行软换行
                lines = []
                for line in text.split('<br>'):
                    if len(line) <= line_length:
                        lines.append(line)
                    else:
                        # 对超长行进行智能换行
                        words = line.split()
                        current_line = ""
                        for word in words:
                            if len(current_line + " " + word) <= line_length:
                                if current_line:
                                    current_line += " " + word
                                else:
                                    current_line = word
                            else:
                                if current_line:
                                    lines.append(current_line)
                                current_line = word
                        if current_line:
                            lines.append(current_line)
                
                return "<br>".join(lines)  # 显示所有行，不限制行数
            
            # 构建简化的悬停提示文本，只显示关键信息
            hover_text = (
                f"<b>{tool_name}</b><br>"
                f"状态: {call['status']} | 总耗时: {duration_ms}ms<br>"
                f"执行耗时: {exec_duration_ms}ms"
            )
            
            # 显示用户确认信息（如果有的话）
            if 'confirmations' in call and call['confirmations']:
                hover_text += "<br><br><b>用户确认:</b>"
                for conf in call['confirmations']:
                    conf_time = datetime.fromtimestamp(conf['timestamp'] / 1000.0).strftime('%H:%M:%S.%f')[:-3]
                    hover_text += f"<br>• {conf['event']} at {conf_time}"
                    if conf['confirmationType'] != 'unknown':
                        hover_text += f" ({conf['confirmationType']})"
            
            # 显示所有重要参数，使用完整文本
            if call['args']:
                hover_text += f"<br><br><b>参数:</b>"
                for key, value in call['args'].items():
                    value_text = text_with_wrapping(str(value), 60)
                    hover_text += f"<br><b>{key}:</b><br>{value_text}"
            
            if call['error']:
                error_text = text_with_wrapping(call['error'], 60)
                hover_text += f"<br><br><b>错误:</b><br>{error_text}"
            
            gantt_data.append({
                'Task': task_name,
                'Start': start_dt,
                'Finish': end_dt,
                'Duration': duration_ms,
                'Type': 'Tool',
                'Status': call['status'],
                'Y': y_position,
                'Hover': hover_text,
                'Color': self._get_status_color(call['status'], True)
            })
            y_position += 1
        
        # 添加Embedding调用
        for call_id, call in self.embedding_calls.items():
            if not call['start_time'] or not call['end_time']:
                continue
                
            start_dt = self._timestamp_to_datetime(call['start_time'])
            end_dt = self._timestamp_to_datetime(call['end_time'])
            duration_ms = call['duration'] or 0
            
            def text_with_wrapping(text, line_length=60):
                """处理文本换行，限制长度但保持完整性，并进行HTML转义"""
                if not text:
                    return ""
                
                # 首先进行HTML转义，防止特殊字符破坏HTML结构
                import html
                text = html.escape(str(text))
                
                # 转换换行符为HTML
                text = text.replace('\n', '<br>')
                
                # 对每行进行单词级别的换行处理
                lines = text.split('<br>')
                wrapped_lines = []
                for line in lines:
                    if len(line) <= line_length:
                        wrapped_lines.append(line)
                    else:
                        # 按单词进行换行
                        words = line.split(' ')
                        current_line = ""
                        for word in words:
                            if len(current_line + " " + word) <= line_length:
                                current_line += " " + word if current_line else word
                            else:
                                if current_line:
                                    wrapped_lines.append(current_line)
                                current_line = word
                        if current_line:
                            wrapped_lines.append(current_line)
                
                return "<br>".join(wrapped_lines)
            
            task_name = f"🔗 Embedding-{call['model'].replace('gemini-embedding-', '')}"
            hover_text = (
                f"<b>Embedding-{call['model']}</b><br>"
                f"状态: {call['status']} | 耗时: {duration_ms}ms<br>"
                f"文本数量: {call['textCount']}"
            )
            
            if call.get('vectorDimensions'):
                hover_text += f"<br>向量维度: {call['vectorDimensions']}"
            
            # 显示请求文本（如果有的话）
            if call.get('requestTexts') and len(call['requestTexts']) > 0:
                hover_text += f"<br><br><b>输入文本:</b>"
                # 限制显示前3个文本，避免过长
                for i, text in enumerate(call['requestTexts'][:3]):
                    text_preview = text_with_wrapping(text, 60)
                    hover_text += f"<br><b>文本{i+1}:</b><br>{text_preview}"
                if len(call['requestTexts']) > 3:
                    hover_text += f"<br>... 还有 {len(call['requestTexts'])-3} 个文本"
            
            if call['error']:
                error_text = text_with_wrapping(call['error'], 60)
                hover_text += f"<br><br><b>错误:</b><br>{error_text}"
            
            gantt_data.append({
                'Task': task_name,
                'Start': start_dt,
                'Finish': end_dt,
                'Duration': duration_ms,
                'Type': 'Embedding',
                'Status': call['status'],
                'Y': y_position,
                'Hover': hover_text,
                'Color': self._get_status_color(call['status'], False, True)
            })
            y_position += 1
        
        # 按开始时间排序
        gantt_data.sort(key=lambda x: x['Start'])
        
        # 重新分配Y位置
        for i, item in enumerate(gantt_data):
            item['Y'] = i
        
        # 计算所有事件的实际持续时间，找出最短持续时间
        actual_durations = []
        for item in gantt_data:
            duration_ms = (item['Finish'] - item['Start']).total_seconds() * 1000
            if duration_ms > 0:  # 只考虑正的持续时间
                actual_durations.append(duration_ms)
        
        # 设置原子长度（最小可见长度）
        min_atomic_duration_ms = 100  # 固定10毫秒的横向原子长度
        
        # 创建甘特图条形
        for item in gantt_data:
            # 计算持续时间（以毫秒为单位）
            duration_ms = (item['Finish'] - item['Start']).total_seconds() * 1000
            
            # 确保每个bar都有最小可见长度
            display_duration = max(duration_ms, min_atomic_duration_ms)
            
            fig.add_trace(go.Bar(
                x=[display_duration],
                y=[item['Y']],
                base=[item['Start']],
                orientation='h',
                name=item['Task'],
                marker=dict(
                    color=item['Color'],
                    line=dict(color='rgba(0,0,0,0.2)', width=1)  # 添加边框增强可见性
                ),
                hovertemplate=item['Hover'] + f'<br>实际持续时间: {duration_ms:.1f}ms<extra></extra>',
                showlegend=False
            ))
        
        # 更新布局
        fig.update_layout(
            title={
                'text': '🔍 Gemini CLI 监控数据甘特图<br><sub>原子长度: {:.1f}ms | 包含用户确认事件信息</sub>'.format(min_atomic_duration_ms),
                'x': 0.5,
                'font': {'size': 20}
            },
            xaxis_title='时间轴',
            yaxis_title='调用事件',
            xaxis=dict(
                type='date',
                tickformat='%H:%M:%S.%L',
                title_font_size=14,
                showgrid=True,           # 显示垂直网格线
                gridwidth=1,             # 网格线宽度
                gridcolor='rgba(128,128,128,0.3)',  # 网格线颜色（浅灰色）
                zeroline=True,           # 显示零线
                zerolinewidth=2,         # 零线宽度
                zerolinecolor='rgba(128,128,128,0.5)'  # 零线颜色
            ),
            yaxis=dict(
                tickmode='array',
                tickvals=[item['Y'] for item in gantt_data],
                ticktext=[item['Task'] for item in gantt_data],
                title_font_size=14,
                showgrid=True,           # 显示水平网格线
                gridwidth=1,             # 网格线宽度
                gridcolor='rgba(128,128,128,0.3)',  # 网格线颜色（浅灰色）
                zeroline=True,           # 显示零线
                zerolinewidth=2,         # 零线宽度
                zerolinecolor='rgba(128,128,128,0.5)'  # 零线颜色
            ),
            height=max(600, len(gantt_data) * 40 + 200),
            template='plotly_white',
            hovermode='closest',
            plot_bgcolor='rgba(245,245,245,0.8)',  # 设置绘图区域背景色（浅灰色）
            autosize=True,  # 启用自动大小调整
            margin=dict(l=150, r=50, t=100, b=50)  # 设置合适的边距
        )
        
        # 添加图例
        legend_items = [
            {'name': '🤖 LLM调用', 'color': '#1E90FF'},
            {'name': '🔧 工具调用', 'color': '#FF6347'},
            {'name': '🔗 Embedding调用', 'color': '#00CED1'},
            {'name': '✅ 成功', 'color': '#32CD32'},
            {'name': '❌ 错误', 'color': '#FF0000'}
        ]
        
        for item in legend_items:
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode='markers',
                marker=dict(size=10, color=item['color']),
                name=item['name'],
                showlegend=True
            ))
        
        return fig
    
    def save_chart(self, fig: go.Figure, output_file: str = "gantt_chart.html") -> None:
        """保存甘特图到HTML文件"""
        # 配置响应式HTML输出
        config = {
            'responsive': True,  # 启用响应式设计
            'displayModeBar': True,  # 显示工具栏
            'displaylogo': False,  # 隐藏Plotly logo
            'modeBarButtonsToRemove': ['pan2d', 'select2d', 'lasso2d'],  # 移除不需要的工具
        }
        
        # 保存HTML时确保中文字符不被转义
        import json
        fig.write_html(
            output_file, 
            include_plotlyjs='cdn',
            config=config,
            div_id="gantt-chart"
        )
        
        # 在生成的HTML文件中添加自定义CSS样式以支持换行显示
        with open(output_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 修复Unicode转义问题 - 将JSON中被转义的Unicode字符恢复为正常字符
        html_content = html_content.replace('\\u003c', '<')
        html_content = html_content.replace('\\u003e', '>')
        html_content = html_content.replace('\\u002f', '/')
        html_content = html_content.replace('\\u0027', "'")
        html_content = html_content.replace('\\u0026', '&')
        html_content = html_content.replace('\\u0022', '"')
        
        custom_css = """
        <style>
        .hoverlayer .hovertext {
            max-width: 700px !important;
            max-height: 600px !important;
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
            overflow-y: auto !important;
            overflow-x: hidden !important;
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
            font-size: 12px !important;
            line-height: 1.5 !important;
            padding: 16px !important;
            border-radius: 8px !important;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
            background-color: rgba(255,255,255,0.98) !important;
            border: 1px solid rgba(0,0,0,0.1) !important;
            backdrop-filter: blur(5px) !important;
        }
        .hoverlayer .hovertext text {
            font-size: 12px !important;
        }
        /* 添加滚动条样式 */
        .hoverlayer .hovertext::-webkit-scrollbar {
            width: 6px !important;
        }
        .hoverlayer .hovertext::-webkit-scrollbar-track {
            background: rgba(0,0,0,0.1) !important;
            border-radius: 3px !important;
        }
        .hoverlayer .hovertext::-webkit-scrollbar-thumb {
            background: rgba(0,0,0,0.3) !important;
            border-radius: 3px !important;
        }
        .hoverlayer .hovertext::-webkit-scrollbar-thumb:hover {
            background: rgba(0,0,0,0.5) !important;
        }
        </style>
        """
        
        # 在</head>标签前插入CSS
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', custom_css + '\n</head>')
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        print(f"✅ 甘特图已保存到: {output_file}")
    
    def show_chart(self, fig: go.Figure) -> None:
        """显示甘特图"""
        fig.show()
    
    def print_summary(self) -> None:
        """打印数据摘要"""
        llm_count = len(self.llm_calls)
        tool_count = len(self.tool_calls)
        embedding_count = len(self.embedding_calls)
        
        print(f"\n📊 数据摘要:")
        print(f"   LLM调用: {llm_count}次")
        print(f"   工具调用: {tool_count}次")
        print(f"   Embedding调用: {embedding_count}次")
        print(f"   总事件: {len(self.events)}条")
        
        if llm_count > 0:
            total_llm_duration = sum(call.get('duration', 0) or 0 for call in self.llm_calls.values())
            total_tokens = sum(call.get('tokens', 0) or 0 for call in self.llm_calls.values())
            print(f"   LLM总耗时: {total_llm_duration}ms")
            print(f"   总Token消耗: {total_tokens}")
        
        if tool_count > 0:
            total_tool_duration = sum(call.get('duration', 0) or 0 for call in self.tool_calls.values())
            print(f"   工具总耗时: {total_tool_duration}ms")
        
        if embedding_count > 0:
            total_embedding_duration = sum(call.get('duration', 0) or 0 for call in self.embedding_calls.values())
            total_texts = sum(call.get('textCount', 0) for call in self.embedding_calls.values())
            print(f"   Embedding总耗时: {total_embedding_duration}ms")
            print(f"   处理文本总数: {total_texts}")

def main():
    parser = argparse.ArgumentParser(description='生成Gemini CLI监控数据甘特图')
    parser.add_argument('trace_file', nargs='?', default='trace.jsonl',
                       help='trace文件路径 (默认: trace.jsonl)')
    parser.add_argument('-o', '--output', default='gantt_chart.html',
                       help='输出HTML文件名 (默认: gantt_chart.html)')
    parser.add_argument('--show', action='store_true',
                       help='在浏览器中显示图表')
    parser.add_argument('--no-save', action='store_true',
                       help='不保存HTML文件')
    
    args = parser.parse_args()
    
    # 创建甘特图生成器
    generator = GanttChartGenerator(args.trace_file)
    
    # 加载数据
    if not generator.load_trace_data():
        sys.exit(1)
    
    # 打印摘要
    generator.print_summary()
    
    # 生成甘特图
    print("\n🎨 正在生成甘特图...")
    fig = generator.create_gantt_chart()
    
    # 保存或显示图表
    if not args.no_save:
        generator.save_chart(fig, args.output)
    
    if args.show:
        print("🌐 正在浏览器中打开图表...")
        generator.show_chart(fig)
    
    print("\n✨ 甘特图生成完成！")

if __name__ == "__main__":
    main()
