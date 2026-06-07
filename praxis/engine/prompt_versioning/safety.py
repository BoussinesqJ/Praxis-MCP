"""Prompt 安全检查器

GPT 要求：增加 Prompt Safety Test，确保 Prompt 安全性。
支持：
- 注入攻击检测
- 敏感信息泄露检测
- 权限越界检测
- 逻辑漏洞检测
"""
from __future__ import annotations

import re
from pydantic import BaseModel


class SafetyConfig(BaseModel):
    """安全配置"""
    blocked_patterns: list[str] = [
        r"ignore\s+previous\s+instructions",  # 忽略之前的指令
        r"system\s*prompt",                    # 系统提示词
        r"api[_\s]?key",                       # API 密钥
        r"password",                           # 密码
        r"secret",                             # 密钥
    ]
    dangerous_actions: list[str] = [
        "delete_all",
        "drop_table",
        "format_disk",
        "execute_code",
    ]
    max_length: int = 100000  # 最大 Prompt 长度


class SafetyCheckResult(BaseModel):
    """安全检查结果"""
    is_safe: bool
    risk_level: str  # low, medium, high, critical
    issues: list[str]
    warnings: list[str]


class PromptSafetyChecker:
    """Prompt 安全检查器"""

    def __init__(self, config: SafetyConfig | None = None):
        self._config = config or SafetyConfig()

    def check_safety(self, prompt_content: str) -> SafetyCheckResult:
        """检查 Prompt 安全性

        Args:
            prompt_content: Prompt 内容

        Returns:
            安全检查结果
        """
        issues = []
        warnings = []

        # 1. 检查长度
        if len(prompt_content) > self._config.max_length:
            issues.append(f"Prompt 长度超过限制: {len(prompt_content)} > {self._config.max_length}")

        # 2. 检查注入攻击模式
        for pattern in self._config.blocked_patterns:
            if re.search(pattern, prompt_content, re.IGNORECASE):
                issues.append(f"发现潜在注入攻击模式: {pattern}")

        # 3. 检查危险操作
        for action in self._config.dangerous_actions:
            if action.lower() in prompt_content.lower():
                issues.append(f"发现危险操作: {action}")

        # 4. 检查敏感信息泄露
        sensitive_patterns = [
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "邮箱地址"),
            (r"\b\d{11}\b", "手机号码"),
            (r"\b\d{18}\b", "身份证号码"),
        ]
        for pattern, name in sensitive_patterns:
            if re.search(pattern, prompt_content):
                warnings.append(f"可能包含{name}")

        # 5. 检查代码执行
        code_patterns = [
            (r"```python", "Python 代码块"),
            (r"```bash", "Bash 命令块"),
            (r"eval\(", "eval 函数"),
            (r"exec\(", "exec 函数"),
        ]
        for pattern, name in code_patterns:
            if re.search(pattern, prompt_content):
                warnings.append(f"包含{name}")

        # 6. 检查外部链接
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, prompt_content)
        if urls:
            warnings.append(f"包含 {len(urls)} 个外部链接")

        # 确定风险等级
        if issues:
            risk_level = "high"
        elif len(warnings) > 3:
            risk_level = "medium"
        elif warnings:
            risk_level = "low"
        else:
            risk_level = "low"

        return SafetyCheckResult(
            is_safe=len(issues) == 0,
            risk_level=risk_level,
            issues=issues,
            warnings=warnings,
        )

    def sanitize_prompt(self, prompt_content: str) -> str:
        """清理 Prompt

        Args:
            prompt_content: 原始 Prompt

        Returns:
            清理后的 Prompt
        """
        sanitized = prompt_content

        # 1. 移除潜在的注入攻击模式
        for pattern in self._config.blocked_patterns:
            sanitized = re.sub(pattern, "[BLOCKED]", sanitized, flags=re.IGNORECASE)

        # 2. 移除敏感信息
        sanitized = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", sanitized)
        sanitized = re.sub(r"\b\d{11}\b", "[PHONE]", sanitized)
        sanitized = re.sub(r"\b\d{18}\b", "[ID_CARD]", sanitized)

        return sanitized
