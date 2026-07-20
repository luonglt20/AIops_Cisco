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


from config import to_vn_time

def _tool_config_changes(org_id: str) -> str:
    if not org_id:
        return "Không có org_id."
    try:
        changes = meraki.get_org_config_changes(org_id, timespan=86400)
        if not changes:
            return "Không ghi nhận thay đổi cấu hình nào trong 24 giờ qua."
        
        formatted_logs = []
        for c in changes[:10]:
            ts_raw = c.get("ts", "")
            ts_vn = to_vn_time(ts_raw, "%H:%M:%S") if ts_raw else "N/A"
            admin_name = c.get("adminName") or "Unknown Admin"
            admin_email = c.get("adminEmail") or "N/A"
            network_name = c.get("networkName") or "N/A"
            page = c.get("page") or "N/A"
            label = c.get("label") or "N/A"
            old_val = c.get("oldValue") or "N/A"
            new_val = c.get("newValue") or "N/A"
            
            formatted_logs.append(
                f"• [{ts_vn} (giờ VN)] Admin: {admin_name} ({admin_email}) | Page: '{page}' | Port/Label: '{label}' | Network: '{network_name}'\n"
                f"  Thay đổi: {old_val} ➔ {new_val}"
            )
        return "\n".join(formatted_logs)
    except Exception as e:
        return f"Lỗi truy vấn Audit Config Changes: {e}"


def analyze_with_llm(state: dict) -> str:
    org_id = state.get("org_id") or state.get("org", {}).get("id", "")
    alert  = state.get("alert_data") or state.get("alert", {})
    serial = state.get("serial") or state.get("resolved_serial", "")
    net_id = state.get("network_id") or state.get("resolved_net_id", "")

    raw_changes = _tool_config_changes(org_id)

    prompt = f"""Bạn là Tác nhân AI Chuyên gia Audit & Compliance (AuditConfigAgent).
Nhiệm vụ: Phân tích và trích xuất chi tiết từng sự kiện thay đổi cấu hình (Configuration Changes Audit Log) từ người dùng/Admin dẫn đến sự cố mạng.

THÔNG TIN SỰ CỐ:
- Thiết bị: {alert.get('device', 'Unknown')} ({serial})
- Cảnh báo: {alert.get('issue', 'Unknown')}
- Org ID: {org_id}

NHẬT KÝ THAY ĐỔI CẤU HÌNH THỰC TẾ (AUDIT LOGS - GIỜ VIỆT NAM UTC+7):
{raw_changes}

YÊU CẦU TRÌNH BÀY BẮT BỘC CHI TIẾT (ĐỔI MỐC THỜI GIAN THEO GIỜ VIỆT NAM UTC+7):
1. TRÍCH XUẤT ĐẦY ĐỦ VÀ CHÍNH XÁC TỪNG MỐC THỜI GIAN THEO GIỜ VIỆT NAM (UTC+7):
   - Nêu rõ Thời gian giờ VN, Tên Admin, Email Admin, Tên Cổng/Switch (Label), và giá trị trước/sau (Old Value ➔ New Value).
   - Ví dụ cụ thể: "Lúc 22:44:00 (giờ VN), Admin CMC Duc (thongduc@cmc.com.vn) đã chuyển Cổng SW_Internal / 46 từ Port: enabled ➔ disabled."
2. ĐÁNH GIÁ TÁC ĐỘNG VÀ CHUỖI NGUYÊN NHÂN:
   - Chỉ rõ hành động nào gây ra sự cố (ngắt nguồn PoE/tắt port) và hành động nào là thao tác sửa chữa khôi phục.
3. Giữ định dạng rõ ràng, chuyên nghiệp, liệt kê chính xác các mốc sự kiện thực tế theo giờ Việt Nam.
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
