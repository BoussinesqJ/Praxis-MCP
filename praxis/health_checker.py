"""
启动健康检查器

在 Praxis 启动时检测所有数据源的可用性，永久跳过不可用的数据源。
避免每次请求都浪费时间等待超时。
"""

import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class DataSourceHealth:
    """数据源健康状态"""
    name: str
    available: bool = True
    last_check: float = 0.0
    check_duration: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None
    
    def mark_healthy(self, duration: float):
        """标记为健康"""
        self.available = True
        self.last_check = time.time()
        self.check_duration = duration
        self.error_count = 0
        self.last_error = None
    
    def mark_unhealthy(self, error: str):
        """标记为不健康"""
        self.available = False
        self.last_check = time.time()
        self.error_count += 1
        self.last_error = error


class HealthChecker:
    """数据源健康检查器"""
    
    def __init__(self):
        self._health_status: Dict[str, DataSourceHealth] = {}
        self._initialized = False
    
    async def initialize(self):
        """启动时初始化，检测所有数据源"""
        if self._initialized:
            return
        
        print("[HealthChecker] 🔍 启动数据源健康检查...")
        
        # 检测 mootdx
        await self._check_mootdx()
        
        # 检测 tencent
        await self._check_tencent()
        
        # 检测 akshare
        await self._check_akshare()
        
        self._initialized = True
        self._print_summary()
    
    async def _check_mootdx(self):
        """检测 mootdx 可用性"""
        name = "mootdx"
        self._health_status[name] = DataSourceHealth(name=name)
        
        start = time.time()
        try:
            from mootdx.quotes import Quotes
            client = Quotes.factory(market='std', timeout=5)
            # 尝试获取一个简单行情
            result = client.quotes(symbol=['000001'])
            
            if result is not None and len(result) > 0:
                duration = time.time() - start
                self._health_status[name].mark_healthy(duration)
                print(f"[HealthChecker] ✅ mootdx 可用 ({duration:.2f}s)")
            else:
                self._health_status[name].mark_unhealthy("返回空数据")
                print(f"[HealthChecker] ❌ mootdx 返回空数据")
        except ImportError:
            self._health_status[name].mark_unhealthy("未安装")
            print(f"[HealthChecker] ❌ mootdx 未安装")
        except Exception as e:
            self._health_status[name].mark_unhealthy(str(e))
            print(f"[HealthChecker] ❌ mootdx 不可用: {e}")
    
    async def _check_tencent(self):
        """检测 tencent 直连可用性"""
        name = "tencent"
        self._health_status[name] = DataSourceHealth(name=name)
        
        start = time.time()
        try:
            import httpx
            
            url = "https://qt.gtimg.cn/q=sz000001"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200 and "v_sz000001" in response.text:
                    duration = time.time() - start
                    self._health_status[name].mark_healthy(duration)
                    print(f"[HealthChecker] ✅ tencent 可用 ({duration:.2f}s)")
                else:
                    self._health_status[name].mark_unhealthy("响应异常")
                    print(f"[HealthChecker] ❌ tencent 响应异常")
        except Exception as e:
            self._health_status[name].mark_unhealthy(str(e))
            print(f"[HealthChecker] ❌ tencent 不可用: {e}")
    
    async def _check_akshare(self):
        """检测 akshare 可用性"""
        name = "akshare"
        self._health_status[name] = DataSourceHealth(name=name)
        
        start = time.time()
        try:
            import akshare as ak
            
            # 尝试获取一个简单行情
            df = ak.stock_zh_a_spot_em()
            
            if df is not None and len(df) > 0:
                duration = time.time() - start
                self._health_status[name].mark_healthy(duration)
                print(f"[HealthChecker] ✅ akshare 可用 ({duration:.2f}s)")
            else:
                self._health_status[name].mark_unhealthy("返回空数据")
                print(f"[HealthChecker] ❌ akshare 返回空数据")
        except ImportError:
            self._health_status[name].mark_unhealthy("未安装")
            print(f"[HealthChecker] ❌ akshare 未安装")
        except Exception as e:
            self._health_status[name].mark_unhealthy(str(e))
            print(f"[HealthChecker] ❌ akshare 不可用: {e}")
    
    def _print_summary(self):
        """打印健康检查摘要"""
        print("\n" + "=" * 60)
        print("[HealthChecker] 📊 数据源健康检查摘要")
        print("=" * 60)
        
        for name, health in self._health_status.items():
            status = "✅ 可用" if health.available else "❌ 不可用"
            duration = f"{health.check_duration:.2f}s" if health.available else "N/A"
            error = f" | 错误: {health.last_error}" if health.last_error else ""
            print(f"  {name:12} | {status} | 耗时: {duration}{error}")
        
        print("=" * 60)
        
        # 计算可用数据源
        available = [name for name, h in self._health_status.items() if h.available]
        unavailable = [name for name, h in self._health_status.items() if not h.available]
        
        print(f"  可用数据源: {', '.join(available) if available else '无'}")
        print(f"  不可用数据源: {', '.join(unavailable) if unavailable else '无'}")
        print("=" * 60 + "\n")
    
    def is_available(self, name: str) -> bool:
        """检查数据源是否可用"""
        if name not in self._health_status:
            return False
        return self._health_status[name].available
    
    def get_available_sources(self) -> List[str]:
        """获取所有可用数据源"""
        return [name for name, h in self._health_status.items() if h.available]
    
    def get_unavailable_sources(self) -> List[str]:
        """获取所有不可用数据源"""
        return [name for name, h in self._health_status.items() if not h.available]
    
    def get_health_status(self) -> Dict[str, Dict]:
        """获取所有数据源健康状态"""
        return {
            name: {
                "available": h.available,
                "last_check": h.last_check,
                "check_duration": h.check_duration,
                "error_count": h.error_count,
                "last_error": h.last_error,
            }
            for name, h in self._health_status.items()
        }


# 全局健康检查器实例
health_checker = HealthChecker()


async def initialize_health_checker():
    """初始化健康检查器（启动时调用）"""
    await health_checker.initialize()


def get_health_checker() -> HealthChecker:
    """获取健康检查器实例"""
    return health_checker
