"""
Agent: ClientAgent (v5.1 — Real AI-Driven Client Impact Analyzer + Expert Persona)
Phân tích tác động người dùng dựa trên danh sách clients thực tế trả về từ Meraki API.
Không sử dụng bộ luật cứng Python.
"""
import json
from api import llm, meraki
from agents.react_loop import run_react_loop
from agents.system_prompts import get_system_prompt


TOOL_REGISTRY = {
    "get_network_clients":           lambda net_id: _tool_network_clients(net_id),
    "get_wireless_connection_stats": lambda net_id: _tool_wireless_connection_stats(net_id),
    "get_top_bandwidth_hogs":        lambda net_id: meraki.get_top_bandwidth_hogs(net_id),
    "send_wake_on_lan":              lambda net_id, mac="": meraki.send_wake_on_lan(net_id, mac),
}


def _tool_network_clients(net_id: str) -> str:
    if not net_id:
        return "Không có net_id."
    try:
        cls = meraki.get_network_clients(net_id, timespan=3600)[:20]
        if not cls:
            return "Không tìm thấy clients nào."
        return json.dumps([
            {
                "mac": c.get("mac"), 
                "ip": c.get("ip"), 
                "status": c.get("status"), 
                "ssid": c.get("ssid"),
                "rssi": c.get("rssi") or -65,
                "usage": c.get("usage") or {}
            }
            for c in cls
        ], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn clients: {e}"


def _tool_wireless_connection_stats(net_id: str) -> str:
    if not net_id:
        return "Không có net_id."
    try:
        stats = meraki.get_wireless_connection_stats(net_id, timespan=3600)
        if not stats:
            return "Dữ liệu connection stats rỗng."
        return json.dumps(stats, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn wireless connection stats: {e}"


def run(state: dict) -> dict:
    """Fetch raw network clients for diagnostic context."""
    net_id = state.get("resolved_net_id", "")
    clients = []

    if net_id and net_id != "UNKNOWN_NETID":
        try:
            # Fetch last 30 clients to prevent payload bloat
            clients = meraki.get_network_clients(net_id, timespan=3600)[:30]
        except Exception as e:
            print(f"[ClientAgent v5.0] API fetch failed: {e}")

    state["clients"] = clients
    return state


def analyze_with_llm(state: dict) -> str:
    alert      = state.get("alert", {})
    org        = state.get("org", {})
    clients    = state.get("clients", [])
    serial     = state.get("resolved_serial", "")
    net_id     = state.get("resolved_net_id", "")
    blackboard = state.get("blackboard", {})

    # Extract clean list of clients for the prompt
    clean_clients = []
    online_count = 0
    offline_count = 0
    
    for c in clients:
        status = c.get("status", "Offline")
        if status == "Online":
            online_count += 1
        else:
            offline_count += 1
        
        # Only extract fields useful for reasoning
        clean_clients.append({
            "mac": c.get("mac"),
            "ip": c.get("ip"),
            "os": c.get("os"),
            "status": status,
            "recentDeviceSerial": c.get("recentDeviceSerial"),
            "ssid": c.get("ssid"),
            "vlan": c.get("vlan"),
        })

    clients_json = json.dumps(clean_clients[:15], indent=2, ensure_ascii=False) if clean_clients else "Không tìm thấy client nào."

    # Compute quick network baseline counts
    devices = org.get("devices", {}).get("list", [])
    net_devices = [d for d in devices if d.get("networkId") == net_id]
    alerting_net = len([d for d in net_devices if d.get("status") == "alerting"])

    bb_ctx = ""
    if blackboard:
        bb_ctx = "\n== BLACKBOARD CONTEXT ==\n" + "\n".join([f"- {k}: {v[:120]}" for k, v in blackboard.items()])

    base_prompt = f"""Bạn là Kỹ sư đánh giá tác động dịch vụ mạng (Client Impact Analyst).
Nhiệm vụ: Phân tích danh sách máy khách thực tế và xác định quy mô ảnh hưởng.

== TOOLS KHẢ DỤNG CHO REACT ==
- Action: get_network_clients           -> Truy vấn chi tiết danh sách máy khách trong mạng chi nhánh
- Action: get_wireless_connection_stats -> Truy vấn thống kê thất bại kết nối Wi-Fi (assoc, auth, dhcp, dns)

== MA TRẬN QUYẾT ĐỊNH GỌI TOOL BẮT BUỘC ==
1. Nếu nghi ngờ lỗi kết nối vô tuyến, lỗi đăng nhập WPA hoặc lỗi cấp IP DHCP:
   -> BẮT BUỘC viết "Action: get_wireless_connection_stats" để đo tỷ lệ thất bại của từng công đoạn onboarding.
2. Nếu nghi ngờ quy mô ảnh hưởng người dùng diện rộng:
   -> BẮT BUỘC viết "Action: get_network_clients" để đếm số máy khách offline thực tế.

== THÔNG SỐ SỰ CỐ ==
- Thiết bị báo động: {alert.get('device','AP')} (Serial: {serial})
- Sự cố: {alert.get('issue','?')}
 
== THỐNG KÊ CHI NHÁNH ==
- Tổng thiết bị trong nhánh: {len(net_devices)}
- Số thiết bị đang lỗi/alerting: {alerting_net}
- Số lượng máy khách ghi nhận trực tiếp (trong 1h): {len(clients)} (Đang online: {online_count}, Offline: {offline_count})
 
== DANH SÁCH MÁY KHÁCH THỰC TẾ (RAW CLIENT DATA JSON) ==
{clients_json}
{bb_ctx}
 
== CẨN THẬN: NGUYÊN TẮC TRUNG THỰC DỮ LIỆU ==
1. Tuyệt đối không tự suy diễn số lượng client bị ảnh hưởng nếu dữ liệu thực tế ghi nhận 0 clients offline hoặc không có clients.
2. Nếu danh sách client ghi nhận trạng thái hoạt động bình thường, hãy kết luận: *"Không phát hiện tác động gián đoạn người dùng thực tế tại thời điểm này."*
3. Nếu phát hiện một tệp khách hàng cụ thể bị lỗi (ví dụ: các thiết bị trên cùng một SSID hoặc cùng một VLAN), hãy chỉ ra sự tương quan kỹ thuật (như lỗi cấu hình VLAN, lỗi DHCP pool trên VLAN đó).
NHIỆM VỤ: Trình bày gạch đầu dòng ngắn gọn (bullet points) tóm tắt số liệu thô (CHỈ RAW DATA, KHÔNG ĐƯA RA KẾT LUẬN, KHÔNG VIẾT VĂN XUÔI DÀI DÒNG):
- Đưa ra con số cụ thể (số client online/offline, tỷ lệ rớt mạng).
- Tác động vận hành kinh doanh thực tế.
- Khuyến nghị thời hạn xử lý (SLA) và bước khoanh vùng xử lý kế tiếp.
KHÔNG chào hỏi, KHÔNG dùng kính ngữ, KHÔNG thêm 'Action:' ở cuối."""

    client_sys = get_system_prompt("client_agent")
    final_note = run_react_loop(
        agent_name="ClientAgent",
        base_prompt=base_prompt,
        tool_registry=TOOL_REGISTRY,
        tool_args=(net_id,),
        max_iterations=2,
        system_prompt=client_sys,
        alert_ctx=state.get("alert", {}),
    )

    state.setdefault("blackboard", {})["client_agent"] = final_note
    print(f"[ClientAgent v5.1] Analysis generated (length={len(final_note)})")
    return final_note
