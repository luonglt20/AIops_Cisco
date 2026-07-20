import json
from api import llm, meraki
from agents.react_loop import run_react_loop, clean_technical_note


TOOL_REGISTRY = {
    "get_network_topology": lambda net_id: _tool_network_topology(net_id),
}


def _tool_network_topology(net_id: str) -> str:
    if not net_id:
        return "Không có net_id."
    try:
        topo = meraki.get_network_topology(net_id)
        if not topo:
            return "Dữ liệu sơ đồ liên kết Layer 2 rỗng."
        return json.dumps(topo, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi truy vấn sơ đồ liên kết Layer 2: {e}"


def run(state: dict) -> dict:
    org_data = state.get("org", {})
    alert = state.get("alert", {})
    net_id = state.get("resolved_net_id", "")

    dev_list = org_data.get("devices", {}).get("list", [])
    net_devices = [d for d in dev_list if d.get("networkId") == net_id]
    
    offline_net = len([d for d in net_devices if d.get("status") == "offline"])
    alerting_net = len([d for d in net_devices if d.get("status") == "alerting"])
    
    state["correlation_stats"] = {
        "total_net_devices": len(net_devices),
        "offline_net_devices": offline_net,
        "alerting_net_devices": alerting_net,
        "total_org_devices": len(dev_list),
        "total_org_offline": org_data.get("devices", {}).get("offline", 0),
    }
    return state


def analyze_with_llm(state: dict) -> str:
    stats  = state.get("correlation_stats", {})
    alert  = state.get("alert", {})
    net_id = state.get("resolved_net_id", "")
    blackboard = state.get("blackboard", {})

    total_net = stats.get("total_net_devices", 0)
    off_net = stats.get("offline_net_devices", 0)
    alert_net = stats.get("alerting_net_devices", 0)
    
    issue_desc = alert.get("issue", "Unknown")
    dev_name = alert.get("device", "Unknown")

    bb_ctx = ""
    if blackboard:
        bb_ctx = "\n== SHARED BLACKBOARD ==\n" + "\n".join([f"- {k}: {v[:120]}" for k, v in blackboard.items()]) + "\n"

    base_prompt = f"""Bạn là kỹ sư đối soát tương quan mạng (Correlation Engineer) trong hệ thống Cisco Meraki AIOps.
Nhiệm vụ: Đưa ra nhận định kỹ thuật đối soát tương quan lỗi chéo.

== TOOLS KHẢ DỤNG CHO REACT ==
- Action: get_network_topology -> Truy vấn sơ đồ kết nối mạng Layer 2 (topology) để phân tích liên kết giữa các thiết bị

== MA TRẬN QUYẾT ĐỊNH GỌI TOOL BẮT BUỘC ==
1. Nếu phát hiện nhiều thiết bị trong cùng chi nhánh đồng thời báo lỗi/offline:
   -> BẮT BUỘC viết "Action: get_network_topology" để lấy đồ thị liên kết Layer 2, xác định xem các thiết bị này có cắm chung vào 1 Switch/MX Core không.

== THÔNG SỐ TƯƠNG QUAN ==
- Thiết bị lỗi chính: {dev_name} ({alert.get('model','')})
- Cảnh báo: {issue_desc}
- Tổng số thiết bị trong cùng Network: {total_net}
- Số thiết bị offline cùng Network: {off_net}
- Số thiết bị alerting cùng Network: {alert_net}
- Tổng thiết bị offline trong toàn Org: {stats.get('total_org_offline', 0)} / {stats.get('total_org_devices', 0)}
{bb_ctx}
YÊU CẦU:
1. Đánh giá lỗi là Cục bộ (Isolated) hay Diện rộng (Site-wide/Network-wide/Org-wide). Dựa vào tỷ lệ phần trăm thiết bị lỗi trên tổng số (ví dụ: {off_net + alert_net}/{total_net} thiết bị trong nhánh).
2. Phân tích nguyên nhân chéo: Nếu nhiều thiết bị cùng bị ảnh hưởng, xác định lỗi ở lớp nào (Physical Layer, Distribution Layer, hoặc ISP Uplink).
3. Đưa ra kết luận ngắn gọn (3 câu). KHÔNG chào hỏi, KHÔNG giới thiệu, KHÔNG sử dụng kính ngữ xã giao. Viết trực diện vấn đề kỹ thuật."""

    final_note = run_react_loop(
        agent_name="CorrelationAgent",
        base_prompt=base_prompt,
        tool_registry=TOOL_REGISTRY,
        tool_args=(net_id,),
        max_iterations=2,
        alert_ctx=alert,
    )
    
    if "blackboard" not in state:
        state["blackboard"] = {}
    state["blackboard"]["correlation_agent"] = final_note
    return final_note
