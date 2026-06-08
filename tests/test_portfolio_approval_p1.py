"""P1 - 组合配置更新变更申请与审批写入流程集成测试"""
import pytest
import tempfile
import json
import yaml
from pathlib import Path
from praxis.tools.strategy import update_portfolio, approve_portfolio_update


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. 创建投资者与组合配置目录及文件
        port_dir = tmp_path / "investors" / "example" / "portfolios" / "demo"
        port_dir.mkdir(parents=True)
        with open(port_dir / "portfolio.yaml", "w", encoding="utf-8") as f:
            f.write("""
portfolio:
  strategy_type: "grid_value"
  strategy_template: "grid_value"
  created_at: "2026-05-18"
  version: "v1.0"
  description: "Initial description"
""")
            
        yield tmp_path


def test_portfolio_update_and_approval_flow(temp_workspace):
    """测试 update_portfolio 生成提案，并由 approve_portfolio_update 校验写入 YAML 文件"""
    
    # 1. 发起描述更新提案
    new_desc = "Updated description via MCP tool"
    res_prep = update_portfolio(
        investor="example",
        portfolio="demo",
        field="description",
        value=new_desc,
        workspace=str(temp_workspace)
    )
    
    assert res_prep["success"] is True
    data_prep = res_prep["data"]
    assert data_prep["status"] == "pending_approval"
    proposal_id = data_prep["proposal_id"]
    assert "port-update-example-demo-description" in proposal_id
    
    # 2. 检查提案是否持久化在 portfolio_updates.json
    updates_path = temp_workspace / "data" / "portfolio_updates.json"
    assert updates_path.exists()
    with open(updates_path, "r", encoding="utf-8") as f:
        updates = json.load(f)
    assert proposal_id in updates
    assert updates[proposal_id]["new_value"] == new_desc
    
    # 3. 用错误的审批值尝试批准，应当失败
    res_app_fail = approve_portfolio_update(
        investor="example",
        portfolio="demo",
        field="description",
        value="Mismatched value",
        workspace=str(temp_workspace)
    )
    assert res_app_fail["success"] is False
    assert "审批内容不匹配" in res_app_fail["error"]
    
    # 4. 用正确的审批值批准，期望成功
    res_app_success = approve_portfolio_update(
        investor="example",
        portfolio="demo",
        field="description",
        value=new_desc,
        workspace=str(temp_workspace)
    )
    assert res_app_success["success"] is True
    
    # 5. 验证 YAML 文件内容是否被真实更改
    yaml_path = temp_workspace / "investors" / "example" / "portfolios" / "demo" / "portfolio.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    assert config_data["portfolio"]["description"] == new_desc
    
    # 6. 验证已通过的提案被清除
    with open(updates_path, "r", encoding="utf-8") as f:
        updates_after = json.load(f)
    assert proposal_id not in updates_after
