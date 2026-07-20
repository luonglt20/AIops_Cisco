"""
Agent: security_airmarshal_agent
"""
import json
from api import llm, meraki
from agents.react_loop import run_react_loop
from agents.system_prompts import get_system_prompt

TOOL_REGISTRY = {
    "get_network_events": lambda net_id, serial: meraki.get_network_events(net_id, serial=serial),
    "get_device_wireless_rf": lambda net_id, serial: meraki.get_device_wireless_rf(serial),
    "get_wireless_connection_stats": lambda net_id, serial: meraki.get_wireless_connection_stats(net_id),
    "get_switch_port_statuses": lambda net_id, serial: meraki.get_switch_port_statuses(serial),
    "get_appliance_uplinks": lambda net_id, serial: meraki.get_appliance_uplinks(net_id),
    "get_network_clients": lambda net_id, serial: meraki.get_network_clients(net_id),
    "get_network_air_marshal": lambda net_id, serial: meraki.get_network_air_marshal(net_id),
    "get_sensor_readings": lambda net_id, serial: meraki.get_sensor_readings(net_id),
    "get_network_firmware_upgrades": lambda net_id, serial: meraki.get_network_firmware_upgrades(net_id),
    "get_device_loss_latency": lambda net_id, serial: meraki.get_device_loss_latency(serial),
    "get_uplink_loss_latency": lambda net_id, serial: meraki.get_uplink_loss_latency(net_id),
    "run_ping_test": lambda net_id, serial: meraki.run_ping_test(serial),
    "run_throughput_test": lambda net_id, serial: meraki.run_throughput_test(serial),
    "get_cable_test": lambda net_id, serial: meraki.get_cable_test(serial),
    "get_arp_table": lambda net_id, serial: meraki.get_arp_table(serial),
    "get_device_switch_ports_statuses_packets": lambda net_id, serial: meraki.get_device_switch_ports_statuses_packets(serial),
    "get_device_lldp_cdp": lambda net_id, serial: meraki.get_device_lldp_cdp(serial),
    "get_network_channel_utilization": lambda net_id, serial: meraki.get_network_channel_utilization(net_id),
    "get_wireless_client_connection_stats": lambda net_id, serial: meraki.get_wireless_client_connection_stats(net_id),
    "quarantine_malicious_client": lambda net_id, serial: meraki.quarantine_malicious_client(net_id, serial),
    "get_content_filtering_rules": lambda net_id, serial: meraki.get_content_filtering_rules(net_id)
}

def run(state: dict) -> dict:
    """Khởi tạo dữ liệu cơ bản nếu cần."""
    return state

def analyze_with_llm(state: dict) -> str:
    alert      = state.get("alert", {})
    serial     = state.get("resolved_serial", "")
    net_id     = state.get("resolved_net_id", "")
    org_id     = state.get("org", {}).get("id", "")
    
    base_prompt = f"""Bạn là security_airmarshal_agent. Nhiệm vụ của bạn là thu thập thông tin thô bằng tools dựa trên yêu cầu từ alert.
    
== THÔNG TIN THIẾT BỊ ==
- Thiết bị: {alert.get('device','?')} ({alert.get('model','?')})
- Serial: {serial}
- Network ID: {net_id}
- Alert: {alert.get('issue','?')}

NHIỆM VỤ: Hãy liệt kê các thông số kỹ thuật (metrics) và bằng chứng thô (raw evidence) chính xác thu thập được từ hệ thống bằng cách gọi tool. 
BẮT BUỘC liệt kê rõ số liệu (VD: độ trễ 12ms, packet loss 5%, nhiệt độ 40C, CRC error 10, v.v.).
KHÔNG TỰ ĐƯA RA KẾT LUẬN CHẨN ĐOÁN!
"""

    system_prompt = get_system_prompt("security_airmarshal_agent")
    allowed = state.get("allowed_tools", [])
    # Chỉ cung cấp cho agent những tools mà Coordinator cho phép dựa vào usecase
    active_registry = {k: v for k, v in TOOL_REGISTRY.items() if not allowed or k in allowed}

    final_note = run_react_loop(
        agent_name="security_airmarshal_agent",
        base_prompt=base_prompt,
        tool_registry=active_registry,
        tool_args=(net_id, serial),
        max_iterations=2,
        system_prompt=system_prompt,
        alert_ctx=alert,
    )

    state.setdefault("blackboard", {})["security_airmarshal_agent"] = final_note
    print(f"[security_airmarshal_agent] Diagnosis generated (length={len(final_note)})")
    return final_note
