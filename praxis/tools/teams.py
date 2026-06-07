"""MCP 工具 - AI 团队"""
from __future__ import annotations

from pathlib import Path

from praxis.engine.prompt_composer import PromptComposer


def list_teams(workspace: str = ".") -> dict:
    """列出所有可用的 AI 团队"""
    teams_dir = Path(workspace) / "teams" / "base_prompts"
    if not teams_dir.exists():
        return {"success": True, "data": {"teams": []}}

    teams = []
    for md_file in sorted(teams_dir.glob("*.md")):
        team_name = md_file.stem
        # 读取前几行获取描述
        with open(md_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[:5]
        description = ""
        for line in lines:
            if line.strip() and not line.startswith("#"):
                description = line.strip()
                break

        teams.append({
            "name": team_name,
            "file": md_file.name,
            "description": description,
        })

    return {
        "success": True,
        "data": {"teams": teams},
    }


def get_team_prompt(team_name: str, workspace: str = ".") -> dict:
    """获取指定团队的完整 Prompt"""
    team_path = Path(workspace) / "teams" / "base_prompts" / f"{team_name}.md"
    if not team_path.exists():
        return {"success": False, "error": f"团队 {team_name} 不存在"}

    try:
        content = team_path.read_text(encoding="utf-8")
        return {
            "success": True,
            "data": {
                "team_name": team_name,
                "content": content,
                "length": len(content),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_output_templates(workspace: str = ".") -> dict:
    """列出所有输出模板"""
    templates_dir = Path(workspace) / "teams" / "output_templates"
    if not templates_dir.exists():
        return {"success": True, "data": {"templates": []}}

    templates = []
    for md_file in sorted(templates_dir.glob("*.md")):
        template_name = md_file.stem
        # 读取前几行获取描述
        with open(md_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[:5]
        description = ""
        for line in lines:
            if line.strip() and not line.startswith("#"):
                description = line.strip()
                break

        templates.append({
            "name": template_name,
            "file": md_file.name,
            "description": description,
        })

    return {
        "success": True,
        "data": {"templates": templates},
    }


def get_output_template(template_name: str, workspace: str = ".") -> dict:
    """获取指定输出模板"""
    template_path = Path(workspace) / "teams" / "output_templates" / f"{template_name}.md"
    if not template_path.exists():
        return {"success": False, "error": f"模板 {template_name} 不存在"}

    try:
        content = template_path.read_text(encoding="utf-8")
        return {
            "success": True,
            "data": {
                "template_name": template_name,
                "content": content,
                "length": len(content),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_output_template(template_name: str, new_content: str, reason: str, workspace: str = ".") -> dict:
    """更新输出模板（需审批）

    流程：
    1. 备份原模板
    2. 预览变更
    3. 返回 pending_approval 状态
    """
    template_path = Path(workspace) / "teams" / "output_templates" / f"{template_name}.md"
    if not template_path.exists():
        return {"success": False, "error": f"模板 {template_name} 不存在"}

    try:
        # 读取原内容
        old_content = template_path.read_text(encoding="utf-8")

        # 计算 diff
        old_lines = old_content.split("\n")
        new_lines = new_content.split("\n")
        diff_lines = []
        for i, (old, new) in enumerate(zip(old_lines, new_lines)):
            if old != new:
                diff_lines.append(f"- {i+1}: {old}")
                diff_lines.append(f"+ {i+1}: {new}")
        diff = "\n".join(diff_lines) if diff_lines else "无差异"

        # 备份
        from datetime import datetime
        backup_path = template_path.with_suffix(f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        import shutil
        shutil.copy2(template_path, backup_path)

        return {
            "success": True,
            "data": {
                "status": "pending_approval",
                "template_name": template_name,
                "backup_path": str(backup_path),
                "diff": diff[:1000],
                "reason": reason,
                "message": f"模板变更预览已生成，备份已创建。请确认后执行。",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def approve_output_template_update(template_name: str, new_content: str, workspace: str = ".") -> dict:
    """审批通过后执行模板更新"""
    template_path = Path(workspace) / "teams" / "output_templates" / f"{template_name}.md"
    if not template_path.exists():
        return {"success": False, "error": f"模板 {template_name} 不存在"}

    try:
        template_path.write_text(new_content, encoding="utf-8")
        return {
            "success": True,
            "data": {
                "message": f"模板 {template_name} 已更新",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_output_template(template_name: str, content: str, workspace: str = ".") -> dict:
    """创建新的输出模板"""
    template_path = Path(workspace) / "teams" / "output_templates" / f"{template_name}.md"
    if template_path.exists():
        return {"success": False, "error": f"模板 {template_name} 已存在"}

    try:
        template_path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "data": {
                "message": f"模板 {template_name} 已创建",
                "path": str(template_path),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def compose_team_prompt(
    team_name: str,
    strategy_name: str = "grid_value",
    investor_id: str = "example",
    workspace: str = ".",
) -> dict:
    """组合团队 Prompt（基础 + 团队 + 策略 + 投资者）"""
    try:
        composer = PromptComposer(workspace)
        prompt = composer.compose(team_name, strategy_name, investor_id)
        return {
            "success": True,
            "data": {
                "team_name": team_name,
                "strategy_name": strategy_name,
                "investor_id": investor_id,
                "prompt": prompt,
                "length": len(prompt),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
