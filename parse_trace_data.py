#!/usr/bin/env python3
"""
解析trace文件中的data内容，转换为标准JSON格式
"""

import json
import argparse
from typing import Dict, Any, List
from pathlib import Path

class TraceDataParser:
    def __init__(self, trace_file: str):
        self.trace_file = trace_file
        self.parsed_data = []
    
    def parse_trace_file(self) -> List[Dict[str, Any]]:
        """解析trace文件，提取data内容"""
        print(f"📖 正在解析文件: {self.trace_file}")
        
        try:
            with open(self.trace_file, 'r', encoding='utf-8') as f:
                line_count = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        # 解析JSONL行
                        event = json.loads(line)
                        line_count += 1
                        
                        # 提取data字段
                        if 'data' in event:
                            data_entry = {
                                'line_number': line_count,
                                'timestamp': event.get('timestamp', ''),
                                'type': event.get('type', ''),
                                'event': event.get('event', ''),
                                'data': event['data']
                            }
                            
                            # 尝试解析data中的JSON字符串字段
                            data_entry['data'] = self._parse_nested_json(event['data'])
                            
                            self.parsed_data.append(data_entry)
                        
                    except json.JSONDecodeError as e:
                        print(f"⚠️  第{line_count}行JSON解析错误: {e}")
                        continue
                        
            print(f"✅ 成功解析 {len(self.parsed_data)} 条记录")
            return self.parsed_data
            
        except FileNotFoundError:
            print(f"❌ 文件不存在: {self.trace_file}")
            return []
        except Exception as e:
            print(f"❌ 解析文件时出错: {e}")
            return []
    
    def _parse_nested_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """递归解析data中的JSON字符串字段"""
        parsed_data = {}
        
        for key, value in data.items():
            if isinstance(value, str) and self._is_json_string(value):
                try:
                    # 尝试解析JSON字符串
                    parsed_value = json.loads(value)
                    parsed_data[key] = {
                        'raw': value,
                        'parsed': parsed_value,
                        'type': 'json_string'
                    }
                except json.JSONDecodeError:
                    # 如果解析失败，保持原值
                    parsed_data[key] = value
            else:
                parsed_data[key] = value
                
        return parsed_data
    
    def _is_json_string(self, text: str) -> bool:
        """判断字符串是否可能是JSON"""
        text = text.strip()
        return (text.startswith('{') and text.endswith('}')) or \
               (text.startswith('[') and text.endswith(']'))
    
    def save_to_json(self, output_file: str, indent: int = 2) -> None:
        """保存解析结果为JSON文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.parsed_data, f, indent=indent, ensure_ascii=False)
            print(f"💾 数据已保存到: {output_file}")
        except Exception as e:
            print(f"❌ 保存文件时出错: {e}")
    
    def save_data_only(self, output_file: str, indent: int = 2) -> None:
        """只保存data字段的内容"""
        try:
            data_only = [entry['data'] for entry in self.parsed_data]
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data_only, f, indent=indent, ensure_ascii=False)
            print(f"💾 Data内容已保存到: {output_file}")
        except Exception as e:
            print(f"❌ 保存文件时出错: {e}")
    
    def extract_specific_fields(self, output_file: str, fields: List[str]) -> None:
        """提取特定字段并保存"""
        try:
            extracted_data = []
            for entry in self.parsed_data:
                extracted_entry = {}
                for field in fields:
                    if field in entry:
                        extracted_entry[field] = entry[field]
                    elif field in entry.get('data', {}):
                        extracted_entry[field] = entry['data'][field]
                
                if extracted_entry:  # 只添加非空条目
                    extracted_data.append(extracted_entry)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            print(f"💾 提取的字段已保存到: {output_file}")
        except Exception as e:
            print(f"❌ 提取字段时出错: {e}")
    
    def print_summary(self) -> None:
        """打印解析摘要"""
        if not self.parsed_data:
            print("📊 没有解析到任何数据")
            return
        
        print(f"\n📊 解析摘要:")
        print(f"   总记录数: {len(self.parsed_data)}")
        
        # 统计事件类型
        event_types = {}
        for entry in self.parsed_data:
            event_type = f"{entry['type']}.{entry['event']}"
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        print(f"   事件类型分布:")
        for event_type, count in sorted(event_types.items()):
            print(f"     {event_type}: {count}")
        
        # 显示数据字段
        print(f"\n   常见data字段:")
        all_keys = set()
        for entry in self.parsed_data:
            all_keys.update(entry['data'].keys())
        
        for key in sorted(all_keys):
            count = sum(1 for entry in self.parsed_data if key in entry['data'])
            print(f"     {key}: 出现在 {count} 条记录中")

def main():
    parser = argparse.ArgumentParser(description='解析trace文件中的data内容')
    parser.add_argument('trace_file', nargs='?', default='test_trace_1.jsonl',
                       help='trace文件路径 (默认: test_trace_1.jsonl)')
    parser.add_argument('-o', '--output', default='parsed_trace_data.json',
                       help='输出JSON文件名 (默认: parsed_trace_data.json)')
    parser.add_argument('--data-only', action='store_true',
                       help='只输出data字段内容')
    parser.add_argument('--fields', nargs='+',
                       help='提取特定字段 (例如: --fields id model status)')
    parser.add_argument('--indent', type=int, default=2,
                       help='JSON缩进空格数 (默认: 2)')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not Path(args.trace_file).exists():
        print(f"❌ 文件不存在: {args.trace_file}")
        return
    
    # 创建解析器
    parser = TraceDataParser(args.trace_file)
    
    # 解析文件
    data = parser.parse_trace_file()
    if not data:
        print("❌ 没有解析到任何数据")
        return
    
    # 打印摘要
    parser.print_summary()
    
    # 保存结果
    if args.fields:
        parser.extract_specific_fields(args.output, args.fields)
    elif args.data_only:
        parser.save_data_only(args.output, args.indent)
    else:
        parser.save_to_json(args.output, args.indent)
    
    print(f"\n🎉 解析完成！")

if __name__ == "__main__":
    main()
