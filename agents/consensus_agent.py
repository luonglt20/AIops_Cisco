"""
Agent 8 — ConsensusAgent v5.0 (2-Phase Structured Debate + Causal Chain)
Nâng cấp từ 1-shot → 2-phase diagnostic debate:
  Phase 1: Evidence Weighing — so sánh báo cáo agents với raw telemetry
  Phase 2: Causal Chain + Confidence Verdict — chuỗi nhân quả + mức độ chắc chắn

Output bổ sung:
  - causal_chain: chuỗi nhân quả A → B → C
  - confidence: HIGH | MEDIUM | LOW
  - consensus_note: chẩn đoán thống nhất cuối cùng (tiếng Việt)
"""
import json
from api import llm
from agents.react_loop import clean_technical_note
from agents.system_prompts import get_system_prompt


def run_consensus(state: dict) -> str:
    """
    Run 2-phase consensus debate across all specialist agent reports.
    Returns unified diagnostic string and enriches state with structured consensus data.
    """
    print("[ConsensusAgent v5.0] Initiating 2-phase multi-agent diagnostic debate...")

    notes_di  = state.get("notes_device_intel", "")
    notes_co  = state.get("notes_correlation_agent", "")
    notes_el  = state.get("notes_event_log", "")
    notes_ca  = state.get("notes_client_agent", "")
    notes_ua  = state.get("notes_uplink_agent", "")
    notes_ac  = state.get("notes_audit_config", "")
    notes_aq  = state.get("notes_app_qoe", "")
    notes_sa  = state.get("notes_security_airmarshal_agent", "")
    notes_fc  = state.get("notes_firmware_crash_agent", "")
    notes_si  = state.get("notes_sensor_iot_agent", "")
    notes_rf  = state.get("notes_rf_wireless_agent", "")
    notes_sp  = state.get("notes_switch_port_agent", "")
    notes_ws  = state.get("notes_wan_sdwan_agent", "")
    notes_cx  = state.get("notes_client_experience_agent", "")
    telemetry = state.get("telemetry", {})
    alert     = state.get("alert", {})
    dev       = state.get("device_detail", {})

    # Build agent report blocks
    route = state.get("route", {})
    agent_reports = []
    report_map = {
        "DeviceIntel [Phần cứng & Firmware]": notes_di if route.get("run_device_intel", True) else "",
        "CorrelationAgent [Tương quan chéo]": notes_co if route.get("run_correlation_agent", True) else "",
        "EventLog [Nhật ký sự kiện]": notes_el if route.get("run_event_log", True) else "",
        "ClientAgent [Tác động người dùng]": notes_ca if route.get("run_client_agent", True) else "",
        "UplinkAgent [WAN & Kết nối]": notes_ua if route.get("run_uplink_agent", True) else "",
        "AuditConfigAgent [Nhật ký thay đổi cấu hình Audit]": notes_ac if route.get("run_audit_config", True) else "",
        "AppQoEAgent [Trải nghiệm ứng dụng & VoIP]": notes_aq if route.get("run_app_qoe", True) else "",
        "SecurityAirMarshalAgent [Bảo mật vô tuyến AirMarshal]": notes_sa,
        "FirmwareCrashAgent [Firmware & Crashes]": notes_fc,
        "SensorIoTAgent [Cảm biến IoT & Môi trường]": notes_si,
        "RfWirelessAgent [Tần số vô tuyến RF]": notes_rf,
        "SwitchPortAgent [Cổng Switch & Cáp TDR]": notes_sp,
        "WanSdwanAgent [Gateway & SD-WAN Path]": notes_ws,
        "ClientExperienceAgent [Trải nghiệm Wi-Fi Client]": notes_cx,
    }
    for label, note in report_map.items():
        if note and "Bỏ Qua" not in note and len(note.strip()) > 15:
            agent_reports.append(f"▶ {label}:\n  {note.strip()}")

    if not agent_reports:
        print("[ConsensusAgent v5.0] No agent reports available — returning default.")
        default_note = f"Không đủ dữ liệu agent để tranh biện. Sự cố: {alert.get('issue','?')} trên {dev.get('name','?')}."
        state["notes_consensus"] = default_note
        state["consensus_confidence"] = "LOW"
        state["causal_chain"] = ""
        return default_note

    reports_str  = "\n\n".join(agent_reports)
    telemetry_str = json.dumps(telemetry, indent=2, ensure_ascii=False)
    consensus_sys = get_system_prompt("consensus")
    alert_type   = alert.get("issue", "unknown")
    dev_name     = dev.get("name", "Unknown Device")
    dev_model    = dev.get("model", alert.get("model", ""))

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 1: Evidence Weighing — tìm điểm đồng thuận và mâu thuẫn
    # ─────────────────────────────────────────────────────────────────────────
    phase1_prompt = f"""Bạn đang phân tích sự cố mạng: [{alert_type}] trên thiết bị {dev_name} ({dev_model}).

== BÁO CÁO TỪ CÁC AGENTS CHUYÊN MÔN ==
{reports_str}

== SỐ LIỆU TELEMETRY GỐC (GROUND TRUTH) ==
{telemetry_str}

NHIỆM VỤ PHASE 1 — EVIDENCE WEIGHING:
Hãy thực hiện theo đúng cấu trúc sau (3 mục, không thêm gì khác):

ĐIỂM ĐỒNG THUẬN:
• [liệt kê tối đa 3 điểm mà ≥2 agent đồng ý và có bằng chứng từ telemetry]

ĐIỂM MÂU THUẪN:
• [liệt kê các điểm mà các agent không đồng ý với nhau, hoặc mâu thuẫn với telemetry]
• [Nếu không có mâu thuẫn, ghi: Không có mâu thuẫn đáng kể]

BẰNG CHỨNG SỐ LIỆU ỦNG HỘ:
• [trích dẫn số liệu cụ thể từ telemetry JSON: port speed, packet loss %, power watts, v.v.]
• [Nếu không có số liệu cụ thể, ghi: Telemetry không có số liệu định lượng rõ ràng]"""

    print("[ConsensusAgent v5.0] Phase 1: Evidence Weighing...")
    phase1_result = llm.generate(
        phase1_prompt,
        system_prompt=consensus_sys,
        temperature=0.25,
        max_tokens=1024,
    )

    if not phase1_result:
        phase1_result = "Không thể phân tích evidence — sử dụng báo cáo agents trực tiếp."

    print(f"[ConsensusAgent v5.0] Phase 1 complete ({len(phase1_result)} chars)")

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2: Causal Chain + Confidence Verdict
    # ─────────────────────────────────────────────────────────────────────────
    phase2_prompt = f"""Bạn đang đưa ra phán quyết cuối cùng cho sự cố: [{alert_type}] trên {dev_name}.

== KẾT QUẢ TRANH BIỆN PHASE 1 ==
{phase1_result}

== BÁO CÁO AGENTS ĐẦY ĐỦ ==
{reports_str}

== SỐ LIỆU TELEMETRY GỐC ==
{telemetry_str}

NHIỆM VỤ PHASE 2 — FINAL VERDICT:
Hãy trả về một JSON object chứa đúng 3 trường sau (không thêm markdown, không giải thích):

{{
  "causal_chain": "Mô tả chuỗi nhân quả dạng A → B → C bằng tiếng Việt kỹ thuật (ví dụ: Sụt nguồn PoE port 12 → AP watchdog reboot mỗi 4h → 47 client mất kết nối WiFi). Nếu không đủ bằng chứng thì ghi chuỗi ngắn 1 bước.",
  "confidence": "HIGH hoặc MEDIUM hoặc LOW — HIGH khi có số liệu telemetry cụ thể; MEDIUM khi dựa trên pattern; LOW khi suy diễn",
  "diagnosis": "Nhận định thống nhất cuối cùng (2-4 câu tiếng Việt kỹ thuật, không chào hỏi, đi thẳng vào kết luận)"
}}"""

    print("[ConsensusAgent v5.0] Phase 2: Final Verdict + Causal Chain...")
    phase2_result = llm.generate(
        phase2_prompt,
        system_prompt=consensus_sys,
        temperature=0.2,    # Very low temp for structured JSON output
        max_tokens=768,
    )

    # ── Parse Phase 2 JSON ────────────────────────────────────────────────────
    causal_chain     = ""
    confidence       = "MEDIUM"
    consensus_note   = ""

    if phase2_result:
        raw = phase2_result.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = lines[1:] if lines[0].startswith("```") else lines
            lines = lines[:-1] if lines and lines[-1].startswith("```") else lines
            raw = "\n".join(lines).strip()
        try:
            parsed = json.loads(raw)
            causal_chain   = parsed.get("causal_chain", "")
            confidence     = parsed.get("confidence", "MEDIUM").upper()
            consensus_note = parsed.get("diagnosis", "")
            if confidence not in ("HIGH", "MEDIUM", "LOW"):
                confidence = "MEDIUM"
            print(f"[ConsensusAgent v5.0] ✅ Consensus parsed — confidence={confidence}")
        except (json.JSONDecodeError, Exception) as e:
            print(f"[ConsensusAgent v5.0] JSON parse failed ({e}), extracting from raw text...")
            # Fallback: extract diagnosis text from raw response
            consensus_note = clean_technical_note(phase2_result)
            # Try to find confidence keyword in raw text
            for conf_level in ("HIGH", "MEDIUM", "LOW"):
                if conf_level in phase2_result.upper():
                    confidence = conf_level
                    break

    # ── Fallback if phase 2 completely failed ─────────────────────────────────
    if not consensus_note:
        print("[ConsensusAgent v5.0] Phase 2 failed — using phase 1 summary as fallback.")
        consensus_note = clean_technical_note(phase1_result or reports_str[:300])
        confidence     = "LOW"

    # ── Build final formatted output ──────────────────────────────────────────
    confidence_badge = {
        "HIGH":   "🟢 [HIGH]",
        "MEDIUM": "🟡 [MEDIUM]",
        "LOW":    "🔴 [LOW]",
    }.get(confidence, "⚪ [UNKNOWN]")

    final_lines = [f"{confidence_badge} {consensus_note}"]
    if causal_chain:
        final_lines.append(f"⛓️ Chuỗi nhân quả: {causal_chain}")

    final_consensus = "\n".join(final_lines)

    # Store all consensus data in state
    state["notes_consensus"]      = final_consensus
    state["consensus_confidence"] = confidence
    state["causal_chain"]         = causal_chain
    state["phase1_evidence"]      = phase1_result

    print(f"[ConsensusAgent v5.0] Consensus complete: {confidence} — {consensus_note[:100]}...")
    return final_consensus
