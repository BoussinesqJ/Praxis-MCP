"""tests for core/feature_flags.py — FeatureFlag 全静态方法类."""

from __future__ import annotations

import pytest

from praxis.core.feature_flags import FeatureFlag


# ── 场景1：6 个开关默认值 ────────────────────────────────────────


class TestDefaultValues:
    """验证所有开关的默认值。"""

    def test_agent_mode_default_true(self):
        """PRAXIS_AGENT_MODE 默认 True。"""
        assert FeatureFlag.is_enabled("PRAXIS_AGENT_MODE") is True

    def test_guardrail_default_true(self):
        """PRAXIS_GUARDRAIL_ENABLED 默认 True。"""
        assert FeatureFlag.is_enabled("PRAXIS_GUARDRAIL_ENABLED") is True

    def test_memory_default_false(self):
        """PRAXIS_MEMORY_ENABLED 默认 False。"""
        assert FeatureFlag.is_enabled("PRAXIS_MEMORY_ENABLED") is False

    def test_auto_session_default_true(self):
        """PRAXIS_AUTO_SESSION 默认 True。"""
        assert FeatureFlag.is_enabled("PRAXIS_AUTO_SESSION") is True

    def test_storage_backend_default_jsonl(self):
        """PRAXIS_STORAGE_BACKEND 默认 'jsonl'。"""
        assert FeatureFlag.get_value("PRAXIS_STORAGE_BACKEND") == "jsonl"

    def test_orchestration_mode_default_agent(self):
        """PRAXIS_ORCHESTRATION_MODE 默认 'agent'。"""
        assert FeatureFlag.get_value("PRAXIS_ORCHESTRATION_MODE") == "agent"


# ── 场景2：环境变量覆盖 ──────────────────────────────────────────


class TestEnvOverride:
    """monkeypatch 环境变量覆盖测试。"""

    def test_false_override(self, monkeypatch: pytest.MonkeyPatch):
        """设置 'false' 覆盖 True → False。"""
        monkeypatch.setenv("PRAXIS_AGENT_MODE", "false")
        assert FeatureFlag.is_enabled("PRAXIS_AGENT_MODE") is False

    def test_true_values(self, monkeypatch: pytest.MonkeyPatch):
        """true/1/yes/on 四种真值。"""
        for val in ("true", "1", "yes", "on"):
            monkeypatch.setenv("PRAXIS_MEMORY_ENABLED", val)
            assert FeatureFlag.is_enabled("PRAXIS_MEMORY_ENABLED") is True, f"value={val}"

    def test_false_values(self, monkeypatch: pytest.MonkeyPatch):
        """false/0/no/off 四种假值。"""
        for val in ("false", "0", "no", "off"):
            monkeypatch.setenv("PRAXIS_AGENT_MODE", val)
            assert FeatureFlag.is_enabled("PRAXIS_AGENT_MODE") is False, f"value={val}"

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量值大小写不敏感。"""
        monkeypatch.setenv("PRAXIS_AGENT_MODE", "TRUE")
        assert FeatureFlag.is_enabled("PRAXIS_AGENT_MODE") is True
        monkeypatch.setenv("PRAXIS_AGENT_MODE", "False")
        assert FeatureFlag.is_enabled("PRAXIS_AGENT_MODE") is False

    def test_memory_enabled_via_env(self, monkeypatch: pytest.MonkeyPatch):
        """PRAXIS_MEMORY_ENABLED=1 覆盖默认 False。"""
        monkeypatch.setenv("PRAXIS_MEMORY_ENABLED", "1")
        assert FeatureFlag.is_enabled("PRAXIS_MEMORY_ENABLED") is True


# ── 场景3：get_value 非布尔型 ─────────────────────────────────────


class TestGetValue:
    """get_value 非布尔型开关。"""

    def test_storage_backend_default(self):
        """默认返回 'jsonl'。"""
        assert FeatureFlag.get_value("PRAXIS_STORAGE_BACKEND") == "jsonl"

    def test_storage_backend_env_override(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量覆盖后正确返回。"""
        monkeypatch.setenv("PRAXIS_STORAGE_BACKEND", "sqlite")
        assert FeatureFlag.get_value("PRAXIS_STORAGE_BACKEND") == "sqlite"

    def test_orchestration_mode_env_override(self, monkeypatch: pytest.MonkeyPatch):
        """编排模式可覆盖。"""
        monkeypatch.setenv("PRAXIS_ORCHESTRATION_MODE", "hybrid")
        assert FeatureFlag.get_value("PRAXIS_ORCHESTRATION_MODE") == "hybrid"

    def test_storage_backend_is_string_type(self):
        """get_value 返回的是字符串（默认值 str(default)）。"""
        val = FeatureFlag.get_value("PRAXIS_STORAGE_BACKEND")
        assert isinstance(val, str)
        assert val == "jsonl"


# ── 场景4：不存在开关 ─────────────────────────────────────────────


class TestNonexistentFlag:
    """不存在开关的行为。"""

    def test_is_enabled_nonexistent(self):
        """is_enabled 不存在开关返回 False。"""
        assert FeatureFlag.is_enabled("NONEXISTENT_FLAG") is False

    def test_get_value_nonexistent(self):
        """get_value 不存在开关返回 False。"""
        assert FeatureFlag.get_value("NONEXISTENT") is False

    def test_is_enabled_empty_string(self):
        """空字符串也不存在。"""
        assert FeatureFlag.is_enabled("") is False

    def test_is_enabled_random_string(self):
        """随机字符串返回 False。"""
        assert FeatureFlag.is_enabled("RANDOM_UNREGISTERED_FLAG") is False


# ── 场景5：list_all 完整性 ───────────────────────────────────────


class TestListAll:
    """list_all 返回全部开关。"""

    def test_returns_six_keys(self):
        """返回 6 个 key。"""
        all_flags = FeatureFlag.list_all()
        assert len(all_flags) == 6

    def test_keys_structure(self):
        """每个 key 含 value/description/default。"""
        all_flags = FeatureFlag.list_all()
        for key, info in all_flags.items():
            assert "value" in info, f"{key} missing 'value'"
            assert "description" in info, f"{key} missing 'description'"
            assert "default" in info, f"{key} missing 'default'"

    def test_all_expected_keys(self):
        """预期 6 个 key 名。"""
        expected = {
            "PRAXIS_AGENT_MODE",
            "PRAXIS_GUARDRAIL_ENABLED",
            "PRAXIS_STORAGE_BACKEND",
            "PRAXIS_MEMORY_ENABLED",
            "PRAXIS_ORCHESTRATION_MODE",
            "PRAXIS_AUTO_SESSION",
        }
        assert set(FeatureFlag.list_all().keys()) == expected

    def test_default_values_match_definitions(self):
        """值与默认定义一致。"""
        all_flags = FeatureFlag.list_all()
        assert all_flags["PRAXIS_AGENT_MODE"]["default"] is True
        assert all_flags["PRAXIS_MEMORY_ENABLED"]["default"] is False
        assert all_flags["PRAXIS_STORAGE_BACKEND"]["default"] == "jsonl"


# ── 场景6：get_storage_backend 便捷方法 ────────────────────────────


class TestGetStorageBackend:
    """get_storage_backend 便捷方法。"""

    def test_default_returns_jsonl(self):
        """默认返回 'jsonl'。"""
        assert FeatureFlag.get_storage_backend() == "jsonl"

    def test_env_override_returns_correct(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量覆盖后正确返回。"""
        monkeypatch.setenv("PRAXIS_STORAGE_BACKEND", "sqlite")
        assert FeatureFlag.get_storage_backend() == "sqlite"

    def test_returns_type_str(self):
        """始终返回 str 类型。"""
        assert isinstance(FeatureFlag.get_storage_backend(), str)


# ── 场景7：is_auto_session_enabled 便捷方法 ────────────────────────


class TestIsAutoSessionEnabled:
    """is_auto_session_enabled 便捷方法。"""

    def test_default_returns_true(self):
        """默认返回 True。"""
        assert FeatureFlag.is_auto_session_enabled() is True

    def test_env_disable(self, monkeypatch: pytest.MonkeyPatch):
        """设置 false 后返回 False。"""
        monkeypatch.setenv("PRAXIS_AUTO_SESSION", "false")
        assert FeatureFlag.is_auto_session_enabled() is False

    def test_env_enable_explicit(self, monkeypatch: pytest.MonkeyPatch):
        """显式设为 true 返回 True。"""
        monkeypatch.setenv("PRAXIS_AUTO_SESSION", "1")
        assert FeatureFlag.is_auto_session_enabled() is True


# ── 场景8：环境变量恢复后幂等性 ────────────────────────────────────


class TestIdempotency:
    """monkeypatch 前后状态隔离。"""

    def test_is_enabled_idempotent(self):
        """同一开关两次调用结果一致。"""
        v1 = FeatureFlag.is_enabled("PRAXIS_AGENT_MODE")
        v2 = FeatureFlag.is_enabled("PRAXIS_AGENT_MODE")
        assert v1 == v2

    def test_monkeypatch_isolation(self, monkeypatch: pytest.MonkeyPatch):
        """monkeypatch 不影响后续测试的默认值。"""
        # Before
        assert FeatureFlag.is_enabled("PRAXIS_AGENT_MODE") is True
        # During
        monkeypatch.setenv("PRAXIS_AGENT_MODE", "false")
        assert FeatureFlag.is_enabled("PRAXIS_AGENT_MODE") is False
        # monkeypatch 撤销后由 pytest 自动恢复

    def test_memory_idempotent_after_patch(self, monkeypatch: pytest.MonkeyPatch):
        """PRAXIS_MEMORY_ENABLED 默认 False，patch 后恢复。"""
        assert FeatureFlag.is_enabled("PRAXIS_MEMORY_ENABLED") is False
        monkeypatch.setenv("PRAXIS_MEMORY_ENABLED", "1")
        assert FeatureFlag.is_enabled("PRAXIS_MEMORY_ENABLED") is True

    def test_storage_backend_idempotent(self):
        """storage_backend 两次调用一致。"""
        v1 = FeatureFlag.get_storage_backend()
        v2 = FeatureFlag.get_storage_backend()
        assert v1 == v2 == "jsonl"

    def test_guardrail_idempotent(self):
        """guardrail 两次调用一致。"""
        v1 = FeatureFlag.is_enabled("PRAXIS_GUARDRAIL_ENABLED")
        v2 = FeatureFlag.is_enabled("PRAXIS_GUARDRAIL_ENABLED")
        assert v1 == v2 is True
