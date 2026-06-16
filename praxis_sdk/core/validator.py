"""
Praxis v3.0 结构化输出校验器（Schema Validation + 优雅降级）

借鉴 TradingAgents 的 structured.py 模式：
- Pydantic schema 约束核心决策输出
- 校验失败时优雅降级为 Markdown 正则提取
- 拦截点：orchestrator_tool compile_prompt + decision_tool create

设计原则：
- 绝不触碰 Portfolio vault（MCP 工具层不变）
- 在 praxis_sdk 本地库做拦截与校验
- 完全兼容现有的 Rule 28 等铁律
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─── Pydantic Schema 定义 ─────────────────────────────────────

try:
    from pydantic import BaseModel, Field, validator
    from enum import Enum

    class TeamRecommendation(str, Enum):
        """三团队统一推荐等级。"""
        STRONG_BUY = "strong_buy"
        BUY = "buy"
        HOLD = "hold"
        SELL = "sell"
        STRONG_SELL = "strong_sell"

    class ASRGOutput(BaseModel):
        """ASRG 团队输出 schema。"""
        recommendation: TeamRecommendation
        confidence: float = Field(ge=0.0, le=1.0, description="置信度 0-1")
        key_findings: str = Field(min_length=10, description="核心发现")
        logic_strong_validation: bool = Field(default=False, description="是否标注强验证")

    class MastersOutput(BaseModel):
        """Masters 大师圆桌输出 schema。"""
        recommendation: TeamRecommendation
        safety_margin: str = Field(description="安全边际评估")
        philosophical_verdict: str = Field(min_length=10, description="哲学裁决")

    class TradingOutput(BaseModel):
        """Trading 团队输出 schema。"""
        recommendation: TeamRecommendation
        confidence: float = Field(ge=0.0, le=1.0)
        pda_valid: bool = Field(default=False, description="PDA 是否有效")
        entry_price: Optional[float] = None
        stop_loss: Optional[float] = None
        position_sizing: Optional[str] = None

    class DecisionOutput(BaseModel):
        """决策记录输出 schema。"""
        ticker: str
        action: str = Field(description="buy/sell/hold/watch")
        confidence: float = Field(ge=0.0, le=1.0)
        reasoning: str = Field(min_length=10)
        quantity: Optional[float] = None
        price_range: Optional[list] = None

    HAS_PYDANTIC = True

except ImportError:
    HAS_PYDANTIC = False
    logger.warning("pydantic not installed; validator will use regex-only fallback")


# ─── Markdown 正则提取器（降级方案）───────────────────────────

# 推荐等级正则
_RECOMMENDATION_RE = re.compile(
    r"(?:recommendation|建议|评级|评级)[：:\s]*"
    r"(strong\s*(?:buy|sell)|buy|hold|sell)",
    re.IGNORECASE
)

# 置信度正则
_CONFIDENCE_RE = re.compile(
    r"(?:confidence|置信度)[：:\s]*(\d+(?:\.\d+)?)\s*(?:%|/100|/1)?",
    re.IGNORECASE
)

# PDA 有效正则
_PDA_VALID_RE = re.compile(
    r"PDA[：:\s]*(有效|无效|valid|invalid|true|false)",
    re.IGNORECASE
)

# 逻辑强验证正则
_LOGIC_VALIDATION_RE = re.compile(
    r"\[?Logic_Strong_Validation\]?|逻辑强验证",
    re.IGNORECASE
)


@dataclass
class ValidationResult:
    """校验结果。"""
    valid: bool                           # schema 校验是否通过
    data: Optional[Dict[str, Any]] = None # 结构化数据（如果校验通过）
    fallback_used: bool = False           # 是否使用了降级方案
    fallback_data: Optional[Dict[str, Any]] = None  # 降级提取的数据
    errors: list = field(default_factory=list)       # 校验错误信息
    raw_text: str = ""                    # 原始文本


# ─── 核心校验函数 ─────────────────────────────────────────────

def validate_or_fallback(
    text: str,
    schema_type: str = "decision",
) -> ValidationResult:
    """校验结构化输出，失败时降级为正则提取。

    Args:
        text: LLM 输出的原始文本
        schema_type: schema 类型，可选 "asrg" / "masters" / "trading" / "decision"

    Returns:
        ValidationResult 包含校验结果和数据
    """
    result = ValidationResult(valid=False, raw_text=text)

    # Step 1: 尝试 Pydantic schema 校验
    if HAS_PYDANTIC:
        parsed = _try_pydantic_parse(text, schema_type)
        if parsed is not None:
            result.valid = True
            result.data = parsed
            return result
        result.errors.append("Pydantic schema validation failed")

    # Step 2: 降级为正则提取
    fallback = _regex_extract(text, schema_type)
    if fallback:
        result.fallback_used = True
        result.fallback_data = fallback
        logger.info("Validator: used regex fallback for %s", schema_type)
    else:
        result.errors.append("Regex fallback also failed")

    return result


def _try_pydantic_parse(text: str, schema_type: str) -> Optional[Dict[str, Any]]:
    """尝试用 Pydantic schema 解析文本。"""
    if not HAS_PYDANTIC:
        return None

    schema_map = {
        "asrg": ASRGOutput,
        "masters": MastersOutput,
        "trading": TradingOutput,
        "decision": DecisionOutput,
    }

    schema_class = schema_map.get(schema_type)
    if schema_class is None:
        return None

    # 尝试直接解析 JSON（如果 LLM 输出了 JSON）
    try:
        import json
        # 尝试从文本中提取 JSON 块
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            instance = schema_class(**data)
            return instance.model_dump()
    except Exception:
        pass

    # 尝试从 Markdown 中提取字段
    try:
        extracted = _regex_extract(text, schema_type)
        if extracted:
            instance = schema_class(**extracted)
            return instance.model_dump()
    except Exception:
        pass

    return None


def _regex_extract(text: str, schema_type: str) -> Optional[Dict[str, Any]]:
    """从 Markdown 文本中用正则提取关键字段。"""
    result = {}

    # 提取推荐等级
    rec_match = _RECOMMENDATION_RE.search(text)
    if rec_match:
        result["recommendation"] = rec_match.group(1).lower().replace(" ", "_")
    elif "buy" in text.lower():
        result["recommendation"] = "buy"
    elif "sell" in text.lower():
        result["recommendation"] = "sell"
    elif "hold" in text.lower():
        result["recommendation"] = "hold"

    # 提取置信度
    conf_match = _CONFIDENCE_RE.search(text)
    if conf_match:
        val = float(conf_match.group(1))
        result["confidence"] = val / 100 if val > 1 else val

    # 提取逻辑强验证
    if _LOGIC_VALIDATION_RE.search(text):
        result["logic_strong_validation"] = True

    # 提取 PDA 状态
    pda_match = _PDA_VALID_RE.search(text)
    if pda_match:
        result["pda_valid"] = pda_match.group(1).lower() in ("有效", "valid", "true")

    # 根据 schema_type 添加特定字段
    if schema_type == "decision":
        action_match = re.search(r'(buy|sell|hold|watch)', text, re.IGNORECASE)
        if action_match:
            result["action"] = action_match.group(1).lower()
        # 提取 reasoning（取前 500 字符）
        result["reasoning"] = text[:500]

    return result if result else None


# ─── 便捷函数 ─────────────────────────────────────────────

def validate_decision(text: str) -> ValidationResult:
    """校验决策输出（decision_tool create 拦截点）。"""
    return validate_or_fallback(text, "decision")


def validate_team_output(text: str, team: str) -> ValidationResult:
    """校验团队输出（orchestrator_tool compile_prompt 拦截点）。"""
    team_map = {"asrg": "asrg", "masters": "masters", "trading": "trading"}
    return validate_or_fallback(text, team_map.get(team, "trading"))


def get_validator_status() -> dict:
    """返回校验器状态（用于日志和调试）。"""
    return {
        "pydantic_available": HAS_PYDANTIC,
        "schema_types": ["asrg", "masters", "trading", "decision"],
        "fallback_method": "regex",
    }
