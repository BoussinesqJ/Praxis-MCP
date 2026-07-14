"""团队管理工具 — 管理 3 个 AI 分析团队（ASRG/Masters/Trading）

action: list | info | prompts | update_prompt
"""
from __future__ import annotations

from pathlib import Path

from praxis.agents.base import Tool
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)

# 内置 3 个团队定义
BUILTIN_TEAMS = {
    "asrg": {
        "name": "ASRG",
        "full_name": "Absolute Return Strategy Group",
        "description": "绝对收益策略组 — 宏观驱动，风险优先",
        "role": "宏观策略",
        "model_hint": "deep",
        "default_prompt": "从宏观视角分析市场，关注估值、流动性、政策周期。\n决策标准: 安全边际 > 30%, 仓位上限 = 哨兵限额。",
    },
    "masters": {
        "name": "Masters",
        "full_name": "Masters of the Market",
        "description": "市场大师组 — 趋势跟随，动量驱动",
        "role": "技术分析",
        "model_hint": "deep",
        "default_prompt": "从趋势和动量角度分析，关注均线、成交量、相对强度。\n决策标准: 趋势确认后入场，止损严格 -5%。",
    },
    "trading": {
        "name": "Trading",
        "full_name": "Trading Desk",
        "description": "交易执行组 — 执行优化，成本最小化",
        "role": "交易执行",
        "model_hint": "quick",
        "default_prompt": "优化执行策略，控制摩擦成本。\n关注点: 滑点估计、流动性、交易时间窗口。\n决策标准: 滑点 < 2bps, 单笔成本 < 50元。",
    },
}


def _get_config_dir() -> Path:
    """获取 config/teams/ 目录路径"""
    base = Path(__file__).resolve().parent.parent / "config" / "teams"
    return base


def _ensure_team_dir(team_name: str) -> Path:
    """确保团队目录存在并返回路径"""
    team_dir = _get_config_dir() / team_name
    team_dir.mkdir(parents=True, exist_ok=True)
    return team_dir


def _get_prompt_file(team_name: str, prompt_file: str) -> Path | None:
    """获取 prompt 文件路径"""
    team_dir = _get_config_dir() / team_name
    if not team_dir.exists():
        return None
    path = team_dir / prompt_file
    if path.exists() and path.is_file():
        return path
    return None


def _list_prompts(team_name: str) -> list[str]:
    """列出团队目录下的所有 prompt 文件"""
    team_dir = _get_config_dir() / team_name
    if not team_dir.exists():
        return []
    return [
        f.name for f in team_dir.iterdir()
        if f.is_file() and f.suffix in (".md", ".txt")
    ]


async def teams(
    action: str,
    team_name: str = "",
    prompt_file: str = "",
    _deps: dict | None = None,
) -> dict:
    """团队管理入口

    Args:
        action: "list" | "info" | "prompts" | "update_prompt"
        team_name: 团队名称 (asrg/masters/trading)
        prompt_file: prompt 文件名
        _deps: 依赖注入字典

    Returns:
        {success: bool, data: dict, error: str | None}
    """
    if action == "list":
        return {
            "success": True,
            "data": {
                "teams": [
                    {"name": k, "description": v["description"], "role": v["role"]}
                    for k, v in BUILTIN_TEAMS.items()
                ],
                "count": len(BUILTIN_TEAMS),
            },
            "error": None,
        }

    if action == "info":
        if not team_name:
            return {"success": False, "data": None, "error": "需提供 team_name"}
        team = BUILTIN_TEAMS.get(team_name)
        if not team:
            return {"success": False, "data": None, "error": f"未知团队: {team_name}"}
        return {"success": True, "data": {"team": team}, "error": None}

    if action == "prompts":
        if not team_name:
            return {"success": False, "data": None, "error": "需提供 team_name"}
        if team_name not in BUILTIN_TEAMS:
            return {"success": False, "data": None, "error": f"未知团队: {team_name}"}

        prompt_list = _list_prompts(team_name)

        # 如果目录下没有文件，返回默认 prompt
        if not prompt_list:
            _ensure_team_dir(team_name)
            return {
                "success": True,
                "data": {
                    "team": team_name,
                    "templates": ["default_prompt"],
                    "default_content": BUILTIN_TEAMS[team_name]["default_prompt"],
                },
                "error": None,
            }

        return {
            "success": True,
            "data": {
                "team": team_name,
                "templates": prompt_list,
            },
            "error": None,
        }

    if action == "update_prompt":
        if not team_name:
            return {"success": False, "data": None, "error": "需提供 team_name"}
        if team_name not in BUILTIN_TEAMS:
            return {"success": False, "data": None, "error": f"未知团队: {team_name}"}
        if not prompt_file:
            return {"success": False, "data": None, "error": "需提供 prompt_file"}

        content = _deps.get("prompt_content", "") if _deps else ""
        team_dir = _ensure_team_dir(team_name)
        file_path = team_dir / prompt_file
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"prompt 已更新: {file_path}")
            return {
                "success": True,
                "data": {
                    "team": team_name,
                    "file": prompt_file,
                    "path": str(file_path),
                },
                "error": None,
            }
        except Exception as e:
            logger.error(f"更新 prompt 失败: {e}")
            return {"success": False, "data": None, "error": f"写入失败: {e}"}

    return {"success": False, "data": None, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(
        name="teams",
        description="AI 分析团队管理：列出团队(list)/查看详情(info)/查看 prompt 模板(prompts)/更新 prompt(update_prompt)。团队: asrg/masters/trading",
        input_schema=type("TeamsInput", (), {}),
        handler=teams,
        agent_name="admin",
        tier="advanced",
        is_readonly=False,
    ))
