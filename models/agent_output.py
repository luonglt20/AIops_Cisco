"""
MerakiMind — Pydantic Agent Output Models
Schema-validated output cho tất cả AI Agents.
Thay thế hoàn toàn regex parsing không ổn định.
"""
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class AgentDiagnosis(BaseModel):
    """Output schema chuẩn cho mọi diagnostic agent."""
    
    finding: str = Field(
        ...,
        description="Phát hiện kỹ thuật chính, 1-3 câu, tiếng Việt.",
        min_length=10,
    )
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        "MEDIUM",
        description="Mức độ nghiêm trọng của phát hiện.",
    )
    confidence: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của phán đoán, từ 0.0 đến 1.0.",
    )
    action_needed: bool = Field(
        True,
        description="True nếu cần hành động can thiệp ngay.",
    )
    root_cause_hypothesis: Optional[str] = Field(
        None,
        description="Giả thuyết nguyên nhân gốc rễ ngắn gọn.",
    )
    recommended_api_calls: List[str] = Field(
        default_factory=list,
        description="Danh sách Meraki API endpoint nên gọi tiếp theo.",
    )
    similar_case_ids: List[str] = Field(
        default_factory=list,
        description="IDs của các sự cố tương tự được retrieve từ memory.",
    )

    @field_validator("finding")
    @classmethod
    def finding_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("finding không được rỗng.")
        return v.strip()


class CollectorEvidence(BaseModel):
    """Schema chuẩn cho Collector Agents (chỉ thu thập bằng chứng log & telemetry, không kết luận chủ quan)."""
    evidence_type: str = Field(..., description="Loại bằng chứng: RF_LOG, WAN_METRICS, SWITCH_PORT_STATUS, EVENT_LOGS, ONBOARDING_STATS")
    log_entries: List[str] = Field(default_factory=list, description="Danh sách các dòng log và bằng chứng kỹ thuật thu thập được.")
    raw_metrics: dict = Field(default_factory=dict, description="Các thông số đo đạc thô thu thập qua Meraki API.")


class VerificationResult(BaseModel):
    """Output schema cho VerifyAgent."""
    
    passed: bool = Field(..., description="True nếu prompt đạt chất lượng.")
    issues: List[str] = Field(
        default_factory=list,
        description="Danh sách vấn đề cần sửa nếu failed.",
    )
    completeness_score: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Điểm đầy đủ thông tin từ 0.0 đến 1.0.",
    )
    feedback: str = Field("OK", description="Nhận xét tổng quát.")


class ReportOutput(BaseModel):
    """Output schema cho ReportingAgent."""
    
    situation: str = Field(..., description="Tình trạng hiện tại, dễ hiểu.")
    scope: str = Field(..., description="Quy mô ảnh hưởng.")
    cause: str = Field(..., description="Nguyên nhân sơ bộ bằng ngôn ngữ phổ thông.")
    action: str = Field(..., description="Hành động IT đang thực hiện.")
    eta: Optional[str] = Field(None, description="Thời gian ước tính khôi phục.")


def parse_agent_output(raw: str, model_cls: type = AgentDiagnosis) -> BaseModel | None:
    """
    Parse JSON string từ LLM thành Pydantic model.
    Trả về None nếu parse thất bại hoàn toàn.
    """
    import json
    import re

    # Strip markdown code block nếu có
    clean = raw.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0].strip()
    elif "```" in clean:
        clean = clean.split("```")[1].split("```")[0].strip()

    # Try direct JSON parse
    try:
        data = json.loads(clean)
        return model_cls(**data)
    except Exception:
        pass

    # Fallback: extract first JSON object in string
    try:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return model_cls(**data)
    except Exception:
        pass

    return None
