"""MCP 工具 - Prompt 版本管理

GPT 要求：增加 Prompt Sandbox，支持版本管理、回滚、安全检查。
"""
from __future__ import annotations

from praxis.engine.prompt_versioning import PromptVersionManager, PromptSafetyChecker


def list_prompt_versions(
    prompt_name: str,
    workspace: str = ".",
) -> dict:
    """列出 Prompt 的所有版本

    Args:
        prompt_name: Prompt 名称

    Returns:
        版本列表
    """
    try:
        manager = PromptVersionManager(workspace)
        versions = manager.list_versions(prompt_name)
        return {
            "success": True,
            "data": {
                "prompt_name": prompt_name,
                "versions": [v.model_dump() for v in versions],
                "total": len(versions),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_prompt_version(
    prompt_name: str,
    version: str | None = None,
    workspace: str = ".",
) -> dict:
    """获取指定版本的 Prompt

    Args:
        prompt_name: Prompt 名称
        version: 版本号（可选，默认获取最新活动版本）

    Returns:
        Prompt 内容
    """
    try:
        manager = PromptVersionManager(workspace)
        content = manager.get_prompt(prompt_name, version)
        return {
            "success": True,
            "data": {
                "prompt_name": prompt_name,
                "version": version or "latest",
                "content": content,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_prompt_version(
    prompt_name: str,
    content: str,
    description: str | None = None,
    workspace: str = ".",
) -> dict:
    """创建新版本

    Args:
        prompt_name: Prompt 名称
        content: Prompt 内容
        description: 版本描述

    Returns:
        新版本信息
    """
    try:
        manager = PromptVersionManager(workspace)
        version = manager.create_version(
            prompt_name=prompt_name,
            content=content,
            description=description,
        )
        return {
            "success": True,
            "data": version.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def rollback_prompt(
    prompt_name: str,
    target_version: str,
    reason: str,
    workspace: str = ".",
) -> dict:
    """回滚到指定版本

    Args:
        prompt_name: Prompt 名称
        target_version: 目标版本
        reason: 回滚原因

    Returns:
        回滚后的版本信息
    """
    try:
        manager = PromptVersionManager(workspace)
        version = manager.rollback(prompt_name, target_version, reason)
        return {
            "success": True,
            "data": version.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_prompt_safety(
    content: str,
    workspace: str = ".",
) -> dict:
    """检查 Prompt 安全性

    Args:
        content: Prompt 内容

    Returns:
        安全检查结果
    """
    try:
        checker = PromptSafetyChecker()
        result = checker.check_safety(content)
        return {
            "success": True,
            "data": result.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_version_diff(
    prompt_name: str,
    from_version: str,
    to_version: str,
    workspace: str = ".",
) -> dict:
    """获取版本差异

    Args:
        prompt_name: Prompt 名称
        from_version: 起始版本
        to_version: 目标版本

    Returns:
        差异信息
    """
    try:
        manager = PromptVersionManager(workspace)
        diff = manager.get_version_diff(prompt_name, from_version, to_version)
        return {
            "success": True,
            "data": diff,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
