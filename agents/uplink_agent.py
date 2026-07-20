"""
Agent: UplinkAgent (v5.1 — Real AI-Driven WAN Telemetry Analyzer + Expert Persona)
Phân tích chất lượng đường truyền WAN1/WAN2, tỷ lệ loss & latency thực tế trên các Gateway (MX).
Nếu thiết bị là AP/Switch, phân tích connectivity cục bộ dựa trên dữ liệu thật.
Không sử dụng bộ luật cứng Python.
"""
import json
from api import llm, meraki
from agents.react_loop import run_react_loop
from agents.system_prompts import get_system_prompt
from api.telemetry import summarize as telemetry_summary



def _tool_device_loss_latency(serial: str, org_id: str) -> str:
    if not serial:
        return "Không có serial hợp lệ."
    try:
        history = meraki.get_device_loss_latency(serial, timespan=86400)
        if not isinstance(history, list) or not history:
            return "Không có dữ liệu loss/latency (không áp dụng cho AP/Switch)."
        return json.dumps(history[-10:], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Không truy vấn được loss/latency: {e}"


def _tool_appliance_uplinks(serial: str, org_id: str) -> str:
    if not org_id:
        return "Không có org ID."
    try:
        uplinks = meraki.get_appliance_uplinks(org_id)
        for u in uplinks:
            if u.get("serial") == serial:
                return json.dumps(u, indent=2, ensure_ascii=False)
        return "Không tìm thấy serial trong danh sách appliance uplinks."
    except Exception as e:
        return f"Không truy vấn được uplinks: {e}"


TOOL_REGISTRY = {
    "get_device_loss_latency": lambda serial, org_id: _tool_device_loss_latency(serial, org_id),
    "get_appliance_uplinks":   lambda serial, org_id: _tool_appliance_uplinks(serial, org_id),
    "run_throughput_test":     lambda serial, org_id: _tool_throughput_test(serial),
}


def _tool_throughput_test(serial: str) -> str:
    if not serial:
        return "Không có serial."
    try:
        res = meraki.run_throughput_test(serial)
        if res and res.get("status") == "completed":
            return json.dumps(res, indent=2, ensure_ascii=False)
        return json.dumps({
            "status": "failed_real_api",
            "error_detail": f"Live Throughput Test API không thành công: {res.get('error', 'API error') if res else 'Unknown'}.",
            "note": "Cần đo kiểm băng thông WAN trực tiếp từ trang Dashboard."
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi gọi live tool Throughput Test: {e}"


def run(state: dict) -> dict:
    org_id = state["org"].get("id", "")
    serial = state.get("resolved_serial", "")
    net_id = state.get("resolved_net_id", "")

    uplink_data = {}
    if org_id:
        try:
            uplinks = meraki.get_appliance_uplinks(org_id)
            for u in uplinks:
                if u.get("serial") == serial or u.get("networkId") == net_id:
                    uplink_data = u
                    break
        except Exception:
            pass

    state["uplink"] = uplink_data
    return state


def analyze_with_llm(state: dict) -> str:
    uplink     = state.get("uplink", {})
    serial     = state.get("resolved_serial", "")
    org_id     = state.get("org", {}).get("id", "")
    alert      = state.get("alert", {})
    blackboard = state.get("blackboard", {})
    telemetry  = state.get("telemetry", {})

    model = state.get("device_detail", {}).get("model") or alert.get("model") or ""
    if not isinstance(model, str):
        model = str(model)
    is_mx = "MX" in model.upper() or "appliance" in model.lower()

    tool_section = ""
    if serial:
        if is_mx:
            tool_section = (
                "\n\n== TOOLS KHẢ DỤNG CHO REACT ==\n"
                "  Action: get_device_loss_latency  → Kiểm tra lịch sử WAN loss/latency\n"
                "  Action: get_appliance_uplinks    → Kiểm tra trạng thái các cổng WAN vật lý\n"
                "  Action: run_throughput_test     → Chạy Live Speedtest băng thông upload/download thực tế\n\n"
                "== MA TRẬN QUYẾT ĐỊNH GỌI TOOL BẮT BUỘC ==\n"
                "1. Nếu nghi ngờ WAN1/WAN2 bị suy hao hoặc mất gói:\n"
                "   -> BẮT BUỘC viết 'Action: get_device_loss_latency' để đo loss/latency.\n"
                "2. Nếu nghi ngờ nhà mạng bóp băng thông (throttling) hoặc tắc nghẽn đường truyền:\n"
                "   -> Gọi 'Action: run_throughput_test' để đo tốc độ Mbps thực tế."
            )
        else:
            tool_section = (
                "\n\nLưu ý: Đây là AP/Switch (không phải MX). Không gọi được tools WAN."
            )

    bb_ctx = ("\n== BLACKBOARD CONTEXT ==\n" + "\n".join([f"- {k}: {v[:100]}" for k, v in blackboard.items()])) if blackboard else ""

    base_prompt = f"""Bạn là Kỹ sư giám sát đường truyền WAN (WAN Uplink Engineer) của Cisco Meraki.
Nhiệm vụ: Đánh giá chất lượng WAN/connectivity dựa trên dữ liệu JSON thô.

== THÔNG TIN THIẾT BỊ ==
- Thiết bị: {alert.get('device','?')} (Model: {model})
- Serial: {serial}
- Uplink từ cache: {json.dumps(uplink, indent=2, ensure_ascii=False) if uplink else 'Không có dữ liệu'}

== DỮ LIỆU TELEMETRY THÔ (RAW TELEMETRY JSON) ==
{json.dumps(telemetry.get('wan', {}), indent=2, ensure_ascii=False)}
{bb_ctx}
{tool_section}

== CẨN THẬN: NGUYÊN TẮC TRUNG THỰC DỮ LIỆU ==
1. Tuyệt đối không tự bịa ra tỷ lệ mất gói (loss %) hay độ trễ (latency ms) nếu dữ liệu thực tế rỗng hoặc bình thường.
2. Nếu không có dữ liệu WAN (ví dụ do thiết bị là AP/Switch nên không có WAN1/WAN2), hãy giải thích rõ: *"Thiết bị là Access Point, các chỉ số WAN Uplink không áp dụng trực tiếp. Kết nối Layer 2 nội bộ bình thường."*
3. Nếu phát hiện suy hao thực tế (packet loss > 5% hoặc latency > 150ms), hãy phân tích ảnh hưởng từ nguyên lý gốc (ví dụ: ISP routing, link degradation).
NHIỆM VỤ: Trình bày gạch đầu dòng ngắn gọn (bullet points) tóm tắt số liệu thô (CHỈ RAW DATA, KHÔNG ĐƯA RA KẾT LUẬN, KHÔNG VIẾT VĂN XUÔI DÀI DÒNG):
- Đưa ra con số cụ thể (Loss, Latency) và cổng liên quan.
- Liên kết với sự cố hiện tại.
- SLA/khuyến nghị kỹ thuật tiếp theo.
KHÔNG chào hỏi, KHÔNG kính ngữ, KHÔNG thêm 'Action:' ở cuối."""

    uplink_sys = get_system_prompt("uplink_agent")
    allowed = state.get("allowed_tools", [])
    active_registry = {k: v for k, v in TOOL_REGISTRY.items() if not allowed or k in allowed}

    final_note = run_react_loop(
        agent_name="UplinkAgent",
        base_prompt=base_prompt,
        tool_registry=active_registry,
        tool_args=(serial, org_id),
        max_iterations=2 if is_mx else 1,
        system_prompt=uplink_sys,
        alert_ctx=state.get("alert", {}),
    )

    state.setdefault("blackboard", {})["uplink_agent"] = final_note
    print(f"[UplinkAgent v5.1] Analysis generated (length={len(final_note)})")
    return final_note
