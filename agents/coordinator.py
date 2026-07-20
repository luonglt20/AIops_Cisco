"""
Agent: Coordinator (Rule-Based Expert Routing v3.2)
Routing thông minh dựa trên alert type + model type + org data.
KHÔNG dùng LLM cho routing nữa — rule-based đơn giản hơn nhưng chính xác hơn.
"""
import json
import re
from api import llm


_ALERT_ROUTING = {
    "device is alerting": {
        "run_device_intel":      True,
        "run_event_log":         True,
        "run_client_agent":      True,
        "run_uplink_agent":      False,  # AP/Switch không phân tích WAN
        "run_audit_config":      True,
        "run_app_qoe":           False,
        "run_correlation_agent": True,
        "plan": "Thiết bị đang alerting — chạy DeviceIntel (firmware/PoE check), EventLog (auth/disconnect patterns), ClientAgent (impact scope), AuditConfigAgent."
    },
    "offline": {
        "run_device_intel":      True,
        "run_event_log":         True,
        "run_client_agent":      False,
        "run_uplink_agent":      True,
        "run_audit_config":      False,
        "run_app_qoe":           False,
        "run_correlation_agent": True,
        "plan": "Thiết bị offline — chạy DeviceIntel + EventLog để xác định điểm mất kết nối, UplinkAgent kiểm tra WAN."
    },
    "unreachable": {
        "run_device_intel":      True,
        "run_event_log":         True,
        "run_client_agent":      False,
        "run_uplink_agent":      True,
        "run_audit_config":      False,
        "run_app_qoe":           False,
        "run_correlation_agent": True,
        "plan": "Thiết bị unreachable — phân tích WAN loss, routing, VLAN config."
    },
    "low_power": {
        "run_device_intel":      True,
        "run_event_log":         False,
        "run_client_agent":      False,
        "run_uplink_agent":      False,
        "run_audit_config":      False,
        "run_app_qoe":           False,
        "run_correlation_agent": False,
        "plan": "Low power alert — chỉ cần DeviceIntel kiểm tra PoE supply từ upstream switch."
    },
    "insight_web_app": {
        "run_device_intel":      False,
        "run_event_log":         False,
        "run_client_agent":      True,
        "run_uplink_agent":      True,
        "run_audit_config":      False,
        "run_app_qoe":           True,
        "run_correlation_agent": True,
        "plan": "Web app performance issue — tập trung AppQoEAgent (Webex/Zoom MOS), UplinkAgent và ClientAgent."
    },
    "uplink": {
        "run_device_intel":      False,
        "run_event_log":         False,
        "run_client_agent":      True,
        "run_uplink_agent":      True,
        "run_audit_config":      False,
        "run_app_qoe":           True,
        "run_correlation_agent": True,
        "plan": "Uplink issue — phân tích WAN quality và tác động người dùng."
    },
    "default": {
        "run_device_intel":      True,
        "run_event_log":         True,
        "run_client_agent":      True,
        "run_uplink_agent":      True,
        "run_audit_config":      True,
        "run_app_qoe":           True,
        "run_correlation_agent": True,
        "plan": "Sự cố không xác định — chạy toàn bộ agents để có đủ context."
    }
}


def run(state: dict) -> dict:
    print("[Coordinator] Analyzing routing strategy...")

    alert   = state.get("alert", {})
    org     = state.get("org", {})
    issue   = (alert.get("issue", "") or "").lower()
    model   = (alert.get("model", "") or "").upper()
    devices = org.get("devices", {}).get("list", [])
    alerts  = org.get("alerts", [])

    # ── Step 1: Match alert type to route ────────────────────────────────────
    route_config = _ALERT_ROUTING["default"]
    matched_key  = "default"

    for key, config in _ALERT_ROUTING.items():
        if key == "default":
            continue
        if key in issue:
            route_config = config
            matched_key  = key
            break

    route = {k: v for k, v in route_config.items() if k.startswith("run_")}
    plan  = route_config["plan"]

    # ── Step 2: Model-based refinement ───────────────────────────────────────
    if model.startswith("MR") or "WIRELESS" in model:
        # AP: WAN analysis không áp dụng trực tiếp
        if matched_key not in ("offline", "unreachable", "insight_web_app", "uplink"):
            route["run_uplink_agent"] = False

    if model.startswith("MX"):
        # MX Appliance: luôn cần UplinkAgent
        route["run_uplink_agent"] = True

    # ── Step 3: Org-wide check — if many devices alerting, maximize agents ──
    other_alerting = [a for a in alerts if a.get("serial") != alert.get("serial")]

    if "diện rộng" in alert.get("issue", "") or len(other_alerting) > 0:
        for key in route:
            route[key] = True
        plan = (
            f"⚠️ PHÁT HIỆN {len(other_alerting)} THIẾT BỊ KHÁC ĐANG ALERT — khả năng sự cố diện rộng. "
            f"Triển khai toàn bộ agents để phân tích toàn diện."
        )

    # ── Step 4: Multi-Agent Classification Engine ──────────────
    if "config" in issue or "change" in issue or "audit" in issue:
        assigned_agent = "audit_config_agent"
        allowed_tools = ["get_org_config_changes"]
    elif "voip" in issue or "media" in issue or "webex" in issue or "zoom" in issue or "qoe" in issue:
        assigned_agent = "app_qoe_agent"
        allowed_tools = ["get_insight_monitored_media_servers", "get_network_insight_app_health"]
    elif "rogue" in issue or "airmarshal" in issue or "security" in issue:
        assigned_agent = "security_airmarshal_agent"
        allowed_tools = [
            "get_network_air_marshal",
            "get_device_wireless_rf",
            "get_network_events"
        ]
    elif "firmware" in issue or "reboot" in issue or "crash" in issue:
        assigned_agent = "firmware_crash_agent"
        allowed_tools = [
            "get_network_firmware_upgrades",
            "get_device_detail",
            "get_network_events"
        ]
    elif "unreachable" in issue or "offline" in issue or "power" in issue or "poe" in issue:
        assigned_agent = "switch_port_agent"
        allowed_tools = [
            "get_switch_port_statuses", 
            "get_cable_test", 
            "get_arp_table", 
            "get_device_switch_ports_statuses_packets", 
            "get_device_lldp_cdp",
            "get_network_events"
        ]
    elif model.startswith("MT") or "sensor" in issue or "temp" in issue:
        assigned_agent = "sensor_iot_agent"
        allowed_tools = [
            "get_sensor_readings",
            "get_network_events"
        ]
    elif model.startswith("MR") or "WIRELESS" in model:
        assigned_agent = "rf_wireless_agent"
        allowed_tools = [
            "get_device_wireless_rf", 
            "get_wireless_connection_stats", 
            "get_wireless_client_connection_stats", 
            "get_network_channel_utilization",
            "get_network_events"
        ]
    elif model.startswith("MS") or "SWITCH" in model:
        assigned_agent = "switch_port_agent"
        allowed_tools = [
            "get_switch_port_statuses", 
            "get_cable_test", 
            "get_arp_table", 
            "get_device_switch_ports_statuses_packets", 
            "get_device_lldp_cdp",
            "get_network_events"
        ]
    elif model.startswith("MX") or "UPLINK" in issue or "wan" in issue:
        assigned_agent = "wan_sdwan_agent"
        allowed_tools = [
            "get_appliance_uplinks", 
            "get_uplink_loss_latency", 
            "get_device_loss_latency", 
            "run_ping_test", 
            "run_throughput_test",
            "get_network_events"
        ]
    else:
        assigned_agent = "client_experience_agent"
        allowed_tools = [
            "get_network_clients", 
            "get_arp_table", 
            "get_network_events"
        ]

    state["route"]             = route
    state["coordination_plan"] = plan
    state["assigned_agent"]    = assigned_agent
    state["allowed_tools"]     = allowed_tools

    print(f"[Coordinator] Assigned Agent: {assigned_agent}")
    print(f"[Coordinator] Allowed Tools: {allowed_tools}")
    print(f"[Coordinator] Route: {route}")
    print(f"[Coordinator] Plan: {plan}")
    return state
