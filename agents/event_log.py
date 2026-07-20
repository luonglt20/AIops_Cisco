"""
Agent: EventLog (v5.0 — Real AI-Driven Event Analyzer)
Phân tích log sự kiện và cảnh báo thô từ Meraki để phát hiện lỗi logic chéo,
đặc biệt là các vòng lặp auth loop, reboot loop, sụt nguồn.
Không sử dụng bộ luật cứng Python.
"""
import json
from api import llm, meraki
from agents.react_loop import run_react_loop
from agents.system_prompts import get_system_prompt


TOOL_REGISTRY = {
    "get_network_events":            lambda net_id, serial: _tool_network_events(net_id, serial),
    "get_network_air_marshal":        lambda net_id, serial: _tool_air_marshal(net_id),
    "get_network_firmware_upgrades":  lambda net_id, serial: _tool_firmware_upgrades(net_id),
    "get_sensor_readings":            lambda net_id, serial: _tool_sensor_readings(net_id),
    "get_webhook_http_servers":       lambda net_id, serial: meraki.get_webhook_http_servers(net_id),
    "get_webhook_delivery_logs":      lambda net_id, serial: meraki.get_webhook_delivery_logs(net_id),
    "get_assurance_alerts":           lambda net_id, serial: meraki.get_assurance_alerts(net_id),
    "get_network_alerts_history":     lambda net_id, serial: meraki.get_network_alerts_history(net_id),
}


def _tool_air_marshal(net_id: str) -> str:
    if not net_id:
        return "Không có net_id."
    try:
        res = meraki.get_network_air_marshal(net_id, timespan=86400)
        return json.dumps(res[:8], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn AirMarshal: {e}"


def _tool_firmware_upgrades(net_id: str) -> str:
    if not net_id:
        return "Không có net_id."
    try:
        res = meraki.get_network_firmware_upgrades(net_id)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn Firmware Upgrades: {e}"


def _tool_sensor_readings(net_id: str) -> str:
    try:
        res = meraki.get_sensor_readings(net_id)
        return json.dumps(res[:8], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn MT Sensors: {e}"


def _tool_network_events(net_id: str, serial: str) -> str:
    if not net_id:
        return "Không có net_id."
    try:
        evts = meraki.get_network_events(net_id, serial=serial, per_page=20)
        if not evts:
            return "Không tìm thấy sự kiện nào cho thiết bị."
        return json.dumps([
            {
                "type": e.get("type"), 
                "occurredAt": e.get("occurredAt"), 
                "description": e.get("description"),
                "clientMac": e.get("clientMac") or e.get("clientIp") or "N/A",
                "deviceSerial": e.get("deviceSerial") or serial or "N/A"
            }
            for e in evts[:10]
        ], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn sự kiện: {e}"


def run(state: dict) -> dict:
    """Fetch raw events from Meraki API for context."""
    net_id = state.get("resolved_net_id", "")
    serial = state.get("resolved_serial", "")
    dev_info = state.get("device_detail", {})
    prod = dev_info.get("productType", "wireless")

    events = []
    if net_id and net_id != "UNKNOWN_NETID":
        try:
            events = meraki.get_network_events(net_id, product_type=prod, serial=serial, per_page=25)
        except Exception as e:
            print(f"[EventLog v5.0] API fetch failed: {e}")

    state["events"] = events
    return state


def analyze_with_llm(state: dict) -> str:
    alert      = state.get("alert", {})
    org        = state.get("org", {})
    events     = state.get("events", [])
    serial     = state.get("resolved_serial", "")
    net_id     = state.get("resolved_net_id", "")
    blackboard = state.get("blackboard", {})

    all_alerts = org.get("alerts", [])
    
    # Pre-render context strings for LLM without making decisions
    alerts_summary = []
    for a in all_alerts:
        if a.get("device") or a.get("serial"):
            alerts_summary.append(f"- Alert: {a.get('device','?')} | Model: {a.get('model','?')} | Issue: {a.get('issue','?')}")
    
    alerts_str = "\n".join(alerts_summary) if alerts_summary else "Không có alert nào khác."

    events_str = ""
    if events:
        events_str = json.dumps([
            {"type": e.get("type"), "occurredAt": e.get("occurredAt"), "description": e.get("description")}
            for e in events[:15]
        ], indent=2, ensure_ascii=False)
    else:
        events_str = "Không tìm thấy dữ liệu nhật ký sự kiện."

    bb_ctx = ""
    if blackboard:
        bb_ctx = "\n== BLACKBOARD CONTEXT ==\n" + "\n".join([f"- {k}: {v[:120]}" for k, v in blackboard.items()])

    base_prompt = f"""Bạn là Kỹ sư mạng phân tích nhật ký sự kiện chuyên sâu của Cisco Meraki (Event Analyst).
Nhiệm vụ: Phân tích log sự kiện và tìm ra quy luật lỗi (patterns) thực tế.

== TOOLS KHẢ DỤNG CHO REACT ==
- Action: get_network_events -> Truy vấn danh sách sự kiện mạng thô bổ sung thời gian thực

== MA TRẬN QUYẾT ĐỊNH GỌI TOOL BẮT BUỘC ==
1. Nếu danh sách sự kiện ban đầu chưa đầy đủ hoặc nghi ngờ có sự kiện lặp lại (reboot/auth loop):
   -> BẮT BUỘC viết "Action: get_network_events" để lọc log sự kiện mới nhất thời gian thực từ Meraki API.

== THÔNG TIN THIẾT BỊ ==
- Thiết bị: {alert.get('device','?')} ({alert.get('model','MR46')})
- Serial: {serial}
- Alert: {alert.get('issue','?')}

== NHẬT KÝ ALERTS TRONG TOÀN ORG ==
{alerts_str}

== NHẬT KÝ SỰ KIỆN CHI TIẾT THÔ (RAW EVENT LOG) ==
{events_str}
{bb_ctx}

== CẨN THẬN: NGUYÊN TẮC TRUNG THỰC DỮ LIỆU ==
1. Không bịa đặt: Chỉ phân tích các sự kiện thực tế có trong danh sách trên hoặc thu được từ tool. 
2. Nếu danh sách sự kiện rỗng hoặc không chứa lỗi (như không có 'wpa_auth_fail', không có 'device_booted'), bạn PHẢI khẳng định không phát hiện bất thường trong event log. Tuyệt đối không tự bịa ra 'reboot loop' hay 'auth loop' khi log trống/bình thường.
3. Nếu phát hiện các sự kiện lặp lại (như nhiều dòng boot liên tục hoặc nhiều dòng auth error), hãy giải thích logic chéo của chúng.
NHIỆM VỤ: Trình bày gạch đầu dòng ngắn gọn (bullet points) tóm tắt số liệu thô (CHỈ RAW DATA, KHÔNG ĐƯA RA KẾT LUẬN, KHÔNG VIẾT VĂN XUÔI DÀI DÒNG):
- Đưa ra con số cụ thể và các ID/MAC liên quan.
- Thống kê tần suất các loại sự kiện (event type) xuất hiện trong log.
- Liệt kê các mốc thời gian xảy ra sự kiện gần nhất hoặc lặp lại nhiều nhất.
KHÔNG chào hỏi, KHÔNG dùng kính ngữ, KHÔNG thêm 'Action:' ở cuối."""

    event_sys = get_system_prompt("event_log")
    allowed = state.get("allowed_tools", [])
    active_registry = {k: v for k, v in TOOL_REGISTRY.items() if not allowed or k in allowed}

    final_note = run_react_loop(
        agent_name="EventLog",
        base_prompt=base_prompt,
        tool_registry=active_registry,
        tool_args=(net_id, serial),
        max_iterations=2,
        system_prompt=event_sys,
        alert_ctx=alert,
    )

    state.setdefault("blackboard", {})["event_log"] = final_note
    print(f"[EventLog v5.0] Diagnosis generated (length={len(final_note)})")
    return final_note
