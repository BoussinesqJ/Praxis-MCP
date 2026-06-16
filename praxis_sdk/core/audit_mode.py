"""
Praxis 审计模式管理器
防止 Agent 在非审计场景下输出模拟数据

用法：
  from praxis_sdk.core.audit_mode import AuditMode, get_audit_mode
  
  mode = get_audit_mode()
  mode.set_mode("live")  # 实盘模式
  mode.set_mode("simulation")  # 模拟模式
  
  # 检查是否需要水印
  if mode.needs_watermark():
      print(mode.get_watermark())
"""

from enum import Enum
from typing import Optional
from datetime import datetime


class ModeType(Enum):
    """审计模式类型"""
    LIVE = "live"  # 实盘模式（真实数据）
    SIMULATION = "simulation"  # 模拟模式（模拟数据）
    REVIEW = "review"  # 复盘模式（历史数据，已确认）


class AuditMode:
    """审计模式管理器"""
    
    def __init__(self):
        self._mode = ModeType.LIVE  # 默认实盘模式
        self._authorized = False  # 是否经用户授权
        self._reason: Optional[str] = None  # 模拟原因
        self._set_at: Optional[datetime] = None
    
    @property
    def mode(self) -> ModeType:
        """当前模式"""
        return self._mode
    
    @property
    def is_live(self) -> bool:
        """是否为实盘模式"""
        return self._mode == ModeType.LIVE
    
    @property
    def is_simulation(self) -> bool:
        """是否为模拟模式"""
        return self._mode == ModeType.SIMULATION
    
    @property
    def is_review(self) -> bool:
        """是否为复盘模式"""
        return self._mode == ModeType.REVIEW
    
    def set_mode(self, mode: str, reason: str = None, authorized: bool = False):
        """
        设置审计模式。
        
        Args:
            mode: "live" | "simulation" | "review"
            reason: 模拟原因（simulation 模式必填）
            authorized: 是否经用户授权
        """
        try:
            self._mode = ModeType(mode)
        except ValueError:
            raise ValueError(f"无效的模式: {mode}，可选: live/simulation/review")
        
        self._authorized = authorized
        self._reason = reason
        self._set_at = datetime.now()
        
        # simulation 模式必须有原因
        if self._mode == ModeType.SIMULATION and not reason:
            raise ValueError("simulation 模式必须提供 reason")
    
    def set_live(self):
        """设置为实盘模式"""
        self._mode = ModeType.LIVE
        self._authorized = True
        self._reason = None
        self._set_at = datetime.now()
    
    def set_simulation(self, reason: str, authorized: bool = False):
        """
        设置为模拟模式。
        
        Args:
            reason: 模拟原因
            authorized: 是否经用户授权
        """
        self._mode = ModeType.SIMULATION
        self._authorized = authorized
        self._reason = reason
        self._set_at = datetime.now()
    
    def set_review(self, authorized: bool = True):
        """
        设置为复盘模式。
        
        Args:
            authorized: 是否经用户授权（复盘默认已授权）
        """
        self._mode = ModeType.REVIEW
        self._authorized = authorized
        self._reason = "历史数据复盘"
        self._set_at = datetime.now()
    
    def needs_watermark(self) -> bool:
        """
        检查是否需要水印。
        
        Returns:
            True 如果需要在输出中添加水印
        """
        # 实盘模式不需要水印
        if self._mode == ModeType.LIVE:
            return False
        
        # 复盘模式已授权，不需要水印
        if self._mode == ModeType.REVIEW and self._authorized:
            return False
        
        # 模拟模式未授权，需要水印
        if self._mode == ModeType.SIMULATION and not self._authorized:
            return True
        
        # 其他情况需要水印
        return True
    
    def get_watermark(self) -> str:
        """
        获取水印文本。
        
        Returns:
            水印字符串
        """
        if not self.needs_watermark():
            return ""
        
        if self._mode == ModeType.SIMULATION:
            auth_status = "已授权" if self._authorized else "未授权"
            return f"⚠️ UNVERIFIED SIMULATION — {auth_status} | 原因: {self._reason or '未说明'}"
        
        if self._mode == ModeType.REVIEW:
            return f"📋 REVIEW MODE — 历史数据复盘 | {self._reason or ''}"
        
        return "⚠️ UNKNOWN MODE"
    
    def get_watermark_prefix(self) -> str:
        """
        获取水印前缀（用于输出开头）。
        
        Returns:
            水印前缀字符串
        """
        if not self.needs_watermark():
            return ""
        
        return f"""
---
{self.get_watermark()}
---

"""
    
    def get_watermark_suffix(self) -> str:
        """
        获取水印后缀（用于输出结尾）。
        
        Returns:
            水印后缀字符串
        """
        if not self.needs_watermark():
            return ""
        
        return f"""

---
{self.get_watermark()}
---
"""
    
    def validate_output(self, output: str) -> str:
        """
        验证并添加水印到输出。
        
        Args:
            output: 原始输出
        
        Returns:
            添加水印后的输出
        """
        if not self.needs_watermark():
            return output
        
        # 检查输出是否已有水印
        if "UNVERIFIED SIMULATION" in output:
            return output
        
        # 添加水印
        return self.get_watermark_prefix() + output + self.get_watermark_suffix()
    
    def get_status(self) -> dict:
        """
        获取当前状态。
        
        Returns:
            {
                "mode": str,
                "is_live": bool,
                "is_simulation": bool,
                "is_review": bool,
                "needs_watermark": bool,
                "authorized": bool,
                "reason": str,
                "set_at": str
            }
        """
        return {
            "mode": self._mode.value,
            "is_live": self.is_live,
            "is_simulation": self.is_simulation,
            "is_review": self.is_review,
            "needs_watermark": self.needs_watermark(),
            "authorized": self._authorized,
            "reason": self._reason,
            "set_at": self._set_at.isoformat() if self._set_at else None
        }


# 全局实例
_global_audit_mode = AuditMode()


def get_audit_mode() -> AuditMode:
    """获取全局审计模式实例"""
    return _global_audit_mode


def is_live_mode() -> bool:
    """检查是否为实盘模式"""
    return _global_audit_mode.is_live


def needs_watermark() -> bool:
    """检查是否需要水印"""
    return _global_audit_mode.needs_watermark()


def validate_output(output: str) -> str:
    """验证并添加水印到输出"""
    return _global_audit_mode.validate_output(output)
