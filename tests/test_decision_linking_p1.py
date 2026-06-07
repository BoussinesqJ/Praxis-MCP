"""P1 - 交易与决策关联集成测试"""
import pytest
import tempfile
import json
from pathlib import Path

from praxis.tools.decision import create_decision, get_decision_record
from praxis.tools.ledger import add_transaction, approve_transaction


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        yield tmp_path


def test_decision_transaction_linking_auto_approve(temp_workspace):
    """测试在 auto_approve=True 模式下添加交易，决策记录自动关联并更新状态为 EXECUTED"""
    # 1. 创建决策记录，状态为 PENDING_APPROVAL
    dec_res = create_decision(
        ticker="600995",
        action="buy",
        confidence=0.9,
        reasoning="突破买入",
        workspace=str(temp_workspace)
    )
    assert dec_res["success"] is True
    decision_id = dec_res["data"]["decision_id"]
    
    # 2. 直接以 auto_approve 模式写入交易，并关联该 decision_id
    tx_res = add_transaction(
        ticker="600995",
        action="buy",
        quantity=1000,
        price=10.0,
        decision_id=decision_id,
        auto_approve=True,
        workspace=str(temp_workspace)
    )
    assert tx_res["success"] is True
    tx_id = tx_res["data"]["tx_id"]
    
    # 3. 校验决策记录是否自动更新并关联了交易 ID
    get_res = get_decision_record(decision_id, workspace=str(temp_workspace))
    assert get_res["success"] is True
    decision = get_res["data"]
    assert decision["execution_tx_id"] == tx_id
    assert decision["status"] == "executed"


def test_decision_transaction_linking_on_approve(temp_workspace):
    """测试通过标准审批流程批准交易时，关联决策自动更新并更新状态为 EXECUTED"""
    # 1. 创建决策记录
    dec_res = create_decision(
        ticker="600995",
        action="buy",
        confidence=0.85,
        reasoning="回调买入",
        workspace=str(temp_workspace)
    )
    assert dec_res["success"] is True
    decision_id = dec_res["data"]["decision_id"]
    
    # 2. 创建需审批交易，关联 decision_id
    tx_res = add_transaction(
        ticker="600995",
        action="buy",
        quantity=1000,
        price=10.0,
        decision_id=decision_id,
        auto_approve=False,
        workspace=str(temp_workspace)
    )
    assert tx_res["success"] is True
    pending_tx_id = tx_res["data"]["tx_id"]
    
    # 此时决策记录应该还是 pending_approval 状态，且没有关联交易 ID
    dec_before = get_decision_record(decision_id, workspace=str(temp_workspace))["data"]
    assert dec_before["status"] == "pending_approval"
    assert dec_before["execution_tx_id"] is None
    
    # 3. 审批通过交易
    app_res = approve_transaction(pending_tx_id, workspace=str(temp_workspace))
    assert app_res["success"] is True
    formal_tx_id = app_res["data"]["tx_id"]
    
    # 4. 校验决策记录已更新为 executed 并关联了 formal_tx_id
    dec_after = get_decision_record(decision_id, workspace=str(temp_workspace))["data"]
    assert dec_after["status"] == "executed"
    assert dec_after["execution_tx_id"] == formal_tx_id
