"""P1 - Prompt Composer 与版本管理器集成测试"""
import pytest
import tempfile
from pathlib import Path
from praxis.engine.prompt_composer import PromptComposer
from praxis.engine.prompt_versioning.manager import PromptVersionManager


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. 创建基础 Prompt 目录与文件
        base_dir = tmp_path / "teams" / "base"
        base_dir.mkdir(parents=True)
        with open(base_dir / "base.md", "w", encoding="utf-8") as f:
            f.write("Base system prompt.")
            
        # 2. 创建团队原始 Prompt
        prompts_dir = tmp_path / "teams" / "base_prompts"
        prompts_dir.mkdir(parents=True)
        with open(prompts_dir / "asrg.md", "w", encoding="utf-8") as f:
            f.write("Raw ASRG Prompt.")
            
        yield tmp_path


def test_composer_loads_active_version(temp_workspace):
    """测试 PromptComposer 能正确加载 PromptVersionManager 中的最新活动版本"""
    # 1. 直接用 Composer 拼装，此时应该读取原始文件
    composer = PromptComposer(str(temp_workspace))
    prompt_before = composer.compose(team_name="asrg", strategy_name="grid_value")
    assert "Raw ASRG Prompt." in prompt_before
    
    # 2. 通过 PromptVersionManager 提交一个新版本并自动设为 active
    manager = PromptVersionManager(temp_workspace)
    manager.create_version(
        prompt_name="asrg",
        content="Versioned Active ASRG Prompt Content.",
        description="v1.0.0 init",
        created_by="test_user"
    )
    
    # 3. 再次拼装，期望内容已变更为版本管理库中的 active 内容
    prompt_after = composer.compose(team_name="asrg", strategy_name="grid_value")
    assert "Versioned Active ASRG Prompt Content." in prompt_after
    assert "Raw ASRG Prompt." not in prompt_after
