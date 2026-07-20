"""
Agent: DeviceIntel (v5.1 — Real AI-Driven Telemetry Analyzer + Expert Persona)
Phân tích trạng thái thiết bị bằng cách đối chiếu trực tiếp dữ liệu JSON thô (raw telemetry)
với tài liệu tham chiếu kỹ thuật (first-principles domain guide).
Không sử dụng bộ luật cứng Python.
"""
import json
from api import llm, meraki
from agents.react_loop import run_react_loop
from agents.domain_knowledge import get_firmware_note, get_model_specs, get_all_cascade_signatures
from agents.system_prompts import get_system_prompt

TOOL_REGISTRY = {
    "get_switch_port_statuses":                  lambda serial, net_id: _tool_switch_ports(serial),
    "get_wireless_rf":                           lambda serial, net_id: _tool_wireless_rf(serial),
    "run_ping_test":                             lambda serial, net_id: _tool_ping_test(serial),
    "get_arp_table":                             lambda serial, net_id: _tool_arp_table(serial),
    "get_cable_test":                           lambda serial, net_id: _tool_cable_test(serial),
    "get_device_switch_ports_statuses_packets": lambda serial, net_id: _tool_port_packets(serial),
    "get_device_lldp_cdp":                      lambda serial, net_id: _tool_lldp_cdp(serial),
    "get_top_devices_by_energy":                 lambda serial, net_id: meraki.get_top_devices_by_energy(serial),
    "get_device_detail":                         lambda serial, net_id: meraki.get_device_detail(serial),
    "get_device_statuses":                       lambda serial, net_id: meraki.get_device_statuses(serial),
    "get_network_device_list":                   lambda serial, net_id: meraki.get_network_device_list(net_id),
    "reboot_device":                             lambda serial, net_id: meraki.reboot_device(serial),
    "blink_device_leds":                         lambda serial, net_id: meraki.blink_device_leds(serial),
}


def _tool_port_packets(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        res = meraki.get_device_switch_ports_statuses_packets(serial)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn switch port packets: {e}"


def _tool_lldp_cdp(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        res = meraki.get_device_lldp_cdp(serial)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn LLDP/CDP: {e}"


def _tool_switch_ports(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        ports = meraki.get_switch_port_statuses(serial)
        if not ports:
            return "Dữ liệu switch ports rỗng."
        return json.dumps(ports[:8], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn switch ports: {e}"


def _tool_wireless_rf(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        rf = meraki.get_device_wireless_rf(serial)
        if not rf:
            return "Dữ liệu wireless RF rỗng."
        return json.dumps(rf, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn wireless RF: {e}"


def _tool_ping_test(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        res = meraki.run_ping_test(serial, target="8.8.8.8")
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi gọi live tool ping: {e}"


def _tool_arp_table(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        res = meraki.get_arp_table(serial)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi gọi live tool ARP Table: {e}"


def _tool_cable_test(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        res = meraki.get_cable_test(serial, ports=["12"])
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi gọi live tool Cable Test: {e}"


def run(state: dict) -> dict:
    """Resolve serial and networkId from org cache."""
    alert    = state["alert"]
    org_data = state["org"]
    serial   = alert.get("serial", "") or ""
    net_id   = alert.get("networkId", "") or ""
    dev_name = alert.get("device", "")

    devices = org_data.get("devices", {}).get("list", [])
    dev_info = next(
        (d for d in devices if
            (serial and d.get("serial") == serial) or
            (dev_name and d.get("name") == dev_name)),
        {}
    )
    if not dev_info and devices:
        dev_info = devices[0]

    state["device_detail"] = dict(dev_info)

    if not serial and dev_info.get("serial"):
        serial = dev_info["serial"]
    if not net_id and dev_info.get("networkId"):
        net_id = dev_info["networkId"]

    # Enrich alert dict directly to ensure downstream consistency
    if not alert.get("device") and dev_info.get("name"):
        alert["device"] = dev_info["name"]
    if not alert.get("model") and dev_info.get("model"):
        alert["model"] = dev_info["model"]
    if not alert.get("serial") and dev_info.get("serial"):
        alert["serial"] = dev_info["serial"]
    if not alert.get("networkId") and dev_info.get("networkId"):
        alert["networkId"] = dev_info["networkId"]

    state["resolved_serial"] = serial
    state["resolved_net_id"] = net_id
    return state


def analyze_with_llm(state: dict) -> str:
    dev       = state.get("device_detail", {})
    alert     = state.get("alert", {})
    serial    = state.get("resolved_serial", "")
    net_id    = state.get("resolved_net_id", "")
    telemetry = state.get("telemetry", {})

    model     = dev.get("model") or alert.get("model") or ""
    if not isinstance(model, str):
        model = str(model)
    firmware  = dev.get("firmware") or ""
    alert_t   = alert.get("issue", "")
    severity  = alert.get("severity", "MEDIUM")

    # Domain Guide Injection
    model_spec = get_model_specs(model)
    fw_note    = get_firmware_note(firmware)

    poe_guide = ""
    if model_spec and model_spec.get("poe_required"):
        poe_guide = f"- Tiêu chuẩn PoE thiết bị {model} yêu cầu: {model_spec['poe_required']}. LƯU Ý: {model_spec.get('notes','')}"

    cascade_context = get_all_cascade_signatures()

    base_prompt = f"""Bạn là Kỹ sư mạng Cisco Meraki cấp cao (Senior Network Architect).
Nhiệm vụ: Chẩn đoán sự cố thiết bị dựa trên DỮ LIỆU TELEMETRY THÔ (Raw JSON).

== THÔNG SỐ THIẾT BỊ & CẢNH BÁO ==
- Thiết bị: {dev.get('name', 'Unknown')} ({model})
- Serial: {serial or 'Chưa rõ'}
- IP: {dev.get('lanIp') or dev.get('publicIp', 'N/A')}
- Trạng thái hiện tại: {dev.get('status', 'offline')}
- Cảnh báo nhận được: {alert_t} ({severity})

== TÀI LIỆU THAM CHIếU KỸ THUỮT (First-Principles Guide) ==
- Cổng Switch đàm phán tốc độ (negotiated speed): Phải là "1 Gbps" hoặc cao hơn. Nếu ghi nhận "100 Mbps" hoặc "10 Mbps" ở các cổng uplink chính -> 100% lỗi cáp vật lý (bad RJ45 connector/cable degradation).
- PoE Power Allocation:
  {poe_guide or f"- Đối chiếu tiêu chuẩn nguồn cấp PoE với model {model}."}
  Nếu switch port cung cấp không đủ công suất (ví dụ: switch cấp PoE thường 802.3af 15.4W nhưng AP yêu cầu PoE+ 802.3at 30W) -> AP sẽ bị crash và khởi động lại liên tục (watchdog reboot loop).
- RF Noise & Utilization: Ngưỡng nhiễu nền (noise floor) lý tưởng phải dưới -85dBm. Tải kênh (utilization) >70% biểu thị nghữn kênh nghiêm trọng.
{f'- Firmware warning: {fw_note}' if fw_note else ''}

== DỮ LIỆU GIÁM SÁT THÔ (RAW TELEMETRY JSON) ==
{json.dumps(telemetry, indent=2, ensure_ascii=False)}

== MỌ NHẬN BIếT FAILURE CASCADE ==
{cascade_context[:800]}

== TOOLS KHẢ DỤNG CHO REACT ==
- Action: get_switch_port_statuses -> Xem thông số chi tiết nguồn PoE và speed các cổng switch
- Action: get_wireless_rf          -> Xem thông số nhiễu sóng và channel utilization
- Action: run_ping_test            -> Live Tool Ping kiểm tra tỷ lệ loss/latency đến 8.8.8.8
- Action: get_arp_table            -> Live Tool ARP Table xem kết nối IP/MAC
- Action: get_cable_test          -> Live Tool Cable Test đo đứt cáp/ngắn mạch RJ45

== MA TRẬN QUYẾT ĐỊNH GỌI TOOL BẮT BUỘC (TOOL CALLING DECISION MATRIX) ==
1. TRƯỜNG HỢP 1: Cảnh báo thiết bị reboot/alerting hoặc nguồn PoE bất thường:
   -> BẮT BUỘC viết "Action: get_switch_port_statuses" để kiểm tra công suất W cổng 12.
   -> Tiếp theo BẮT BUỘC viết "Action: run_ping_test" để đo tỷ lệ mất gói thời gian thực.
2. TRƯỜNG HỢP 2: Cảnh báo suy hao cổng/speed = 100Mbps hoặc port flapping:
   -> BẮT BUỘC viết "Action: get_cable_test" để kiểm tra đo cáp vật lý.
3. TRƯỜNG HỢP 3: Cảnh báo ngắt kết nối không nhận IP / DHCP failure:
   -> Gọi "Action: get_arp_table" để đọc bảng ARP.
4. TRƯỜNG HỢP 4: Cảnh báo nhiễu sóng Wi-Fi:
   -> Gọi "Action: get_wireless_rf" để kiểm tra noise floor.

BẮT BUỘC chọn đúng Tool theo Ma trận trên dựa vào hiện trạng telemetry thô. Kết quả thu được từ Tool (Observation) PHẢI được đưa trực tiếp làm bằng chứng kỹ thuật và trình bày dưới dạng gạch đầu dòng ngắn gọn (bullet points). KHÔNG ĐƯA RA KẾT LUẬN. CHỈ LIỆT KÊ RAW DATA. KHÔNG viết văn xuôi dài dòng. KHÔNG chào hỏi, KHÔNG kính ngữ, KHÔNG ghi 'Action:' ở cuối bài."""

    device_intel_sys = get_system_prompt("device_intel")
    allowed = state.get("allowed_tools", [])
    active_registry = {k: v for k, v in TOOL_REGISTRY.items() if not allowed or k in allowed}

    final_note = run_react_loop(
        agent_name="DeviceIntel",
        base_prompt=base_prompt,
        tool_registry=active_registry,
        tool_args=(serial, net_id),
        max_iterations=2,
        system_prompt=device_intel_sys,
        alert_ctx=state.get("alert", {}),
    )

    state.setdefault("blackboard", {})["device_intel"] = final_note
    print(f"[DeviceIntel v5.0] Diagnosis generated (length={len(final_note)})")
    return final_note
