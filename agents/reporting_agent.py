"""
Agent 7 — ReportingAgent (v4.3 — Domain-Expert Executive Reporter)
Dịch thông tin kỹ thuật mạng phức tạp thành báo cáo rõ ràng, chuyên nghiệp cho Nhân sự và Ban Quản lý.
Không sử dụng các lời chào hay lời giải thích thừa của chatbot ở đầu/cuối báo cáo.
"""
from api import llm
from agents.react_loop import clean_technical_note


def run(state: dict) -> dict:
    print("[ReportingAgent] Generating executive report...")

    alert = state.get("alert", {})
    notes_di = state.get("notes_device_intel", "Bình thường.")
    notes_co = state.get("notes_correlation_agent", "Lỗi đơn lẻ.")
    notes_el = state.get("notes_event_log", "Không phát hiện bất thường.")
    notes_ca = state.get("notes_client_agent", "Không ảnh hưởng.")
    notes_ua = state.get("notes_uplink_agent", "Ổn định.")
    notes_ac = state.get("notes_audit_config", "")
    notes_aq = state.get("notes_app_qoe", "")
    notes_sa = state.get("notes_security_airmarshal_agent", "")
    notes_fc = state.get("notes_firmware_crash_agent", "")
    notes_si = state.get("notes_sensor_iot_agent", "")
    notes_rf = state.get("notes_rf_wireless_agent", "")
    notes_sp = state.get("notes_switch_port_agent", "")
    notes_ws = state.get("notes_wan_sdwan_agent", "")

    prompt = f"""You are an IT Infrastructure Director communicating with Company Executives and HR.
Translate the following complex technical network diagnostic findings into a highly specific, professional, and action-oriented status report in Vietnamese.

== CRITICAL DIRECTIONS FOR PROFESSIONAL TONE ==
1. DO NOT use generic boilerplate sentences or clichés (e.g., "Sự cố mạng nghiêm trọng xảy ra...", "IT đang triển khai kiểm tra và phân tích...", "sẽ được cập nhật sau..."). These are weak and non-informative.
2. BE SPECIFIC and quantitative: You must include exact device names, models, numbers, and admin names (e.g., "12.4W", "8 clients", "39.7ms latency", "Admin CMC Duc") as concrete evidence of the issue.
3. PROVIDE CONCRETE REMEDIATION PLANS:
   - If the issue is human error / config change: State exact admin account and port change.
   - If the issue is insufficient PoE power: State that IT is configuring the switch port to PoE+ (802.3at) or replacing it with a 30W PoE Injector.
   - If the issue is WAN loss/latency: State that IT is routing application traffic to backup ISP (WAN2).
4. Keep the text professional, decisive, and direct.

== TECHNICAL FINDINGS ==
- Device: {alert.get('device', 'AP')} ({alert.get('model', 'MR46')})
- Serial: {alert.get('serial', 'N/A')}
- Issue: {alert.get('issue', 'Device is offline')} (Severity: {alert.get('severity', 'HIGH')})
- Hardware/Firmware Status: {notes_di}
- Scope of Outage: {notes_co}
- Network Events: {notes_el}
- Impact on Users: {notes_ca}
- WAN/Internet Path: {notes_ua}
- Audit & Config Changes: {notes_ac if notes_ac else 'Không có thay đổi cấu hình bất thường'}
- Application QoE & VoIP: {notes_aq if notes_aq else 'Không suy hao'}
- Wireless Security AirMarshal: {notes_sa if notes_sa else 'Bình thường'}
- Firmware & Crashes: {notes_fc if notes_fc else 'Ổn định'}
- Sensor IoT & Environment: {notes_si if notes_si else 'Bình thường'}
- RF Spectrum & Wi-Fi: {notes_rf if notes_rf else 'Ổn định'}
- Switch Port & Cable: {notes_sp if notes_sp else 'Bình thường'}
- WAN SD-WAN Path: {notes_ws if notes_ws else 'Ổn định'}

== OUTPUT STRUCTURE (MUST FOLLOW EXACTLY) ==
📄 BÁO CÁO TÌNH TRẠNG SỰ CỐ MẠNG

1. TÌNH TRẠNG HIỆN TẠI
[Nêu rõ thiết bị nào, tại phòng ban nào đang gặp sự cố cụ thể gì, mức độ ưu tiên xử lý khẩn cấp]

2. QUY MÔ ẢNH HƯỞNG
[Phạm vi phòng ban bị ảnh hưởng, số lượng nhân sự/máy khách bị gián đoạn kết nối, mức độ ảnh hưởng đến vận hành doanh nghiệp]

3. NGUYÊN NHÂN SƠ BỘ
[Giải thích nguyên nhân kỹ thuật một cách dễ hiểu nhưng cụ thể, bắt buộc đưa số liệu kỹ thuật làm bằng chứng, ví dụ: cổng switch cấp nguồn thiếu hụt 12.4W so với 25.5W yêu cầu làm thiết bị khởi động lại liên tục]

Output ONLY the Vietnamese report text. Absolutely NO greetings, NO chatbot preambles, and NO conversational filler."""

    result = llm.generate(prompt)
    cleaned = clean_technical_note(result or "Chưa tạo được báo cáo nhân sự.")
    
    # Ensure it starts with the correct header and has no chatbot preamble
    if "BÁO CÁO" not in cleaned and "📄" not in cleaned:
        cleaned = "📄 BÁO CÁO TÌNH TRẠNG SỰ CỐ MẠNG\n\n" + cleaned

    state["notes_reporting"] = cleaned
    return state
