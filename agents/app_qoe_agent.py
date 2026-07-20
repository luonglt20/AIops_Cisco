"""
Agent: AppQoEAgent (Application QoE & VoIP Specialist)
Chuyên trách đo lường và đánh giá chất lượng trải nghiệm ứng dụng Web (SaaS)
và các ứng dụng họp trực tuyến / truyền thông VoIP (Webex, Zoom, MS Teams).
"""
import json
from api import llm, meraki
from agents.react_loop import run_react_loop
from agents.system_prompts import get_system_prompt


TOOL_REGISTRY = {
    "get_insight_monitored_media_servers": lambda net_id, serial, org_id: _tool_media_servers(org_id),
    "get_network_insight_app_health": lambda net_id, serial, org_id: _tool_app_health(net_id),
    "get_network_insight_application_health": lambda net_id, serial, org_id: meraki.get_network_insight_application_health(net_id),
    "get_app_specific_health": lambda net_id, serial, org_id: meraki.get_app_specific_health(net_id),
    "get_voip_jitter_stats": lambda net_id, serial, org_id: meraki.get_voip_jitter_stats(org_id),
}


def _tool_media_servers(org_id: str) -> str:
    if not org_id:
        return "Không có org_id."
    try:
        res = meraki.get_insight_monitored_media_servers(org_id)
        if not res:
            return "Không có dữ liệu media server (Webex/Zoom/Teams)."
        return json.dumps(res[:5], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn Media Servers: {e}"


def _tool_app_health(net_id: str) -> str:
    if not net_id:
        return "Không có net_id."
    try:
        res = meraki.get_network_insight_application_health(net_id)
        if not res:
            return "Không có dữ liệu ứng dụng SaaS Insight."
        return json.dumps(res[:5], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn Application Health: {e}"


def analyze_with_llm(state: dict) -> str:
    org_id = state.get("org_id") or state.get("org", {}).get("id", "")
    alert  = state.get("alert_data") or state.get("alert", {})
    serial = state.get("serial") or state.get("resolved_serial", "")
    net_id = state.get("network_id") or state.get("resolved_net_id", "")

    media_data = _tool_media_servers(org_id)
    app_data = _tool_app_health(net_id)

    prompt = f"""Bạn là Tác nhân AI Chuyên gia Chất lượng Trải nghiệm Ứng dụng & VoIP (AppQoEAgent).
Nhiệm vụ: Phân tích chỉ số trải nghiệm ứng dụng SaaS (Office365, Salesforce) và cuộc gọi online (Webex, Zoom, Teams) đối chiếu với sự cố mạng hiện tại.

THÔNG TIN SỰ CỐ:
- Thiết bị: {alert.get('device', 'Unknown')} ({serial})
- Alert: {alert.get('issue', 'Unknown')}

CHỈ SỐ MEDIA SERVERS (VOIP/VIDEO):
{media_data}

CHỈ SỐ SỨC KHỎE ỨNG DỤNG SAAS:
{app_data}

Yêu cầu:
1. Đánh giá xem sự cố có đang làm suy giảm chất lượng cuộc gọi (MOS score, Jitter, Packet Loss) hoặc ứng dụng Web hay không.
2. Đưa ra kết luận ngắn gọn (dưới 4 dòng).
"""
    sys_prompt = get_system_prompt("app_qoe_agent")
    allowed = state.get("allowed_tools", [])
    active_registry = {k: v for k, v in TOOL_REGISTRY.items() if not allowed or k in allowed}

    try:
        final_note = run_react_loop(
            agent_name="app_qoe_agent",
            base_prompt=prompt,
            tool_registry=active_registry,
            tool_args=(net_id, serial, org_id),
            max_iterations=2,
            system_prompt=sys_prompt,
            alert_ctx=alert,
        )
        final_note = final_note or "Ứng dụng SaaS và chất lượng cuộc gọi truyền thông chưa bị tác động tiêu cực."
        state.setdefault("blackboard", {})["app_qoe_agent"] = final_note
        print(f"[AppQoEAgent] Diagnosis generated (length={len(final_note)})")
        return final_note
    except Exception as e:
        print(f"[AppQoEAgent] Error: {e}")
        fallback = "Chưa ghi nhận suy hao trải nghiệm ứng dụng SaaS / cuộc họp online."
        state.setdefault("blackboard", {})["app_qoe_agent"] = fallback
        return fallback
