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
                'events': []
            }
        
        # 更新调用信息
        call_info = self.llm_calls[call_id]
        call_info['events'].append(event)
        call_info['status'] = data['status']
        
        if event['event'] == 'start':
            call_info['start_time'] = data['startTime']
        elif event['event'] == 'end':
            call_info['end_time'] = data.get('endTime', data['startTime'])
            call_info['duration'] = data.get('duration', 0)
            call_info['tokens'] = data.get('totalTokens', call_info['tokens'])
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
        
        if event['event'] == 'start':
            call_info['start_time'] = data['startTime']
        elif event['event'] == 'end':
            call_info['end_time'] = data.get('endTime', data['startTime'])
            call_info['duration'] = data.get('duration', 0)
            call_info['execution_start_time'] = data.get('executionStartTime')
            call_info['execution_end_time'] = data.get('executionEndTime')
            call_info['execution_duration'] = data.get('executionDuration', 0)
            if data.get('error'):
                call_info['error'] = data['error']
    
    def _timestamp_to_datetime(self, timestamp: int) -> datetime:
        """将时间戳转换为datetime对象"""
        return datetime.fromtimestamp(timestamp / 1000.0)
    
    def _get_status_color(self, status: str, is_tool: bool = False) -> str:
        """根据状态获取颜色"""
        if is_tool:
            color_map = {
                'started': '#FFE4B5',      # 浅橙色
                'validating': '#FFA500',    # 橙色
                'awaiting_approval': '#FF8C00',  # 深橙色
                'scheduled': '#FF6347',     # 番茄红
                'executing': '#FF4500',     # 橙红色
                'completed': '#32CD32',     # 绿色
                'error': '#FF0000',         # 红色
                'cancelled': '#808080'      # 灰色
            }
        else:
            color_map = {
                'started': '#ADD8E6',       # 浅蓝色
                'completed': '#1E90FF',     # 道奇蓝
                'error': '#FF0000'          # 红色
            }
        return color_map.get(status, '#CCCCCC')
    
    def create_gantt_chart(self) -> go.Figure:
        """创建甘特图"""
        fig = go.Figure()
        
        # 计算时间范围
        all_times = []
        for call in list(self.llm_calls.values()) + list(self.tool_calls.values()):
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
            
            task_name = f"🤖 LLM-{model_short}"
            hover_text = (
                f"<b>LLM调用: {model_short}</b><br>"
                f"ID: {call_id}<br>"
                f"状态: {call['status']}<br>"
                f"开始: {start_dt.strftime('%H:%M:%S.%f')[:-3]}<br>"
                f"结束: {end_dt.strftime('%H:%M:%S.%f')[:-3]}<br>"
                f"耗时: {duration_ms}ms<br>"
                f"Tokens: {tokens}"
            )
            
            if call['error']:
                hover_text += f"<br>错误: {call['error']}"
            
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
            hover_text = (
                f"<b>工具调用: {tool_name}</b><br>"
                f"ID: {call_id}<br>"
                f"状态: {call['status']}<br>"
                f"开始: {start_dt.strftime('%H:%M:%S.%f')[:-3]}<br>"
                f"结束: {end_dt.strftime('%H:%M:%S.%f')[:-3]}<br>"
                f"总耗时: {duration_ms}ms<br>"
                f"执行耗时: {exec_duration_ms}ms"
            )
            
            if call['args']:
                args_str = ', '.join([f"{k}={v}" for k, v in list(call['args'].items())[:3]])
                if len(call['args']) > 3:
                    args_str += '...'
                hover_text += f"<br>参数: {args_str}"
            
            if call['error']:
                hover_text += f"<br>错误: {call['error']}"
            
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
        
        # 按开始时间排序
        gantt_data.sort(key=lambda x: x['Start'])
        
        # 重新分配Y位置
        for i, item in enumerate(gantt_data):
            item['Y'] = i
        
        # 创建甘特图条形
        for item in gantt_data:
            # 计算持续时间（以毫秒为单位）
            duration_ms = (item['Finish'] - item['Start']).total_seconds() * 1000
            
            fig.add_trace(go.Bar(
                x=[duration_ms],
                y=[item['Y']],
                base=[item['Start']],
                orientation='h',
                name=item['Task'],
                marker=dict(color=item['Color']),
                hovertemplate=item['Hover'] + '<extra></extra>',
                showlegend=False
            ))
        
        # 更新布局
        fig.update_layout(
            title={
                'text': '🔍 Gemini CLI 监控数据甘特图',
                'x': 0.5,
                'font': {'size': 20}
            },
            xaxis_title='时间轴',
            yaxis_title='调用事件',
            xaxis=dict(
                type='date',
                tickformat='%H:%M:%S.%L',
                title_font_size=14
            ),
            yaxis=dict(
                tickmode='array',
                tickvals=[item['Y'] for item in gantt_data],
                ticktext=[item['Task'] for item in gantt_data],
                title_font_size=14
            ),
            height=max(600, len(gantt_data) * 40 + 200),
            width=1200,
            template='plotly_white',
            hovermode='closest'
        )
        
        # 添加图例
        legend_items = [
            {'name': '🤖 LLM调用', 'color': '#1E90FF'},
            {'name': '🔧 工具调用', 'color': '#FF6347'},
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
        fig.write_html(output_file, include_plotlyjs='cdn')
        print(f"✅ 甘特图已保存到: {output_file}")
    
    def show_chart(self, fig: go.Figure) -> None:
        """显示甘特图"""
        fig.show()
    
    def print_summary(self) -> None:
        """打印数据摘要"""
        llm_count = len(self.llm_calls)
        tool_count = len(self.tool_calls)
        
        print(f"\n📊 数据摘要:")
        print(f"   LLM调用: {llm_count}次")
        print(f"   工具调用: {tool_count}次")
        print(f"   总事件: {len(self.events)}条")
        
        if llm_count > 0:
            total_llm_duration = sum(call.get('duration', 0) for call in self.llm_calls.values())
            total_tokens = sum(call.get('tokens', 0) for call in self.llm_calls.values())
            print(f"   LLM总耗时: {total_llm_duration}ms")
            print(f"   总Token消耗: {total_tokens}")
        
        if tool_count > 0:
            total_tool_duration = sum(call.get('duration', 0) for call in self.tool_calls.values())
            print(f"   工具总耗时: {total_tool_duration}ms")

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
