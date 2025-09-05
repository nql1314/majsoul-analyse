#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雀魂牌谱数据统计脚本
统计用户的连续一位、连续一二位、连续非4位、连续吃4位、连续不吃1的把数
"""

import requests
import time
import json
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PlayerRecord:
    """玩家记录数据类"""
    account_id: int
    nickname: str
    level: int
    score: int
    grading_score: int
    rank: int  # 排名，1-4位


@dataclass
class GameRecord:
    """游戏记录数据类"""
    record_id: str
    mode_id: int
    uuid: str
    start_time: int
    end_time: int
    players: List[PlayerRecord]


class MajsoulAnalyzer:
    """雀魂牌谱数据分析器"""
    
    def __init__(self, user_id: int, modes: List[int] = [16, 12, 9, 11, 8]):
        self.user_id = user_id
        self.modes = modes
        # 模式注释：16=王座, 12=玉, 9=金, 11=玉东, 8=金东
        self.mode_names = {16: "王座", 12: "玉", 9: "金", 11: "玉东", 8: "金东"}
        self.base_url = "https://5-data.amae-koromo.com/api/v2/pl4/player_records"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 初始化总体统计结果（合并所有模式）
        self.total_stats = {
            'total_games': 0,
            'consecutive_first': 0,      # 连续吃一
            'consecutive_top2': 0,       # 连续一二
            'consecutive_third': 0,      # 连续吃三
            'consecutive_last': 0,       # 连续吃四
            'consecutive_not_first': 0,  # 连续非一
            'consecutive_not_last': 0,   # 连续非四
            'max_consecutive_first': 0,
            'max_consecutive_top2': 0,
            'max_consecutive_third': 0,
            'max_consecutive_last': 0,
            'max_consecutive_not_first': 0,
            'max_consecutive_not_last': 0,
            'rank_history': [],  # 排名历史记录
        }
        
        # 当前连续计数（总体统计）
        self.current_streaks = {
            'first': 0,
            'top2': 0,
            'third': 0,
            'last': 0,
            'not_first': 0,
            'not_last': 0,
        }
    
    def fetch_player_records(self, limit: int = 100, mode: str = "12", 
                           start_time: int = None) -> List[Dict]:
        """获取玩家牌谱记录"""
        if start_time is None:
            start_time = int(time.time() * 1000)  # 当前时间戳（毫秒）
        
        url = f"{self.base_url}/{self.user_id}/{start_time}/0"
        params = {
            'limit': limit,
            'mode': mode,
            'descending': 'true',
            'tag': ''
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return []
    
    def parse_game_record(self, record: Dict) -> GameRecord:
        """解析单条游戏记录"""
        players = []
        for i, player_data in enumerate(record['players']):
            # 根据score排序确定排名
            player = PlayerRecord(
                account_id=player_data['accountId'],
                nickname=player_data['nickname'],
                level=player_data['level'],
                score=player_data['score'],
                grading_score=player_data['gradingScore'],
                rank=0  # 稍后计算
            )
            players.append(player)
        
        # 按score降序排序确定排名
        players.sort(key=lambda x: x.score, reverse=True)
        for i, player in enumerate(players):
            player.rank = i + 1
        
        return GameRecord(
            record_id=record['_id'],
            mode_id=record['modeId'],
            uuid=record['uuid'],
            start_time=record['startTime'],
            end_time=record['endTime'],
            players=players
        )
    
    def get_user_rank(self, game_record: GameRecord) -> int:
        """获取用户在单局游戏中的排名"""
        for player in game_record.players:
            if player.account_id == self.user_id:
                return player.rank
        return 0  # 未找到用户
    
    def update_streaks(self, rank: int):
        """更新连续统计"""
        # 更新连续吃一
        if rank == 1:
            self.current_streaks['first'] += 1
            self.current_streaks['top2'] += 1
            self.current_streaks['third'] = 0
            self.current_streaks['last'] = 0
            self.current_streaks['not_first'] = 0
            self.current_streaks['not_last'] += 1
        elif rank == 2:
            self.current_streaks['first'] = 0
            self.current_streaks['top2'] += 1
            self.current_streaks['third'] = 0
            self.current_streaks['last'] = 0
            self.current_streaks['not_first'] += 1
            self.current_streaks['not_last'] += 1
        elif rank == 3:
            self.current_streaks['first'] = 0
            self.current_streaks['top2'] = 0
            self.current_streaks['third'] += 1
            self.current_streaks['last'] = 0
            self.current_streaks['not_first'] += 1
            self.current_streaks['not_last'] += 1
        elif rank == 4:
            self.current_streaks['first'] = 0
            self.current_streaks['top2'] = 0
            self.current_streaks['third'] = 0
            self.current_streaks['last'] += 1
            self.current_streaks['not_first'] += 1
            self.current_streaks['not_last'] = 0
        
        # 更新最大连续记录
        for key in self.current_streaks:
            if self.current_streaks[key] > self.total_stats[f'max_consecutive_{key.replace("_", "_")}']:
                self.total_stats[f'max_consecutive_{key.replace("_", "_")}'] = self.current_streaks[key]
    
    def analyze_all_records(self):
        """分析所有牌谱记录"""
        print(f"开始分析用户 {self.user_id} 的牌谱数据...")
        print(f"分析模式: {self.modes}")
        
        # 显示模式注释
        mode_info = []
        for mode in self.modes:
            mode_info.append(f"{mode}({self.mode_names.get(mode, '未知')})")
        print(f"模式说明: {', '.join(mode_info)}")
        
        # 将模式列表转换为字符串格式
        mode_string = ",".join(map(str, self.modes))
        print(f"模式参数: {mode_string}")
        
        # 获取所有模式的数据
        print(f"\n正在获取所有模式的数据...")
        all_records = []
        start_time = int(time.time() * 1000)  # 从当前时间开始
        page_count = 0
        
        while True:
            page_count += 1
            print(f"  正在获取第 {page_count} 页数据...")
            print(f"  请求参数: start_time={start_time}")
            
            records = self.fetch_player_records(
                limit=100, 
                mode=mode_string, 
                start_time=start_time
            )
            
            if not records:
                print("  没有更多数据了，停止获取")
                break
            
            all_records.extend(records)
            print(f"  本页获取到 {len(records)} 条记录，累计 {len(all_records)} 条")
            
            # 更新时间范围，获取更早的数据
            # 使用本页最后一条记录的时间作为下次查询的start_time
            last_record_time = records[-1]['startTime'] * 1000 - 1  # 转换为毫秒
            start_time = last_record_time
            
            # 避免请求过于频繁
            time.sleep(0.5)
        
        print(f"  总共获取到 {len(all_records)} 条记录")
        
        # 按时间顺序排序（从早到晚）
        all_records.sort(key=lambda x: x['startTime'])
        
        # 分析所有记录（合并所有模式）
        print(f"\n正在分析所有记录...")
        for record_data in all_records:
            try:
                game_record = self.parse_game_record(record_data)
                user_rank = self.get_user_rank(game_record)
                
                if user_rank == 0:
                    continue
                
                self.total_stats['total_games'] += 1
                self.update_streaks(user_rank)
                
                # 记录排名历史（从当前时间往前）
                self.total_stats['rank_history'].append({
                    'rank': user_rank,
                    'mode': record_data.get('modeId', 0),
                    'mode_name': self.mode_names.get(record_data.get('modeId', 0), '未知'),
                    'timestamp': record_data['startTime'],
                    'datetime': datetime.fromtimestamp(record_data['startTime']).strftime('%Y-%m-%d %H:%M:%S')
                })
                
                # 每50局输出一次进度
                if self.total_stats['total_games'] % 50 == 0:
                    print(f"  已分析 {self.total_stats['total_games']} 局游戏...")
                    
            except Exception as e:
                print(f"  解析记录时出错: {e}")
                continue
    
    def print_statistics(self):
        """打印统计结果"""
        print("\n" + "="*80)
        print(f"用户 {self.user_id} 的牌谱统计结果")
        print("="*80)
        
        # 显示模式信息
        mode_info = []
        for mode in self.modes:
            mode_info.append(f"{mode}({self.mode_names.get(mode, '未知')})")
        print(f"分析模式: {', '.join(mode_info)}")
        print(f"总游戏局数: {self.total_stats['total_games']}")
        print()
        
        # 打印当前连续统计
        print("当前连续统计:")
        print(f"  连续吃一: {self.current_streaks['first']} 局")
        print(f"  连续一二: {self.current_streaks['top2']} 局")
        print(f"  连续吃三: {self.current_streaks['third']} 局")
        print(f"  连续吃四: {self.current_streaks['last']} 局")
        print(f"  连续非一: {self.current_streaks['not_first']} 局")
        print(f"  连续非四: {self.current_streaks['not_last']} 局")
        print()
        
        # 打印历史最大连续记录
        print("历史最大连续记录:")
        print(f"  最大连续吃一: {self.total_stats['max_consecutive_first']} 局")
        print(f"  最大连续一二: {self.total_stats['max_consecutive_top2']} 局")
        print(f"  最大连续吃三: {self.total_stats['max_consecutive_third']} 局")
        print(f"  最大连续吃四: {self.total_stats['max_consecutive_last']} 局")
        print(f"  最大连续非一: {self.total_stats['max_consecutive_not_first']} 局")
        print(f"  最大连续非四: {self.total_stats['max_consecutive_not_last']} 局")
        print("="*80)
 
        # 显示最近20局的排名
        recent_ranks = self.total_stats['rank_history'][-20:] if len(self.total_stats['rank_history']) > 20 else self.total_stats['rank_history']
        
        print("最近排名记录:")
        for i, record in enumerate(reversed(recent_ranks)):  # 从最新到最旧
            print(f"  {i+1:2d}. {record['datetime']} - 第{record['rank']}位 ({record['mode_name']})")
        
        # 显示排名数组（纯数字）
        rank_array = [record['rank'] for record in reversed(self.total_stats['rank_history'])]
        
        # 显示排名统计
        rank_counts = {}
        for rank in rank_array:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        print(f"\n排名分布:")
        for rank in sorted(rank_counts.keys()):
            count = rank_counts[rank]
            percentage = (count / len(rank_array)) * 100
            print(f"  第{rank}位: {count}局 ({percentage:.1f}%)")
        
        # 显示各模式游戏数量
        mode_counts = {}
        for record in self.total_stats['rank_history']:
            mode = record['mode']
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        print(f"\n各模式游戏数量:")
        for mode in sorted(mode_counts.keys()):
            mode_name = self.mode_names.get(mode, '未知')
            count = mode_counts[mode]
            percentage = (count / len(rank_array)) * 100
            print(f"  {mode}({mode_name}): {count}局 ({percentage:.1f}%)")
        
        print("="*80)
           
        # 打印排名历史数组
        print("\n排名历史记录 (从当前时间往前):")
        print("="*80)
        
        print(f"\n排名数组 (共{len(rank_array)}局):")
        print(f"  {rank_array}")

    def save_to_file(self, filename: str = None):
        """保存统计结果到文件"""
        if filename is None:
            filename = f"majsoul_stats_{self.user_id}_{int(time.time())}.json"
        
        data = {
            'user_id': self.user_id,
            'modes': self.modes,
            'mode_names': self.mode_names,
            'analysis_time': datetime.now().isoformat(),
            'total_statistics': self.total_stats,
            'current_streaks': self.current_streaks
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"统计结果已保存到: {filename}")
    
    def save_to_txt(self, filename: str = None):
        """保存统计结果到txt文件"""
        if filename is None:
            filename = f"majsoul_stats_{self.user_id}_{int(time.time())}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            # 写入统计结果
            f.write("="*80 + "\n")
            f.write(f"用户 {self.user_id} 的牌谱统计结果\n")
            f.write("="*80 + "\n")
            
            # 显示模式信息
            mode_info = []
            for mode in self.modes:
                mode_info.append(f"{mode}({self.mode_names.get(mode, '未知')})")
            f.write(f"分析模式: {', '.join(mode_info)}\n")
            f.write(f"总游戏局数: {self.total_stats['total_games']}\n")
            f.write("\n")
            
            # 写入当前连续统计
            f.write("当前连续统计:\n")
            f.write(f"  连续吃一: {self.current_streaks['first']} 局\n")
            f.write(f"  连续一二: {self.current_streaks['top2']} 局\n")
            f.write(f"  连续吃三: {self.current_streaks['third']} 局\n")
            f.write(f"  连续吃四: {self.current_streaks['last']} 局\n")
            f.write(f"  连续非一: {self.current_streaks['not_first']} 局\n")
            f.write(f"  连续非四: {self.current_streaks['not_last']} 局\n")
            f.write("\n")
            
            # 写入历史最大连续记录
            f.write("历史最大连续记录:\n")
            f.write(f"  最大连续吃一: {self.total_stats['max_consecutive_first']} 局\n")
            f.write(f"  最大连续一二: {self.total_stats['max_consecutive_top2']} 局\n")
            f.write(f"  最大连续吃三: {self.total_stats['max_consecutive_third']} 局\n")
            f.write(f"  最大连续吃四: {self.total_stats['max_consecutive_last']} 局\n")
            f.write(f"  最大连续非一: {self.total_stats['max_consecutive_not_first']} 局\n")
            f.write(f"  最大连续非四: {self.total_stats['max_consecutive_not_last']} 局\n")
            f.write("="*80 + "\n")
            
            # 写入排名历史记录
            f.write("\n排名历史记录 (从当前时间往前):\n")
            f.write("="*80 + "\n")
            
            # 写入最近20局的排名
            recent_ranks = self.total_stats['rank_history'][-20:] if len(self.total_stats['rank_history']) > 20 else self.total_stats['rank_history']
            
            f.write("最近排名记录:\n")
            for i, record in enumerate(reversed(recent_ranks)):  # 从最新到最旧
                f.write(f"  {i+1:2d}. {record['datetime']} - 第{record['rank']}位 ({record['mode_name']})\n")
            
            rank_array = [record['rank'] for record in reversed(self.total_stats['rank_history'])]

            # 写入排名统计
            rank_counts = {}
            for rank in rank_array:
                rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
            f.write(f"\n排名分布:\n")
            for rank in sorted(rank_counts.keys()):
                count = rank_counts[rank]
                percentage = (count / len(rank_array)) * 100
                f.write(f"  第{rank}位: {count}局 ({percentage:.1f}%)\n")
            
            # 写入各模式游戏数量
            mode_counts = {}
            for record in self.total_stats['rank_history']:
                mode = record['mode']
                mode_counts[mode] = mode_counts.get(mode, 0) + 1
            
            f.write(f"\n各模式游戏数量:\n")
            for mode in sorted(mode_counts.keys()):
                mode_name = self.mode_names.get(mode, '未知')
                count = mode_counts[mode]
                percentage = (count / len(rank_array)) * 100
                f.write(f"  {mode}({mode_name}): {count}局 ({percentage:.1f}%)\n")
            
            f.write("="*80 + "\n")
            # 写入排名数组（纯数字）
            f.write(f"\n排名数组 (共{len(rank_array)}局):\n")
            f.write(f"  {rank_array}\n")
        print(f"统计结果已保存到: {filename}")


def main():
    """主函数"""
    print("雀魂牌谱数据统计工具")
    print("="*30)
    
    try:
        user_id = int(input("请输入雀魂牌谱屋用户ID，位于牌谱屋页面https://amae-koromo.sapk.ch/player/后面的数字: "))
        
        # 支持自定义模式
        custom_modes = input("请输入要分析的模式 (用逗号分隔，默认16,12,9,11,8 对应王座,玉,金,玉东,金东): ").strip()
        if custom_modes:
            modes = [int(m.strip()) for m in custom_modes.split(',')]
        else:
            modes = [16, 12, 9, 11, 8]
        
        analyzer = MajsoulAnalyzer(user_id, modes)
        analyzer.analyze_all_records()
        analyzer.print_statistics()
        
        save_choice = input("\n是否保存结果到文件? (y/n): ").lower()
        if save_choice == 'y':
            print("\n请选择保存格式:")
            print("1. JSON格式 (结构化数据)")
            print("2. TXT格式 (可读文本)")
            print("3. 两种格式都保存")
            
            format_choice = input("请输入选择 (1/2/3): ").strip()
            
            if format_choice == '1':
                analyzer.save_to_file()
            elif format_choice == '2':
                analyzer.save_to_txt()
            elif format_choice == '3':
                analyzer.save_to_file()
                analyzer.save_to_txt()
            else:
                print("无效选择，默认保存为JSON格式")
                analyzer.save_to_file()
            
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n程序运行出错: {e}")


if __name__ == "__main__":
    main()
