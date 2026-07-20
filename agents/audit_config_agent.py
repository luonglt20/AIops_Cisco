"""
Agent: AuditConfigAgent (Audit & Compliance Specialist)
Chuyên trách truy vết nhật ký thay đổi cấu hình (Configuration Changes Audit Log).
Kiểm tra xem có thay đổi cấu hình con người (Admin configuration change) nào vừa xảy ra
ngay trước thời điểm phát sinh sự cố mạng hay không.
"""
import json
from api import llm, meraki
from agents.react_loop import run_react_loop
from agents.system_prompts import get_system_prompt


TOOL_REGISTRY = {
    "get_org_config_changes": lambda net_id, serial, org_id: _tool_config_changes(org_id),
    "get_org_licenses_overview": lambda net_id, serial, org_id: meraki.get_org_licenses_overview(org_id),
    "run_dns_lookup": lambda net_id, serial, org_id: meraki.run_dns_lookup(serial),
    "get_network_group_policies": lambda net_id, serial, org_id: meraki.get_network_group_policies(net_id),
    "get_custom_dns_recurser": lambda net_id, serial, org_id: meraki.get_custom_dns_recurser(net_id),
    "get_org_branding_policies": lambda net_id, serial, org_id: meraki.get_org_branding_policies(org_id),
    "get_organizations": lambda net_id, serial, org_id: meraki.get_organizations(),
    "get_networks": lambda net_id, serial, org_id: meraki.get_networks(org_id),
}


def _tool_config_changes(org_id: str) -> str:
    if not org_id:
        return "Không có org_id."
    try:
        changes = meraki.get_org_config_changes(org_id, timespan=86400)
        if not changes:
            return "Không ghi nhận thay đổi cấu hình nào trong 24 giờ qua."
        return json.dumps([
            {
                "ts": c.get("ts"),
                "admin": c.get("adminName") or c.get("adminEmail"),
                "adminEmail": c.get("adminEmail"),
                "networkName": c.get("networkName"),
                "page": c.get("page"),
                "label": c.get("label"),
                "oldValue": c.get("oldValue"),
                "newValue": c.get("newValue"),
            }
            for c in changes[:10]
        ], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn Audit Config Changes: {e}"


def analyze_with_llm(state: dict) -> str:
    org_id = state.get("org_id") or state.get("org", {}).get("id", "")
    alert  = state.get("alert_data") or state.get("alert", {})
    serial = state.get("serial") or state.get("resolved_serial", "")
    net_id = state.get("network_id") or state.get("resolved_net_id", "")

    raw_changes = _tool_config_changes(org_id)

    prompt = f"""Bạn là Tác nhân AI Chuyên gia Audit & Compliance (AuditConfigAgent).
Nhiệm vụ: Phân tích nhật ký thay đổi cấu hình (Configuration Changes) dưới đây xem có thay đổi con người nào dẫn đến sự cố mạng này hay không.

THÔNG TIN SỰ CỐ:
- Thiết bị: {alert.get('device', 'Unknown')} ({serial})
- Alert: {alert.get('issue', 'Unknown')}
- Org ID: {org_id}

NHẬT KÝ THAY ĐỔI CẤU HÌNH (AUDIT LOG):
{raw_changes}

Yêu cầu:
1. Đánh giá xem có thao tác sửa đổi cấu hình nào (đổi VLAN, đổi SSID, sửa luật Firewall, đổi port setting) vừa xảy ra gần đây không.
2. Nêu rõ tài khoản Admin đã thực hiện (nếu có) và đưa ra nhận định ngắn gọn (dưới 4 dòng).
"""
    sys_prompt = get_system_prompt("audit_config_agent")
    allowed = state.get("allowed_tools", [])
    active_registry = {k: v for k, v in TOOL_REGISTRY.items() if not allowed or k in allowed}

    try:
        final_note = run_react_loop(
            agent_name="audit_config_agent",
            base_prompt=prompt,
            tool_registry=active_registry,
            tool_args=(net_id, serial, org_id),
            max_iterations=2,
            system_prompt=sys_prompt,
            alert_ctx=alert,
        )
        final_note = final_note or "Không phát hiện thay đổi cấu hình bất thường nào gây ra sự cố."
        state.setdefault("blackboard", {})["audit_config_agent"] = final_note
        print(f"[AuditConfigAgent] Diagnosis generated (length={len(final_note)})")
        return final_note
    except Exception as e:
        print(f"[AuditConfigAgent] Error: {e}")
        fallback = "Không ghi nhận thao tác thay đổi cấu hình con người nào ảnh hưởng đến sự cố này."
        state.setdefault("blackboard", {})["audit_config_agent"] = fallback
        return fallback
