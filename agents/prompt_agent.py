"""
Agent: PromptAgent v6.0 — Smart Telemetry Interpreter + Precedent Injector
Nâng cấp:
  - _summarize_telemetry(): chuyển JSON thô → plain Vietnamese summary cho LLM dễ hiểu
  - Precedent injection: lấy similar cases từ memory để AI học từ lịch sử
  - Confidence từ ConsensusAgent được truyền xuống playbook
  - System prompt expert persona được inject
  - Causal chain hiển thị trong output
"""
import json
from datetime import datetime
from api import llm, memory as semantic_memory
from agents.domain_knowledge import get_firmware_note, get_model_specs
from agents.system_prompts import get_system_prompt


# ── Telemetry Summarizer ───────────────────────────────────────────────────────
def _summarize_telemetry(telemetry: dict, model: str = "") -> str:
    """
    Convert raw telemetry JSON into a concise Vietnamese technical summary.
    This dramatically improves LLM comprehension compared to raw JSON dumps.
    """
    if not telemetry:
        return "Không có dữ liệu telemetry."

    lines = []
    is_ap = model.upper().startswith("MR") if model else False
    is_mx = "MX" in model.upper() if model else False
    is_sw = model.upper().startswith("MS") if model else False

    # ── WAN / Loss / Latency ──────────────────────────────────────────────────
    wan_data = telemetry.get("wan", {})
    if wan_data:
        loss = wan_data.get("loss_pct", wan_data.get("lossPercent"))
        latency = wan_data.get("latency_ms", wan_data.get("latencyMs"))
        uplink_status = wan_data.get("uplinks", [])

        if loss is not None:
            severity = "🔴 CRITICAL" if float(loss) > 5 else ("🟠 WARNING" if float(loss) > 1 else "✅ Normal")
            lines.append(f"WAN Packet Loss: {loss}% ({severity})")
        if latency is not None:
            severity = "🔴 HIGH" if float(latency) > 150 else ("🟡 ELEVATED" if float(latency) > 50 else "✅ Normal")
            lines.append(f"WAN Latency: {latency}ms ({severity})")
        if uplink_status:
            for u in uplink_status[:2]:
                iface = u.get("interface", u.get("iface", "WAN"))
                status = u.get("status", "unknown")
                lines.append(f"Uplink {iface}: {status.upper()}")

    # ── Switch Ports ──────────────────────────────────────────────────────────
    ports = telemetry.get("ports", telemetry.get("switch_ports", []))
    if ports and (is_sw or not is_ap):
        problem_ports = []
        for p in ports[:12]:
            speed = p.get("speed", "")
            poe_power = p.get("powerUsageInWh", p.get("poeWatts", p.get("watts")))
            port_id = p.get("portId", p.get("port", "?"))
            status = p.get("status", p.get("enabled", ""))

            if speed and "100" in str(speed) and "1000" not in str(speed):
                problem_ports.append(f"Port {port_id}: speed={speed} ⚠️ Giảm tốc độ (cáp lỗi?)")
            elif poe_power is not None and float(poe_power) < 10:
                problem_ports.append(f"Port {port_id}: PoE={poe_power}W ⚠️ Nguồn thấp")

        if problem_ports:
            lines.append("⚠️ Cổng switch bất thường:")
            lines.extend([f"  {p}" for p in problem_ports[:4]])
        else:
            normal_count = len(ports)
            lines.append(f"Switch ports: {normal_count} cổng — không phát hiện bất thường tốc độ/PoE")

    # ── Wireless RF ───────────────────────────────────────────────────────────
    rf_data = telemetry.get("rf", telemetry.get("wireless", {}))
    if rf_data and is_ap:
        for band in ["5", "2.4", "6"]:
            band_data = rf_data.get(f"band_{band}GHz", rf_data.get(band, {}))
            if not band_data:
                continue
            util = band_data.get("utilization", band_data.get("channelUtilization"))
            noise = band_data.get("noiseFloor", band_data.get("noise"))
            channel = band_data.get("channel")

            if util is not None:
                severity = "🔴 CONGESTED" if float(util) > 70 else ("🟡 ELEVATED" if float(util) > 40 else "✅ Normal")
                lines.append(f"RF {band}GHz Utilization: {util}% ({severity})")
            if noise is not None:
                severity = "🔴 HIGH NOISE" if float(noise) > -85 else "✅ Normal"
                lines.append(f"RF {band}GHz Noise Floor: {noise}dBm ({severity})")
            if channel:
                lines.append(f"RF {band}GHz Channel: {channel}")

    # ── Clients ───────────────────────────────────────────────────────────────
    clients = telemetry.get("clients", [])
    if clients:
        total = len(clients)
        offline_clients = [c for c in clients if c.get("status", "") in ("offline", "disconnected")]
        poor_signal = [
            c for c in clients
            if c.get("rssi") and float(c.get("rssi", 0)) < -75
        ]
        lines.append(f"Clients: {total} total")
        if offline_clients:
            lines.append(f"  Offline clients: {len(offline_clients)} ({round(len(offline_clients)/total*100)}%)")
        if poor_signal:
            lines.append(f"  Poor signal (<-75dBm): {len(poor_signal)} clients")

    # ── Events ────────────────────────────────────────────────────────────────
    events = telemetry.get("events", [])
    if events:
        event_types = {}
        for e in events[:20]:
            etype = e.get("type", e.get("eventType", "unknown"))
            event_types[etype] = event_types.get(etype, 0) + 1
        top_events = sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:4]
        lines.append(f"Sự kiện hệ thống ({len(events)} tổng):")
        for etype, count in top_events:
            lines.append(f"  {etype}: {count} lần")

    if not lines:
        return "Telemetry có sẵn nhưng không phát hiện thông số bất thường."

    return "\n".join(lines)


def run(state: dict, provider: str = None) -> dict:
    print(f"[PromptAgent v6.0] Building expert playbook (provider={provider or 'auto'})...")

    dev            = state.get("device_detail", {})
    alert          = state.get("alert", {})
    serial         = state.get("resolved_serial", "")
    net_id         = state.get("resolved_net_id", "")
    telemetry      = state.get("telemetry", {})
    bb             = state.get("blackboard", {})
    consensus_note = state.get("notes_consensus", "")
    causal_chain   = state.get("causal_chain", "")
    confidence     = state.get("consensus_confidence", "MEDIUM")

    model      = dev.get("model") or alert.get("model", "")
    firmware   = dev.get("firmware") or "Không có trong cache"
    alert_type = alert.get("issue", "")
    severity   = alert.get("severity", "MEDIUM")
    last_seen  = _fmt_ts(alert.get("lastSeen", ""))

    # Find network name
    org_data = state.get("org", {})
    net_name = "Unknown"
    for n in org_data.get("networks") or []:
        if n.get("id") == net_id:
            net_name = n.get("name", "Unknown")
            break

    # Domain knowledge injection
    model_spec = get_model_specs(model)
    fw_warning = get_firmware_note(firmware)
    poe_note   = ""

    # ── Semantic Memory: Retrieve Similar Incidents ───────────────────────────
    precedent_context = ""
    try:
        similar = semantic_memory.retrieve_similar(
            alert_type=alert_type,
            device_model=model,
            firmware=firmware,
            diagnosis_hint=consensus_note[:200] if consensus_note else "",
            org_id=org_data.get("id", ""),
            top_k=3,
        )
        if similar:
            precedent_lines = [f"📚 Sự cố tương tự đã ghi nhận ({len(similar)} trường hợp):"]
            for i, case in enumerate(similar, 1):
                meta = case.get("metadata", {})
                sim  = case.get("similarity", 0)
                resolution = meta.get("resolution", "Không rõ")[:150]
                precedent_lines.append(
                    f"  [{i}] Tương đồng {sim:.0%} | {meta.get('device_model','?')} | "
                    f"{meta.get('alert_type','?')} → Giải pháp: {resolution}"
                )
            precedent_context = "\n".join(precedent_lines)
            print(f"[PromptAgent v6.0] Injecting {len(similar)} precedent cases from memory.")
    except Exception as e:
        print(f"[PromptAgent v6.0] Memory retrieval skipped: {e}")

    # ── Structured Telemetry Summary (replace raw JSON dump) ─────────────────
    telemetry_summary = _summarize_telemetry(telemetry, model)

    # ── Default Analysis Structure ────────────────────────────────────────────
    if "insight_web_app" in alert_type.lower() or "uplink" in alert_type.lower():
        analysis = {
            "net_name":    net_name,
            "model":       model,
            "serial":      serial,
            "firmware":    firmware,
            "alert_type":  alert_type,
            "severity":    severity,
            "scope":       "network_wide",
            "scope_reason": "Ảnh hưởng diện rộng hiệu năng ứng dụng do suy hao chất lượng đường truyền WAN.",
            "root_causes": [
                ("HIGH", "WAN Uplink Packet Loss", "Tỷ lệ mất gói cao trên đường truyền WAN chính đi quốc tế."),
                ("MEDIUM", "Application Latency Peak", "Độ trễ cao khi truy cập ứng dụng SaaS (Google, Office365)."),
                ("LOW", "DNS Server Timeout", "Máy chủ DNS chính gặp sự cố phản hồi chậm.")
            ],
            "api_checks": [
                f"GET /organizations/{org_data.get('id', '?')}/uplinks/statuses",
                f"GET /devices/{serial}/lossAndLatencyHistory?ip=8.8.8.8&timespan=86400" if serial else "GET /organizations/uplinks/statuses",
            ],
            "actions": [
                f"Kiểm tra chất lượng SD-WAN policy trên Meraki Dashboard",
                f"Cấu hình Uplink Preference định tuyến ứng dụng web sang WAN link ổn định hơn",
            ],
            "poe_note": poe_note,
            "fw_note":  fw_warning,
        }
    else:
        analysis = {
            "net_name":    net_name,
            "model":       model,
            "serial":      serial,
            "firmware":    firmware,
            "alert_type":  alert_type,
            "severity":    severity,
            "scope":       "isolated",
            "scope_reason": "Sự cố cục bộ, chỉ ảnh hưởng đến thiết bị này.",
            "root_causes": [
                ("HIGH", "Network Connectivity Interruption", "Thiết bị gặp gián đoạn kết nối vật lý hoặc sụt nguồn PoE."),
                ("MEDIUM", "Firmware Stability Issue", "Phiên bản firmware hiện tại gặp xung đột hoặc lỗi phần mềm."),
                ("LOW", "IP Configuration Conflict", "Trùng IP management hoặc hết pool cấp phát DHCP.")
            ],
            "api_checks": [
                f"GET /devices/{serial}/switch/ports/statuses" if serial else "GET /devices/statuses",
                f"GET /networks/{net_id}/events?productType=wireless&serials={serial}" if serial and net_id else "GET/networks/events",
            ],
            "actions": [
                f"POST /devices/{serial}/liveTools/reboot — Khởi động lại thiết bị" if serial else "Kiểm tra kết nối vật lý thiết bị",
                f"Kiểm tra cáp kết nối vật lý và cấp nguồn PoE từ upstream switch",
            ],
            "poe_note": poe_note,
            "fw_note":  fw_warning,
        }

    # Collect Audit Log note if present
    audit_note = (
        bb.get("audit_config_agent", "") or
        bb.get("audit_config", "") or
        state.get("notes_audit_config", "")
    )

    # ── LLM-driven Playbook Generation ───────────────────────────────────────
    prompt_sys = get_system_prompt("prompt_agent")
    structured_prompt = f"""Phân tích sự cố mạng và tạo diagnostic playbook JSON.

== THÔNG SỐ SỰ CỐ ==
- Thiết bị: {dev.get('name','?')} ({model}) | Serial: {serial}
- Cảnh báo: {alert_type} ({severity}) | Thời điểm: {last_seen}
- Firmware: {firmware}
{f"- Firmware warning: {fw_warning}" if fw_warning else ""}

== CHẨN ĐOÁN HỢP NHẤT (Consensus — Confidence: {confidence}) ==
{consensus_note}

{f"== THAY ĐỔI CẤU HÌNH ADMIN (AUDIT LOGS) ==\n{audit_note}" if audit_note else ""}

{f"== CHUỖI NHÂN QUẢ ==\n{causal_chain}" if causal_chain else ""}

== TÓM TẮT TELEMETRY ==
{telemetry_summary}

{f"== TIỀN LỆ LỊCH SỬ ==\n{precedent_context}" if precedent_context else ""}

NHIỆM VỤ: Trả về JSON object với đúng 5 trường sau (raw JSON, không markdown):
{{
  "scope": "isolated | multi_device | network_wide | model_specific",
  "scope_reason": "Giải thích ngắn gọn phạm vi bằng tiếng Việt (1 câu)",
  "root_causes": [
    ["HIGH|MEDIUM|LOW", "Tên nguyên nhân tiếng Anh", "Mô tả tiếng Việt chi tiết"],
    ...tối đa 4 phần tử...
  ],
  "api_checks": [
    "GET /devices/{serial}/endpoint — mô tả mục đích",
    ...tối đa 4 endpoints thực tế Meraki API...
  ],
  "actions": [
    "Hành động khẩn cấp 1 bằng tiếng Việt — cụ thể, có thể thực hiện ngay",
    ...tối đa 3 hành động...
  ]
}}"""

    try:
        raw_json = llm.generate(
            structured_prompt,
            provider=provider,
            system_prompt=prompt_sys,
            temperature=0.2,
            max_tokens=2048,
        )
        if raw_json:
            parsed = json.loads(raw_json.strip().strip("```json").strip("```"))
            analysis["scope"] = parsed.get("scope", analysis["scope"])
            analysis["scope_reason"] = parsed.get("scope_reason", analysis["scope_reason"])
            if parsed.get("root_causes"):
                analysis["root_causes"] = [
                    (item[0], item[1], item[2])
                    for item in parsed["root_causes"]
                    if isinstance(item, list) and len(item) == 3
                ]
            if parsed.get("api_checks"):
                analysis["api_checks"] = parsed["api_checks"]
            if parsed.get("actions"):
                analysis["actions"] = parsed["actions"]
    except Exception as e:
        print(f"[PromptAgent v6.0] LLM generation error ({e}) — using structured defaults.")
        
    state["extracted_analysis"] = analysis

    # ── Format Output ─────────────────────────────────────────────────────────
    org_name = org_data.get("name", "?")
    org_id   = org_data.get("id", "?")

    # Collect active blackboard notes dynamically from both state and blackboard
    active_notes = []
    seen_labels = set()
    agent_label_mapping = {
        "device_intel": "⚙️ Thông số Thiết bị & Phần cứng",
        "device_intel_agent": "⚙️ Thông số Thiết bị & Phần cứng",
        "event_log": "📋 Nhật ký Sự kiện",
        "event_log_agent": "📋 Nhật ký Sự kiện",
        "client": "👥 Tác động Người dùng",
        "client_agent": "👥 Tác động Người dùng",
        "uplink": "🌐 Trạng thái Đường truyền WAN",
        "uplink_agent": "🌐 Trạng thái Đường truyền WAN",
        "audit_config": "📝 Lịch sử Thay đổi Cấu hình (Audit Log)",
        "audit_config_agent": "📝 Lịch sử Thay đổi Cấu hình (Audit Log)",
        "app_qoe": "📊 Chất lượng Trải nghiệm Ứng dụng & VoIP",
        "app_qoe_agent": "📊 Chất lượng Trải nghiệm Ứng dụng & VoIP",
        "correlation": "🔄 Phân tích Tương quan Chéo Mạng (Correlation)",
        "correlation_agent": "🔄 Phân tích Tương quan Chéo Mạng (Correlation)",
        "rf_wireless": "📡 Thu thập thông tin RF & Wireless",
        "rf_wireless_agent": "📡 Thu thập thông tin RF & Wireless",
        "switch_port": "🔌 Thu thập thông tin Switch Port & Cáp",
        "switch_port_agent": "🔌 Thu thập thông tin Switch Port & Cáp",
        "wan_sdwan": "🌐 Thu thập thông tin WAN & VPN",
        "wan_sdwan_agent": "🌐 Thu thập thông tin WAN & VPN",
        "sensor_iot": "🌡️ Thu thập thông tin Sensor IoT",
        "sensor_iot_agent": "🌡️ Thu thập thông tin Sensor IoT",
        "security_airmarshal": "🛡️ Thu thập thông tin Security & WIDS",
        "security_airmarshal_agent": "🛡️ Thu thập thông tin Security & WIDS",
        "client_experience": "📱 Thu thập thông tin Client Experience",
        "client_experience_agent": "📱 Thu thập thông tin Client Experience",
        "firmware_crash": "🔥 Thu thập thông tin Firmware & Crash Log",
        "firmware_crash_agent": "🔥 Thu thập thông tin Firmware & Crash Log",
    }

    # Helper function to append and condense note
    def _add_note(key_name: str, raw_note: str):
        if not raw_note or not isinstance(raw_note, str) or "Bỏ Qua" in raw_note or len(raw_note.strip()) <= 15:
            return
        clean_key = key_name.replace("notes_", "").replace("_agent", "")
        label = agent_label_mapping.get(key_name) or agent_label_mapping.get(clean_key) or agent_label_mapping.get(f"{clean_key}_agent")
        if not label:
            label = f"🤖 {clean_key.title()} Agent"
        if label in seen_labels:
            return
        seen_labels.add(label)

        # Clean up confidence badges
        display_note = raw_note.replace("[Confidence: HIGH] ", "").replace("[Confidence: MEDIUM] ", "").replace("[Confidence: LOW] ", "")
        
        # Line-by-line note cleaning: strip confidence badges, preambles, dividers, and triple asterisks ***
        lines = []
        for line in display_note.split("\n"):
            l_str = line.strip()
            if l_str.startswith("Dựa vào tool") and "thu được" in l_str:
                continue  # strip repetitive tool preambles
            if not l_str or l_str in ("***", "---", "___"):
                continue  # strip markdown horizontal dividers

            # Remove all triple asterisks *** directly and cleanly
            cleaned_line = line.replace("***", "")

            # Normalize leading bullet symbols (*, +) to standard (-)
            if cleaned_line.lstrip().startswith("* ") or cleaned_line.lstrip().startswith("+ "):
                indent = len(cleaned_line) - len(cleaned_line.lstrip())
                cleaned_line = " " * indent + "- " + cleaned_line.lstrip()[2:]

            lines.append(cleaned_line)

        indented_note = "\n".join([f"  {line}" for line in lines])
        active_notes.append(f"• {label}:\n{indented_note}\n")

    # 1. Scan predefined labels list first for consistent ordering
    for key in agent_label_mapping.keys():
        note_val = (
            bb.get(key, "") or
            bb.get(f"{key}_agent", "") or
            state.get(f"notes_{key}", "") or
            state.get(f"notes_{key}_agent", "")
        )
        _add_note(key, note_val)

    # 2. Scan remaining state notes_* keys for any custom agents
    for k, v in state.items():
        if k.startswith("notes_") and k not in ["notes_consensus", "notes_reporting", "notes_final_prompt"]:
            _add_note(k, v)

    # Root causes string
    causes_str = "\n".join([
        f"  {i+1}. {'🔴' if p == 'HIGH' else '🟠' if p == 'MEDIUM' else '🟡'} [{p}] {c}: {d}"
        for i, (p, c, d) in enumerate(analysis["root_causes"][:4])
    ])

    api_str    = "\n".join([f"  {i+1}. {api}" for i, api in enumerate(analysis["api_checks"][:4])])
    action_str = "\n".join([f"  {i+1}. {act}" for i, act in enumerate(analysis["actions"][:3])])

    scope_badge = {
        "isolated":             "🟡 CỤC BỘ",
        "multi_device":         "🟠 NHIỀU THIẾT BỊ",
        "network_wide":         "🔴 DIỆN RỘNG",
        "model_specific":       "🔴 THEO DÒNG THIẾT BỊ",
        "critical_widespread":  "🚨 KHẨN CẤP DIỆN RỘNG",
    }.get(analysis["scope"], "⚪ CHƯA RÕ")

    confidence_badge = {"HIGH": "🟢 HIGH", "MEDIUM": "🟡 MEDIUM", "LOW": "🔴 LOW"}.get(confidence, "⚪")

    # Compute dynamic telemetry values for playbooks
    clients_count = len(state.get("clients", []))
    events_count = len(state.get("events", []))
    wan_data = telemetry.get("wan", {})
    wan_str = "N/A"
    if wan_data:
        loss = wan_data.get("avg_loss_pct", wan_data.get("loss_pct", 0.0))
        latency = wan_data.get("avg_latency_ms", wan_data.get("latency_ms", 0.0))
        wan_str = f"{loss}% loss | {round(latency) if isinstance(latency, (int, float)) else latency}ms latency"

    prompt_parts = [
        f"🔍 THÔNG TIN SỰ CỐ TỔNG QUAN",
        f"• Tổ chức       : {org_name} (ID: {org_id})",
        f"• Mạng          : {net_name}",
        f"• Thiết bị      : {dev.get('name','Unknown')} | Model: {model} | Serial: {serial}",
        f"• Firmware      : {firmware}",
        f"• Alert         : {alert_type} | Severity: {severity}",
        f"• Thời điểm     : {last_seen}",
        f"• IP / MAC      : {dev.get('lanIp') or dev.get('publicIp','N/A')} / {dev.get('mac','N/A')}",
    ]

    # Dynamic metrics facts block
    prompt_parts += [
        f"\n📊 SỐ LIỆU TELEMETRY THU THẬP THỰC TẾ (GROUND TRUTH):",
        f"  - Thiết bị     : Model {model} (Trạng thái: {dev.get('status', 'N/A')}) | Firmware: {firmware}",
        f"  - Đường truyền : {wan_str}",
        f"  - Người dùng   : {clients_count} máy khách đang kết nối hoạt động",
        f"  - Nhật ký      : {events_count} events ghi nhận trong cửa sổ giám sát",
    ]

    if analysis.get("fw_note"):
        prompt_parts.append(f"\n⚠️ Lưu ý Firmware: {analysis['fw_note']}")

    if active_notes:
        prompt_parts.append("\n📋 BÁO CÁO SỐ LIỆU TỪ AI AGENTS:\n")
        prompt_parts.extend(active_notes)

    if precedent_context:
        prompt_parts.append(f"\n📚 LỊCH SỬ SỰ CỐ TƯƠNG TỰ:\n{precedent_context}")

    prompt_parts += [
        f"\n🎯 YÊU CẦU AI ASSISTANT:",
        f"Dựa vào những thông tin trên hãy kiểm tra và đưa ra kết luận chẩn đoán sâu sát nhất.",
    ]

    result = "\n".join(prompt_parts)
    state["final_prompt"] = result
    return state


from config import to_vn_time

def _fmt_ts(ts: str) -> str:
    if not ts:
        return "N/A"
    res = to_vn_time(ts, "%d/%m/%Y %H:%M")
    return f"{res} (giờ VN)" if res and "/" in res else res
