"""
Praxis 哨兵历史追踪器
记录每日哨兵状态，用于 Rule 3 条件单退场天数计算

用法：
  from praxis_sdk.core.sentinel_tracker import SentinelTracker
  
  tracker = SentinelTracker()
  tracker.record(bullish_count=2, total=8)
  days = tracker.get_consecutive_low_days()
"""

import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict


class SentinelTracker:
    """哨兵历史追踪器"""
    
    def __init__(self, history_file: str = "outputs/logs/sentinel_history.jsonl"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
    
    def record(self, bullish_count: int, total: int):
        """
        记录当日哨兵状态。
        
        Args:
            bullish_count: 多头哨兵数
            total: 总哨兵数
        """
        entry = {
            "date": date.today().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "bullish_count": bullish_count,
            "total": total,
            "state": "绝对防守期" if bullish_count <= 2 else "适度试探期" if bullish_count <= 4 else "积极进攻期"
        }
        
        # 追加到 JSONL 文件
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def get_history(self, days: int = 7) -> List[Dict]:
        """
        获取最近 N 天的哨兵历史。
        
        Args:
            days: 天数
        
        Returns:
            历史记录列表
        """
        if not self.history_file.exists():
            return []
        
        records = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        
        # 按日期排序，返回最近 N 天
        records.sort(key=lambda x: x.get("date", ""), reverse=True)
        return records[:days]
    
    def get_consecutive_low_days(self, threshold: int = 2) -> int:
        """
        获取连续低哨兵天数（哨兵数 <= threshold）。
        
        Args:
            threshold: 哨兵阈值（默认 2）
        
        Returns:
            连续天数
        """
        history = self.get_history(days=30)
        
        if not history:
            return 0
        
        consecutive = 0
        for record in history:
            if record.get("bullish_count", 8) <= threshold:
                consecutive += 1
            else:
                break
        
        return consecutive
    
    def get_rule3_status(self) -> Dict:
        """
        获取 Rule 3 状态。
        
        Returns:
            {
                "consecutive_days": int,
                "triggered": bool,
                "action": str,
                "status_lock": bool
            }
        """
        consecutive = self.get_consecutive_low_days(threshold=2)
        
        # Rule 3 触发条件
        if consecutive >= 2:
            action = "取消存量条件单"
            triggered = True
            status_lock = True
        elif consecutive == 1:
            action = "暂停新建条件单"
            triggered = True
            status_lock = False
        else:
            action = "条件单正常"
            triggered = False
            status_lock = False
        
        return {
            "consecutive_days": consecutive,
            "triggered": triggered,
            "action": action,
            "status_lock": status_lock
        }
    
    def should_record_today(self) -> bool:
        """
        检查今天是否已记录。
        
        Returns:
            True 如果今天未记录
        """
        history = self.get_history(days=1)
        
        if not history:
            return True
        
        today = date.today().isoformat()
        return history[0].get("date") != today


# 全局实例
_global_tracker = SentinelTracker()


def get_sentinel_tracker() -> SentinelTracker:
    """获取全局哨兵追踪器实例"""
    return _global_tracker
