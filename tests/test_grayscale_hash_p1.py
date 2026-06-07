"""P1 - 策略灰度审核哈希校验与安全限制测试"""
import pytest
import tempfile
import json
from pathlib import Path
from praxis.tools.grayscale import prepare_grayscale, approve_grayscale


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 创建 strategies 目录以及 mock 策略文件
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir(parents=True)
        with open(strategies_dir / "grid_value.yaml", "w", encoding="utf-8") as f:
            f.write("initial: true")
            
        yield tmp_path


def test_grayscale_hash_validation(temp_workspace):
    """测试灰度发布过程中的哈希对比校验，确保审批与准备内容完全一致"""
    proposed_content = "version: v1.1.0\nupdated: true"
    
    # 1. 准备灰度，记录待审批哈希
    prep_result = prepare_grayscale(
        strategy_name="grid_value",
        change_description="更新策略参数",
        risk_level="low",
        new_content=proposed_content,
        workspace=str(temp_workspace)
    )
    
    assert prep_result["success"] is True
    backup_path = prep_result["data"]["backup_path"]
    assert backup_path != ""
    
    # 验证 proposals 文件是否写入了对应哈希
    proposals_path = temp_workspace / "data" / "grayscale_proposals.json"
    assert proposals_path.exists()
    with open(proposals_path, "r", encoding="utf-8") as f:
        proposals = json.load(f)
    assert backup_path in proposals
    
    # 2. 尝试用被篡改的 content 审核通过，期望失败
    malicious_content = "version: v1.1.0\nupdated: true\nmalicious_injected: true"
    app_fail = approve_grayscale(
        strategy_name="grid_value",
        backup_path=backup_path,
        new_content=malicious_content,
        workspace=str(temp_workspace)
    )
    assert app_fail["success"] is False
    assert "哈希校验失败" in app_fail["error"]
    
    # 3. 用原本准备的 content 审核通过，期望成功
    app_success = approve_grayscale(
        strategy_name="grid_value",
        backup_path=backup_path,
        new_content=proposed_content,
        workspace=str(temp_workspace)
    )
    assert app_success["success"] is True
    
    # 验证最终文件已修改
    strategy_path = temp_workspace / "strategies" / "grid_value.yaml"
    assert strategy_path.read_text(encoding="utf-8") == proposed_content
