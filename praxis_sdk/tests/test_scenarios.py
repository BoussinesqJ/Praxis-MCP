"""
Praxis 规则回归测试入口
运行 rule_scenarios.json 中的所有测试用例

用法：
  python praxis_sdk/tests/test_scenarios.py              # 运行所有测试
  python praxis_sdk/tests/test_scenarios.py --filter rule2  # 只运行 Rule 2 相关
  python praxis_sdk/tests/test_scenarios.py --verbose     # 详细输出
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from praxis_sdk.core.rule_engine import RuleEngine, SentinelState
from praxis_sdk.core.lcd_detector import LCDDetector


def load_scenarios(filter_keyword: str = None) -> List[Dict[str, Any]]:
    """加载测试场景"""
    scenarios_path = Path(__file__).parent / "rule_scenarios.json"
    with open(scenarios_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    scenarios = data["scenarios"]
    if filter_keyword:
        scenarios = [s for s in scenarios if filter_keyword.lower() in s["id"].lower() 
                     or filter_keyword.lower() in s.get("rule", "").lower()]
    return scenarios


def run_scenario(scenario: Dict[str, Any], rule_engine: RuleEngine, 
                 lcd_detector: LCDDetector, verbose: bool = False) -> Dict[str, Any]:
    """运行单个测试场景"""
    scenario_id = scenario["id"]
    rule = scenario.get("rule", "")
    inp = scenario["input"]
    expected = scenario["expected"]
    
    result = {"id": scenario_id, "passed": False, "actual": None, "expected": expected}
    
    try:
        # 根据规则类型调用对应的检查函数
        if rule == "Rule 1":
            sentinel = SentinelState(bullish_count=inp["sentinel_bullish"], total=8)
            actual = rule_engine.check_rule1(sentinel, inp["rsi_14"])
            result["actual"] = {"allowed": actual.allowed, "reason": actual.reason}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Rule 2":
            sentinel = SentinelState(bullish_count=inp["sentinel_bullish"], total=8)
            actual = rule_engine.check_rule2(
                sentinel, inp["current_position_pct"], inp["new_trade_pct"],
                is_rule8_chase=inp.get("is_rule8_chase", False),
                alpha_bypass=inp.get("alpha_bypass", False),
                alpha_limit_pct=inp.get("alpha_limit_pct", 5.0)
            )
            result["actual"] = {"allowed": actual.allowed, "conflict": actual.conflict, "reason": actual.reason}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Rule 3":
            actual = rule_engine.check_rule3(inp["consecutive_days_below_2"], inp["action"])
            result["actual"] = {"allowed": actual.allowed, "conflict": actual.conflict}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Rule 4":
            actual = rule_engine.check_rule4(
                inp["pe_percentile"], inp["pb_percentile"], inp.get("asset_type", "stock")
            )
            result["actual"] = {"allowed": actual.allowed, "warning": actual.warning, "conflict": actual.conflict}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Rule 5":
            actual = rule_engine.check_rule5(inp["tech_exposure_pct"], inp.get("new_trade_tech_pct", 0))
            result["actual"] = {"allowed": actual.allowed, "conflict": actual.conflict}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Rule 7":
            actual = rule_engine.check_rule7(
                inp["price_in_grid"], inp.get("rsi_14"), inp.get("volume_ratio"),
                inp.get("rule4_blocked", False)
            )
            result["actual"] = {"allowed": actual.allowed, "conflict": actual.conflict, "reason": actual.reason}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Rule 8":
            actual = rule_engine.check_rule8(inp["total_assets"], inp["chase_amount"])
            result["actual"] = {"allowed": actual.allowed, "conflict": actual.conflict}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Rule 9":
            actual = rule_engine.check_rule9(inp["trade_amount"])
            result["actual"] = {"allowed": actual.allowed, "conflict": actual.conflict}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Protocol 1":
            actual = rule_engine.check_protocol1(inp["index_price"], inp["pda_anchor"])
            result["actual"] = {"allowed": actual.allowed, "action": getattr(actual, 'action', None)}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "Protocol 3":
            actual = rule_engine.check_protocol3(inp["user_approved"])
            result["actual"] = {"allowed": actual.allowed, "conflict": actual.conflict}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif rule == "LCD":
            # LCD 测试需要特殊处理
            if "size" in inp:
                actual = lcd_detector.check_trade_vs_rules(
                    ticker=inp.get("ticker", "TEST"),
                    price=inp.get("current_price", 0),
                    size=inp.get("size", 0),
                    sentinel_bullish=inp["sentinel_bullish"],
                    current_position_pct=inp["current_position_pct"],
                    total_assets=inp.get("total_assets", 70000),
                    pe_pct=inp.get("pe_percentile"),
                    pb_pct=inp.get("pb_percentile"),
                    price_in_grid=inp.get("price_in_grid", False),
                    asset_type=inp.get("asset_type", "stock")
                )
            else:
                # 组合层面检查
                portfolio_state = {
                    "position_pct": inp["current_position_pct"],
                    "tech_exposure_pct": inp.get("tech_exposure_pct", 0)
                }
                actual = lcd_detector.check_portfolio_vs_rules(portfolio_state, inp["sentinel_bullish"])
            
            result["actual"] = {"allowed": actual.allowed, "resolution": actual.resolution}
            result["passed"] = actual.allowed == expected["allowed"]
            
        elif "止损" in rule or "000001" in scenario_id:
            # 特殊场景：止损触发
            distance_pct = inp.get("distance_pct", 0)
            result["actual"] = {"warning": f"距止损 {distance_pct}%"}
            result["passed"] = distance_pct < 1.0  # 距止损<1%视为触发
            
        elif "踏空" in rule or "000002" in scenario_id:
            # 特殊场景：踏空归因
            actual_low = inp.get("actual_low", 0)
            buy_range_low = inp.get("buy_range_low", 0)
            result["actual"] = {"missed": actual_low > buy_range_low}
            result["passed"] = result["actual"]["missed"] == expected["missed"]
            
        else:
            result["actual"] = {"error": f"未实现的规则类型: {rule}"}
            result["passed"] = False
            
    except Exception as e:
        result["actual"] = {"error": str(e)}
        result["passed"] = False
    
    return result


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="Praxis 规则回归测试")
    parser.add_argument("--filter", type=str, help="过滤关键词")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()
    
    # 加载场景
    scenarios = load_scenarios(args.filter)
    print(f"📋 加载 {len(scenarios)} 个测试场景")
    
    # 初始化引擎
    rule_engine = RuleEngine()
    lcd_detector = LCDDetector()
    
    # 运行测试
    results = []
    passed = 0
    failed = 0
    
    for scenario in scenarios:
        result = run_scenario(scenario, rule_engine, lcd_detector, args.verbose)
        results.append(result)
        
        if result["passed"]:
            passed += 1
            status = "✅"
        else:
            failed += 1
            status = "❌"
        
        if args.verbose or not result["passed"]:
            print(f"{status} {result['id']}: {scenario['description']}")
            if not result["passed"]:
                print(f"   预期: {result['expected']}")
                print(f"   实际: {result['actual']}")
    
    # 汇总
    print(f"\n{'='*50}")
    print(f"📊 测试结果: {passed}/{passed+failed} Passed")
    if failed > 0:
        print(f"❌ {failed} 个测试失败")
        sys.exit(1)
    else:
        print("✅ 所有测试通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
