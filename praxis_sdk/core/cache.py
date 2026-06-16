"""
Praxis MCP 工具响应缓存
避免重复调用 MCP 工具，减少网络延迟

用法：
  from praxis_sdk.core.cache import MCPCache
  
  cache = MCPCache(ttl_seconds=60)
  
  # 获取缓存或执行工具调用
  result = cache.get_or_execute("sentinel_tool", lambda: sentinel_tool(action="scan"))
"""

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional
from datetime import datetime


class MCPCache:
    """MCP 工具响应缓存"""
    
    def __init__(self, cache_dir: str = "outputs/logs", ttl_seconds: int = 60):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "mcp_cache.json"
        self.ttl_seconds = ttl_seconds
        self._memory_cache = {}
    
    def get(self, tool_name: str, params: dict = None) -> Optional[Any]:
        """
        从缓存获取工具响应。
        
        Returns:
            缓存的响应，或 None（缓存未命中/已过期）
        """
        cache_key = self._make_key(tool_name, params)
        
        # 先检查内存缓存
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if time.time() - entry["timestamp"] < self.ttl_seconds:
                return entry["data"]
        
        # 再检查文件缓存
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    file_cache = json.load(f)
                
                if cache_key in file_cache:
                    entry = file_cache[cache_key]
                    if time.time() - entry["timestamp"] < self.ttl_seconds:
                        # 写入内存缓存
                        self._memory_cache[cache_key] = entry
                        return entry["data"]
            except (json.JSONDecodeError, KeyError):
                pass
        
        return None
    
    def set(self, tool_name: str, data: Any, params: dict = None):
        """
        将工具响应写入缓存。
        """
        cache_key = self._make_key(tool_name, params)
        entry = {
            "timestamp": time.time(),
            "data": data,
            "tool": tool_name,
            "params": params,
            "cached_at": datetime.now().isoformat()
        }
        
        # 写入内存缓存
        self._memory_cache[cache_key] = entry
        
        # 写入文件缓存
        file_cache = {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    file_cache = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass
        
        file_cache[cache_key] = entry
        
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(file_cache, f, ensure_ascii=False, indent=2)
    
    def get_or_execute(self, tool_name: str, execute_fn: Callable, params: dict = None,
                       force_refresh: bool = False) -> Any:
        """
        获取缓存或执行工具调用。
        
        Args:
            tool_name: 工具名称
            execute_fn: 工具执行函数
            params: 工具参数
            force_refresh: 强制刷新缓存
        
        Returns:
            工具响应
        """
        if not force_refresh:
            cached = self.get(tool_name, params)
            if cached is not None:
                return cached
        
        # 执行工具调用
        result = execute_fn()
        
        # 写入缓存
        self.set(tool_name, result, params)
        
        return result
    
    def invalidate(self, tool_name: str = None):
        """
        清除缓存。
        
        Args:
            tool_name: 指定工具名称，或 None 清除所有
        """
        if tool_name is None:
            self._memory_cache.clear()
            if self.cache_file.exists():
                self.cache_file.unlink()
        else:
            keys_to_remove = [k for k in self._memory_cache if k.startswith(tool_name)]
            for key in keys_to_remove:
                del self._memory_cache[key]
            
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        file_cache = json.load(f)
                    
                    keys_to_remove = [k for k in file_cache if k.startswith(tool_name)]
                    for key in keys_to_remove:
                        del file_cache[key]
                    
                    with open(self.cache_file, "w", encoding="utf-8") as f:
                        json.dump(file_cache, f, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, KeyError):
                    pass
    
    def _make_key(self, tool_name: str, params: dict = None) -> str:
        """生成缓存键"""
        if params:
            param_str = json.dumps(params, sort_keys=True)
            return f"{tool_name}:{param_str}"
        return tool_name


# 全局缓存实例
_global_cache = MCPCache(ttl_seconds=60)


def get_cache() -> MCPCache:
    """获取全局缓存实例"""
    return _global_cache


def cached_tool_call(tool_name: str, execute_fn: Callable, params: dict = None,
                     force_refresh: bool = False) -> Any:
    """
    便捷函数：带缓存的工具调用。
    
    Example:
        result = cached_tool_call(
            "sentinel_tool",
            lambda: sentinel_tool(action="scan"),
            {"action": "scan"}
        )
    """
    return _global_cache.get_or_execute(tool_name, execute_fn, params, force_refresh)
