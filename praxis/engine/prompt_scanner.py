"""Prompt 安全扫描器

检测 Prompt 中的危险指令，防止安全语义被破坏。
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel


class ScanResult(BaseModel):
    """扫描结果"""
    file_path: str
    is_safe: bool
    dangerous_patterns: list[dict]  # [{pattern, line, line_num, severity}]
    warnings: list[str]


class PromptScanner:
    """Prompt 安全扫描器"""

    # 危险模式列表
    DANGEROUS_PATTERNS = [
        # 绕过安全规则
        {
            "pattern": r"忽略.*安全.*规则",
            "severity": "critical",
            "description": "绕过安全规则",
        },
        {
            "pattern": r"可以.*忽略.*风控",
            "severity": "critical",
            "description": "绕过风控",
        },
        {
            "pattern": r"在特殊情况下.*忽略",
            "severity": "critical",
            "description": "条件绕过",
        },
        {
            "pattern": r"override.*safety",
            "severity": "critical",
            "description": "覆盖安全设置",
        },
        {
            "pattern": r"ignore.*constraint",
            "severity": "critical",
            "description": "忽略约束",
        },

        # 扩大权限
        {
            "pattern": r"自动.*审批",
            "severity": "high",
            "description": "自动审批",
        },
        {
            "pattern": r"不需要.*人工.*确认",
            "severity": "high",
            "description": "绕过人工确认",
        },
        {
            "pattern": r"skip.*approval",
            "severity": "high",
            "description": "跳过审批",
        },

        # 弱化规则
        {
            "pattern": r"降低.*底线",
            "severity": "medium",
            "description": "降低底线",
        },
        {
            "pattern": r"放宽.*限制",
            "severity": "medium",
            "description": "放宽限制",
        },
        {
            "pattern": r"relax.*rule",
            "severity": "medium",
            "description": "放松规则",
        },

        # 角色压倒
        {
            "pattern": r"角色.*压倒.*规则",
            "severity": "high",
            "description": "角色设定压倒规则",
        },
        {
            "pattern": r"role.*override.*rule",
            "severity": "high",
            "description": "角色覆盖规则",
        },
    ]

    def scan_file(self, file_path: str | Path) -> ScanResult:
        """扫描单个文件"""
        path = Path(file_path)
        if not path.exists():
            return ScanResult(
                file_path=str(path),
                is_safe=True,
                dangerous_patterns=[],
                warnings=[f"文件不存在: {path}"],
            )

        content = path.read_text(encoding="utf-8")
        return self.scan_content(content, str(path))

    def scan_content(self, content: str, file_path: str = "<content>") -> ScanResult:
        """扫描内容"""
        dangerous_patterns = []
        warnings = []

        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            for pattern_info in self.DANGEROUS_PATTERNS:
                if re.search(pattern_info["pattern"], line, re.IGNORECASE):
                    dangerous_patterns.append({
                        "pattern": pattern_info["pattern"],
                        "line": line.strip(),
                        "line_num": line_num,
                        "severity": pattern_info["severity"],
                        "description": pattern_info["description"],
                    })

        is_safe = len(dangerous_patterns) == 0

        if not is_safe:
            critical_count = sum(1 for p in dangerous_patterns if p["severity"] == "critical")
            high_count = sum(1 for p in dangerous_patterns if p["severity"] == "high")
            warnings.append(f"发现 {len(dangerous_patterns)} 个危险模式: {critical_count} 严重, {high_count} 高危")

        return ScanResult(
            file_path=file_path,
            is_safe=is_safe,
            dangerous_patterns=dangerous_patterns,
            warnings=warnings,
        )

    def scan_directory(self, dir_path: str | Path) -> dict[str, ScanResult]:
        """扫描目录下所有 Prompt 文件"""
        path = Path(dir_path)
        results = {}

        if not path.exists():
            return results

        for md_file in path.rglob("*.md"):
            results[str(md_file)] = self.scan_file(md_file)

        return results

    def format_result(self, result: ScanResult) -> str:
        """格式化扫描结果"""
        lines = [
            f"=== Prompt 安全扫描 ===",
            f"文件: {result.file_path}",
            f"状态: {'安全' if result.is_safe else '危险'}",
        ]

        if result.dangerous_patterns:
            lines.append(f"\n--- 危险模式 ({len(result.dangerous_patterns)}) ---")
            for p in result.dangerous_patterns:
                lines.append(f"  [{p['severity'].upper()}] 第 {p['line_num']} 行: {p['description']}")
                lines.append(f"    内容: {p['line'][:50]}...")

        if result.warnings:
            lines.append(f"\n--- 警告 ---")
            for w in result.warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)
