"""
Praxis v3.0 配置模块

集中管理环境变量和系统配置，支持：
- 数据供应商可插拔（PRAXIS_DATA_VENDOR）
- 断点续传开关（PRAXIS_CHECKPOINT_ENABLED）
- 模型分级路由（PRAXIS_DEEP_MODEL / PRAXIS_QUICK_MODEL）
"""

import os
from typing import Optional


# ─── 数据供应商配置 ───────────────────────────────────────────

# 支持的数据供应商
VALID_VENDORS = {"akshare", "eastmoney", "yfinance"}

# 当前数据供应商（环境变量覆盖，默认 akshare）
DATA_VENDOR: str = os.environ.get("PRAXIS_DATA_VENDOR", "akshare")

# 供应商优先级（三层降级）
DATA_VENDOR_FALLBACK: list = ["akshare", "eastmoney", "yfinance"]


def get_data_vendor() -> str:
    """获取当前数据供应商。"""
    vendor = os.environ.get("PRAXIS_DATA_VENDOR", "akshare").lower()
    if vendor not in VALID_VENDORS:
        import warnings
        warnings.warn(
            f"Unknown PRAXIS_DATA_VENDOR='{vendor}', falling back to 'akshare'"
        )
        return "akshare"
    return vendor


def get_vendor_fallback_chain() -> list:
    """获取供应商降级链（从当前供应商开始）。"""
    vendor = get_data_vendor()
    # 把当前供应商放到降级链的最前面
    chain = [vendor]
    for v in DATA_VENDOR_FALLBACK:
        if v not in chain:
            chain.append(v)
    return chain


# ─── 断点续传配置 ───────────────────────────────────────────

CHECKPOINT_ENABLED: bool = os.environ.get(
    "PRAXIS_CHECKPOINT_ENABLED", "true"
).lower() in ("true", "1", "yes")

CHECKPOINT_DIR: str = os.environ.get(
    "PRAXIS_CHECKPOINT_DIR",
    os.path.join(os.path.dirname(__file__), "..", "outputs", "checkpoints"),
)


# ─── 模型分级路由配置 ───────────────────────────────────────

# 深度思考模型（用于复杂推理：LCD仲裁、Dominic裁决、风险判定）
DEEP_MODEL: Optional[str] = os.environ.get("PRAXIS_DEEP_MODEL")

# 快速思考模型（用于数据提取、格式转换、常规汇总）
QUICK_MODEL: Optional[str] = os.environ.get("PRAXIS_QUICK_MODEL")


# ─── 系统路径配置 ───────────────────────────────────────────

# 项目根目录
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 输出目录
OUTPUTS_DIR: str = os.path.join(PROJECT_ROOT, "outputs")

# 日志目录
LOGS_DIR: str = os.path.join(OUTPUTS_DIR, "logs")

# 缓存目录
CACHE_DIR: str = os.path.join(OUTPUTS_DIR, "cache")


def get_config_summary() -> dict:
    """返回当前配置摘要（用于日志和调试）。"""
    return {
        "data_vendor": get_data_vendor(),
        "vendor_fallback_chain": get_vendor_fallback_chain(),
        "checkpoint_enabled": CHECKPOINT_ENABLED,
        "checkpoint_dir": CHECKPOINT_DIR,
        "deep_model": DEEP_MODEL or "(not set)",
        "quick_model": QUICK_MODEL or "(not set)",
    }
