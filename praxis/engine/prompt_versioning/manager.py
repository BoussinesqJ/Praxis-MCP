"""Prompt 版本管理器

GPT 要求：Prompt Sandbox，支持版本管理、回滚、审计。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PromptVersion(BaseModel):
    """Prompt 版本"""
    version_id: str
    prompt_name: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    description: str | None = None
    parent_version: str | None = None
    is_active: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptChange(BaseModel):
    """Prompt 变更记录"""
    change_id: str
    prompt_name: str
    from_version: str | None
    to_version: str
    change_type: str  # create, update, rollback
    change_description: str
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    changed_by: str = "system"
    diff_summary: str | None = None


class PromptVersionManager:
    """Prompt 版本管理器"""

    def __init__(self, workspace: str | Path):
        self._workspace = Path(workspace)
        self._prompts_dir = self._workspace / "teams" / "base_prompts"
        self._versions_dir = self._workspace / "data" / "prompt_versions"
        self._versions_dir.mkdir(parents=True, exist_ok=True)

    def list_prompts(self) -> list[str]:
        """列出所有 Prompt"""
        if not self._prompts_dir.exists():
            return []
        return [f.stem for f in self._prompts_dir.glob("*.md")]

    def get_prompt(self, prompt_name: str, version: str | None = None) -> str:
        """获取 Prompt 内容

        Args:
            prompt_name: Prompt 名称
            version: 版本号（可选，默认获取最新活动版本）

        Returns:
            Prompt 内容
        """
        if version:
            # 获取指定版本
            version_file = self._versions_dir / prompt_name / f"{version}.json"
            if version_file.exists():
                with open(version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data["content"]
            raise ValueError(f"版本 {version} 不存在")

        # 获取最新活动版本
        versions = self.list_versions(prompt_name)
        if versions:
            active_versions = [v for v in versions if v.is_active]
            if active_versions:
                return active_versions[-1].content

        # 回退到原始文件
        prompt_file = self._prompts_dir / f"{prompt_name}.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        raise ValueError(f"Prompt {prompt_name} 不存在")

    def create_version(
        self,
        prompt_name: str,
        content: str,
        description: str | None = None,
        created_by: str = "user",
    ) -> PromptVersion:
        """创建新版本

        Args:
            prompt_name: Prompt 名称
            content: Prompt 内容
            description: 版本描述
            created_by: 创建者

        Returns:
            新版本对象
        """
        # 生成版本号
        versions = self.list_versions(prompt_name)
        if versions:
            last_version = versions[-1].version_id
            # 从 v1.0.0 格式提取版本号
            parts = last_version.replace("v", "").split(".")
            new_version_num = int(parts[-1]) + 1
            version_id = f"v{parts[0]}.{parts[1]}.{new_version_num}"
        else:
            version_id = "v1.0.0"

        # 获取父版本
        parent_version = None
        if versions:
            parent_version = versions[-1].version_id

        # 创建版本对象
        version = PromptVersion(
            version_id=version_id,
            prompt_name=prompt_name,
            content=content,
            created_by=created_by,
            description=description,
            parent_version=parent_version,
            is_active=True,
        )

        # 保存版本
        self._save_version(version)

        # 记录变更
        self._record_change(
            prompt_name=prompt_name,
            from_version=parent_version,
            to_version=version_id,
            change_type="create" if not parent_version else "update",
            change_description=description or f"创建版本 {version_id}",
            changed_by=created_by,
        )

        return version

    def rollback(self, prompt_name: str, target_version: str, reason: str) -> PromptVersion:
        """回滚到指定版本

        Args:
            prompt_name: Prompt 名称
            target_version: 目标版本
            reason: 回滚原因

        Returns:
            回滚后的版本对象
        """
        # 获取目标版本内容
        target_content = self.get_prompt(prompt_name, target_version)

        # 创建新版本（回滚）
        new_version = self.create_version(
            prompt_name=prompt_name,
            content=target_content,
            description=f"回滚到 {target_version}: {reason}",
            created_by="system",
        )

        return new_version

    def list_versions(self, prompt_name: str) -> list[PromptVersion]:
        """列出所有版本"""
        versions_dir = self._versions_dir / prompt_name
        if not versions_dir.exists():
            return []

        versions = []
        for version_file in sorted(versions_dir.glob("*.json")):
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            versions.append(PromptVersion(**data))

        return versions

    def get_version_diff(self, prompt_name: str, from_version: str, to_version: str) -> dict:
        """获取版本差异

        Args:
            prompt_name: Prompt 名称
            from_version: 起始版本
            to_version: 目标版本

        Returns:
            差异信息
        """
        from_content = self.get_prompt(prompt_name, from_version)
        to_content = self.get_prompt(prompt_name, to_version)

        # 简单的行数对比
        from_lines = from_content.split("\n")
        to_lines = to_content.split("\n")

        added_lines = len(to_lines) - len(from_lines)

        return {
            "from_version": from_version,
            "to_version": to_version,
            "from_lines": len(from_lines),
            "to_lines": len(to_lines),
            "added_lines": max(0, added_lines),
            "removed_lines": max(0, -added_lines),
            "content_changed": from_content != to_content,
        }

    def _save_version(self, version: PromptVersion):
        """保存版本到文件"""
        versions_dir = self._versions_dir / version.prompt_name
        versions_dir.mkdir(parents=True, exist_ok=True)

        version_file = versions_dir / f"{version.version_id}.json"
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(version.model_dump(), f, ensure_ascii=False, indent=2, default=str)

    def _record_change(
        self,
        prompt_name: str,
        from_version: str | None,
        to_version: str,
        change_type: str,
        change_description: str,
        changed_by: str,
    ):
        """记录变更"""
        changes_dir = self._workspace / "data" / "audit" / "prompt_changes.jsonl"
        changes_dir.parent.mkdir(parents=True, exist_ok=True)

        change = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_name": prompt_name,
            "from_version": from_version,
            "to_version": to_version,
            "change_type": change_type,
            "change_description": change_description,
            "changed_by": changed_by,
        }

        with open(changes_dir, "a", encoding="utf-8") as f:
            f.write(json.dumps(change, ensure_ascii=False) + "\n")
