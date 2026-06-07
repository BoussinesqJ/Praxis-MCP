"""AI Prompt 注入器（增强版）

核心职责：
1. 加载基础 prompt（从新目录结构）
2. 注入策略上下文
3. 注入投资者画像
4. 安全扫描
5. 变更审批
"""
from __future__ import annotations

from pathlib import Path

from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.prompt_scanner import PromptScanner
from praxis.engine.prompt_change_recorder import PromptChangeRecorder
from praxis.core.models.prompt_change import PromptChange


class PromptComposer:
    """Prompt 组合器（增强版）"""

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._config = YamlConfigLoader(workspace)
        self._scanner = PromptScanner()
        self._recorder = PromptChangeRecorder(
            workspace + "/data/audit/prompt_changes.jsonl"
        )

    def compose(
        self,
        team_name: str,
        strategy_name: str,
        investor_id: str | None = None,
        extra_context: str | None = None,
    ) -> str:
        """组合 prompt"""
        parts = []

        # 1. 基础 prompt（从 teams/base/ 加载）
        base_prompt = self._load_base_prompt()
        if base_prompt:
            parts.append(base_prompt)

        # 2. 团队 prompt（从 teams/base_prompts/ 加载）
        team_prompt = self._load_team_prompt(team_name)
        if team_prompt:
            parts.append(f"---\n## 团队 Prompt：{team_name}\n\n{team_prompt}")

        # 3. 策略上下文注入
        strategy_context = self._load_strategy_context(strategy_name, team_name)
        if strategy_context:
            parts.append(strategy_context)

        # 4. 投资者画像注入
        if investor_id:
            investor_context = self._load_investor_context(investor_id)
            if investor_context:
                parts.append(investor_context)

        # 5. 自适应规则注入
        adaptive_context = self._load_adaptive_context()
        if adaptive_context:
            parts.append(adaptive_context)

        # 6. 额外上下文
        if extra_context:
            parts.append(f"\n---\n## 额外上下文\n{extra_context}")

        return "\n\n".join(parts)

    def _load_base_prompt(self) -> str:
        """加载基础 prompt（从 teams/base/）"""
        base_dir = self._workspace / "teams" / "base"
        if not base_dir.exists():
            return ""

        parts = []
        for md_file in sorted(base_dir.glob("*.md")):
            parts.append(md_file.read_text(encoding="utf-8"))

        return "\n\n".join(parts)

    def _load_team_prompt(self, team_name: str) -> str:
        """加载团队 prompt（从 teams/base_prompts/）"""
        team_path = self._workspace / "teams" / "base_prompts" / f"{team_name}.md"
        if team_path.exists():
            return team_path.read_text(encoding="utf-8")
        return ""

    def _load_strategy_context(self, strategy_name: str, team_name: str) -> str:
        """加载策略上下文"""
        strategy_path = self._workspace / "teams" / "strategy" / f"{strategy_name}.md"
        if strategy_path.exists():
            return strategy_path.read_text(encoding="utf-8")

        # 回退到旧路径
        try:
            strategy = self._config.load_strategy(strategy_name)
            team_config = strategy.ai_teams.model_dump()
            team_data = team_config.get(team_name, {})
            emphasis = team_data.get("emphasis", [])
            debate_focus = team_data.get("debate_focus", "")

            if not emphasis and not debate_focus:
                return ""

            lines = [
                "---",
                "## 当前策略上下文（自动注入）",
                f"**策略类型**：{strategy.name}",
            ]

            if emphasis:
                lines.append("\n**重点分析**：")
                for item in emphasis:
                    lines.append(f"- {item}")

            if debate_focus:
                lines.append(f"\n**辩论焦点**：{debate_focus}")

            return "\n".join(lines)
        except Exception:
            return ""

    def _load_investor_context(self, investor_id: str) -> str:
        """加载投资者画像"""
        investor_path = self._workspace / "teams" / "investor" / f"{investor_id}.md"
        if investor_path.exists():
            return investor_path.read_text(encoding="utf-8")

        # 回退到旧路径
        try:
            investor = self._config.load_investor(investor_id)
            lines = [
                "---",
                "## 投资者画像（自动注入）",
                f"**投资者**：{investor.name}",
                f"**风险等级**：{investor.risk_level}",
                f"**投资风格**：{investor.style}",
            ]

            if investor.philosophy.beliefs:
                lines.append("\n**投资信条**：")
                for belief in investor.philosophy.beliefs:
                    lines.append(f"- {belief}")

            return "\n".join(lines)
        except Exception:
            return ""

    def _load_adaptive_context(self) -> str:
        """加载自适应规则"""
        adaptive_path = self._workspace / "teams" / "adaptive" / "learned_rules.md"
        if adaptive_path.exists():
            return adaptive_path.read_text(encoding="utf-8")
        return ""

    def scan_prompt(self, file_path: str) -> dict:
        """扫描 Prompt 文件"""
        result = self._scanner.scan_file(file_path)
        return result.model_dump()

    def propose_change(
        self,
        file_path: str,
        new_content: str,
        reason: str,
    ) -> dict:
        """提议 Prompt 变更"""
        # 1. 安全扫描新内容
        scan_result = self._scanner.scan_content(new_content, file_path)

        if not scan_result.is_safe:
            return {
                "success": False,
                "error": "安全扫描未通过",
                "scan_result": scan_result.model_dump(),
            }

        # 2. 计算 hash
        import hashlib
        old_path = Path(file_path)
        old_hash = hashlib.md5(old_path.read_bytes()).hexdigest() if old_path.exists() else ""
        new_hash = hashlib.md5(new_content.encode()).hexdigest()

        # 3. 计算 diff
        old_content = old_path.read_text(encoding="utf-8") if old_path.exists() else ""
        diff = self._calculate_diff(old_content, new_content)

        # 4. 记录变更
        change = PromptChange(
            change_id="",
            file_path=file_path,
            old_hash=old_hash,
            new_hash=new_hash,
            diff=diff,
            reason=reason,
            scanner_result=scan_result.model_dump(),
        )
        change_id = self._recorder.record(change)

        return {
            "success": True,
            "data": {
                "change_id": change_id,
                "status": "pending_approval",
                "scan_result": scan_result.model_dump(),
                "diff": diff[:500],  # 只返回前500字符
                "message": "变更已记录，需人工审批后执行",
            },
        }

    def _calculate_diff(self, old_content: str, new_content: str) -> str:
        """计算差异"""
        old_lines = old_content.split("\n")
        new_lines = new_content.split("\n")

        diff_lines = []
        for i, (old, new) in enumerate(zip(old_lines, new_lines)):
            if old != new:
                diff_lines.append(f"- {i+1}: {old}")
                diff_lines.append(f"+ {i+1}: {new}")

        return "\n".join(diff_lines) if diff_lines else "无差异"
