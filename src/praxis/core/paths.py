"""PRAXIS 工作区路径工具

提供标准化的工作区目录结构路径解析。
所有路径函数接受 workspace 根目录，返回标准化的子目录路径字典。
"""

from __future__ import annotations

from pathlib import Path


def get_paths(workspace: str | Path) -> dict[str, Path]:
    """获取工作区标准路径字典

    从 workspace 根目录派生出标准子目录结构：

    目录结构:
        {workspace}/
        ├── config/          — 配置文件（投资者、组合、策略）
        ├── data/            — 数据缓存（行情、K线）
        ├── ledger/          — 交易账本 JSONL 文件
        ├── nav/             — 净值历史记录
        ├── sentinel/        — 哨兵信号记录
        ├── decisions/       — 决策记录
        ├── strategies/      — 策略模板存放
        └── praxis.db        — SQLite 数据库（Guardrail/状态存储）

    Args:
        workspace: 工作区根目录路径

    Returns:
        路径字典: {
            data:       数据缓存目录
            config:     配置目录
            ledger:     账本目录
            nav:        净值目录
            sentinel:   哨兵目录
            decisions:  决策目录
            strategies: 策略目录
            db:         SQLite 数据库文件路径
        }

    Example:
        >>> paths = get_paths("./my_portfolio")
        >>> paths["config"]  # PosixPath('my_portfolio/config')
        >>> paths["db"]      # PosixPath('my_portfolio/praxis.db')
    """
    root = Path(workspace).resolve()

    # NOTE(0710修复): ledger/nav/decisions/sentinel 的真实历史数据均位于
    # {workspace}/data/ 下（与 SentinelEngine 硬编码的 data/sentinel_history.jsonl
    # 保持一致）。此前这些键指向根级空目录，导致 reconcile/performance/nav 读到
    # 空账本。现统一收敛到 data/ 前缀，使读写指向同一真实数据源。
    data_root = root / "data"

    paths: dict[str, Path] = {
        "data":       data_root,
        "config":     root / "config",
        "ledger":     data_root / "ledger",
        "nav":        data_root / "nav",
        "sentinel":   data_root / "sentinel",
        "decisions":  data_root / "decisions",
        "strategies": root / "strategies",
        "db":         root / "db" / "praxis.db",
    }

    return paths


def ensure_paths(workspace: str | Path) -> dict[str, Path]:
    """获取路径并自动创建所有子目录

    与 get_paths 相同，但额外创建所有不存在的目录。

    Args:
        workspace: 工作区根目录

    Returns:
        路径字典（所有目录已确保存在）
    """
    paths = get_paths(workspace)

    for key, path in paths.items():
        if key == "db":
            # db 是文件，只需确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)

    return paths


def get_ledger_path(workspace: str | Path, name: str = "transactions") -> Path:
    """获取指定账本的 JSONL 文件路径

    Args:
        workspace: 工作区根目录
        name: 账本名称（默认 "transactions"）

    Returns:
        JSONL 文件完整路径
    """
    paths = get_paths(workspace)
    paths["ledger"].mkdir(parents=True, exist_ok=True)
    return paths["ledger"] / f"{name}.jsonl"


def get_nav_path(workspace: str | Path, portfolio_id: str) -> Path:
    """获取指定组合的净值文件路径

    Args:
        workspace: 工作区根目录
        portfolio_id: 组合 ID

    Returns:
        净值 CSV 文件路径
    """
    paths = get_paths(workspace)
    paths["nav"].mkdir(parents=True, exist_ok=True)
    return paths["nav"] / f"{portfolio_id}_nav.csv"


def get_decision_path(workspace: str | Path, portfolio_id: str) -> Path:
    """获取指定组合的决策记录文件路径

    Args:
        workspace: 工作区根目录
        portfolio_id: 组合 ID

    Returns:
        决策 JSONL 文件路径
    """
    paths = get_paths(workspace)
    paths["decisions"].mkdir(parents=True, exist_ok=True)
    return paths["decisions"] / f"{portfolio_id}_decisions.jsonl"
