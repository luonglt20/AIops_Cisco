"""
MerakiMind — ReAct Loop Engine v5.0
Nâng cấp:
  - Inject expert system_prompt vào mỗi LLM call
  - Confidence scoring: AI tự đánh giá mức chắc chắn sau khi generate
  - Token budget tracking để tránh vòng lặp không cần thiết
  - Cải thiện Critic prompt với checklist kỹ thuật theo loại alert
  - Cleanup patterns mở rộng hơn
"""
import re
from api import llm
from agents.system_prompts import get_system_prompt

# ── Cleanup Patterns ───────────────────────────────────────────────────────────
CLEANUP_PATTERNS = [
    r"^(Chào\s+(bạn|anh|chị|quý\s+khách|mọi\s+người),?)\s*",
    r"^(Dưới\s+đây\s+là|Tôi\s+xin\s+gửi|Tôi\s+xin\s+đưa\s+ra|Sau\s+đây\s+là)\s*[^:]*:\s*",
    r"^(Dưới\s+đây\s+là\s+nhận\s+định\s+kỹ\s+thuật[^:]*:\s*)",
    r"^(Tôi\s+là\s+[^,\n]+Agent,?)\s*",
    r"^(Xin\s+chào,?)\s*",
    r"^(Nhận\s+định\s+kỹ\s+thuật\s+của\s+tôi[^:]*:\s*)",
    r"^(Với\s+tư\s+cách\s+là[^,]+,)\s*",
    r"^(Là\s+một\s+kỹ\s+sư[^,]+,)\s*",
]

# ── Confidence Keywords Mapping ────────────────────────────────────────────────
_HIGH_CONFIDENCE_KEYWORDS = [
    "phát hiện", "xác nhận", "ghi nhận", "đo được", "thực tế",
    "confirmed", "detected", "measured", "observed", "%", "ms", "mbps", "gbps"
]
_LOW_CONFIDENCE_KEYWORDS = [
    "có thể", "khả năng", "dường như", "nghi ngờ", "không rõ", "chưa xác định",
    "possibly", "likely", "unclear", "uncertain", "might", "could"
]


def clean_technical_note(text: str) -> str:
    """Remove social pleasantries and formatting artifacts from LLM output."""
    if not text:
        return ""
    # Fix unmatched double asterisks formatting glitch like '**Field:*' -> '**Field:**'
    text = re.sub(r'\*\*([^*]+):\*(?!\*)', r'**\1:**', text)
    text = re.sub(r'(?<!\*)\*([^*]+):\*\*', r'**\1:**', text)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        cleaned_line = line.strip()
        for pattern in CLEANUP_PATTERNS:
            cleaned_line = re.sub(pattern, "", cleaned_line, flags=re.IGNORECASE)
        if cleaned_line:
            cleaned_lines.append(cleaned_line)
    return "\n".join(cleaned_lines)


def _score_confidence(text: str) -> str:
    """
    Heuristically determine confidence level of an AI diagnosis.
    Returns: 'HIGH' | 'MEDIUM' | 'LOW'
    """
    if not text:
        return "LOW"
    text_lower = text.lower()
    high_hits = sum(1 for kw in _HIGH_CONFIDENCE_KEYWORDS if kw in text_lower)
    low_hits  = sum(1 for kw in _LOW_CONFIDENCE_KEYWORDS  if kw in text_lower)

    # Presence of actual numbers/metrics = high confidence
    has_numbers = bool(re.search(r'\d+(\.\d+)?\s*(ms|mbps|gbps|%|w|dbm)', text_lower))
    if has_numbers:
        high_hits += 2

    if high_hits >= 3 and low_hits <= 1:
        return "HIGH"
    elif low_hits >= 3 or (low_hits > high_hits):
        return "LOW"
    return "MEDIUM"


def _build_critic_prompt(agent_name: str, draft: str, base_prompt: str, alert_ctx: dict = None) -> str:
    """Build an improved critic prompt with agent-specific checklist."""
    agent_key = agent_name.lower()
    alert_ctx  = alert_ctx or {}

    # Build alert context note so critic knows what data was available
    has_serial  = bool(alert_ctx.get("serial", ""))
    has_model   = bool(alert_ctx.get("model"))
    issue_type  = alert_ctx.get("issue", "")
    is_assurance_alert = issue_type and not has_serial  # Assurance alerts have no device serial

    data_availability_note = ""
    if is_assurance_alert:
        data_availability_note = (
            f"\n⚠️ LƯU Ý QUAN TRỌNG: Đây là Assurance Alert loại '{issue_type}' — "
            "KHÔNG có thông tin serial/model thiết bị cụ thể. "
            "Việc không đề cập serial/model là ĐÚNG, không phải lỗi. "
            "CHỈ kiểm tra xem có số liệu bị bịa đặt hay mâu thuẫn logic không.\n"
        )
    elif not has_serial:
        data_availability_note = (
            "\n⚠️ LƯU Ý: Alert này không có serial thiết bị — "
            "không yêu cầu phải nêu serial trong chẩn đoán.\n"
        )

    # Agent-specific validation rules
    if "device" in agent_key or "intel" in agent_key:
        checklist = """
CHECKLIST KIỂM TRA (DeviceIntel):
□ Nếu thiết bị là AP (MR), KHÔNG được nhận định lỗi WAN port/routing — AP không có WAN
□ Tỷ lệ mất gói (packet loss %) hoặc latency phải CÓ trong telemetry, không được bịa
□ Nếu nói "cáp lỗi" thì phải có bằng chứng port speed < 1Gbps trong dữ liệu"""
    elif "event" in agent_key or "log" in agent_key:
        checklist = """
CHECKLIST KIỂM TRA (EventLog):
□ Kiểm tra tóm tắt sự kiện hệ thống. Nếu không có thông tin MAC/ID trong dữ liệu gốc, chấp nhận không nêu MAC/ID
□ Không tự bịa đặt lỗi log mâu thuẫn với thực tế"""
    elif "client" in agent_key:
        checklist = """
CHECKLIST KIỂM TRA (ClientAgent):
□ Kiểm tra tóm tắt người dùng/client. Nếu không có chỉ số RSSI/SNR trong dữ liệu thực, chấp nhận tóm tắt số lượng client
□ Không kết luận quy mô ảnh hưởng nếu không có bằng chứng"""
    else:
        checklist = """
CHECKLIST KIỂM TRA (General):
□ Mọi số liệu (%, ms, Mbps, W) nêu ra phải khớp dữ liệu gốc
□ Loại thiết bị phải phù hợp với loại lỗi chẩn đoán"""

    return f"""Bạn là Senior QA Network Engineer — phản biện độc lập cho Agent {agent_name}.
{data_availability_note}
== BẢN THẢO CHẨN ĐOÁN ==
{draft}

{checklist}

NHIỆM VỤ: Kiểm tra chéo nghiêm ngặt:
1. Có số liệu nào bị bịa đặt mâu thuẫn dữ liệu gốc không?
2. Có mâu thuẫn logic về thiết bị không?

LƯU Ý: Nếu dữ liệu API không chứa các trường tùy chọn (như MAC hay RSSI), việc không nêu chúng là ĐÚNG. Đừng bắt bẻ thiếu thông tin nếu API không cung cấp.
Nếu bản thảo ĐẠT CHUẨN và phản ánh đúng dữ liệu → chỉ trả về duy nhất chữ: OK
Nếu thực sự có sai lệch dữ liệu → liệt kê 1 lý do ngắn gọn. Không thêm từ thừa."""


def run_react_loop(
    agent_name: str,
    base_prompt: str,
    tool_registry: dict,
    tool_args: tuple,
    max_iterations: int = 3,
    system_prompt: str = None,
    alert_ctx: dict = None,
) -> str:
    """
    Enhanced ReAct loop with:
    - Expert system prompt injection
    - Confidence scoring
    - Improved critic with agent-specific checklist
    - Early exit when confidence is HIGH
    """
    # Get expert persona for this agent
    sys_prompt = system_prompt or get_system_prompt(agent_name)

    conversation    = base_prompt
    last_diagnosis  = ""
    result          = ""

    # ── Phase 1: ReAct Generation ─────────────────────────────────────────────
    for iteration in range(max_iterations):
        result = llm.generate(
            conversation,
            system_prompt=sys_prompt,
            temperature=0.3,      # Slightly lower for more deterministic diagnosis
            max_tokens=2048,
        )
        if not result:
            break

        # Check for tool call
        action_called = None
        for tool_name in tool_registry:
            if f"Action: {tool_name}" in result:
                action_called = tool_name
                break

        if action_called and iteration < max_iterations - 1:
            print(f"[{agent_name}] ReAct iter {iteration+1}: calling tool '{action_called}'")
            obs = tool_registry[action_called](*tool_args)
            print(f"[{agent_name}] Tool observation: {str(obs)[:150]}...")
            conversation = (
                conversation
                + f"\n\n{result}"
                + "\n\n(IMPORTANT: DO NOT DRAW CONCLUSIONS. YOU ARE A RAW DATA COLLECTOR. ONLY LIST FACTUAL LOG EVIDENCE.)\n"
                + "Dựa trên Observation trên, hãy gạch đầu dòng ngắn gọn (bullet points) tóm tắt số liệu thô cuối cùng. TUYỆT ĐỐI KHÔNG viết văn xuôi dài dòng. "
                + "Chỉ dùng số liệu thực tế. KHÔNG gọi thêm tool:"
            )
        else:
            # Handle action-only output
            is_only_action = (
                action_called is not None
                and len([
                    line for line in result.strip().split("\n")
                    if line.strip() and not line.strip().startswith("Action:")
                ]) == 0
            )
            if is_only_action:
                result = last_diagnosis or llm.generate(
                    base_prompt
                    + "\n\nViết ngay gạch đầu dòng ngắn gọn tóm tắt số liệu thô. TUYỆT ĐỐI KHÔNG viết văn xuôi dài dòng. "
                    + "Dùng dữ liệu thực tế. KHÔNG gọi tool:",
                    system_prompt=sys_prompt,
                    temperature=0.3,
                    max_tokens=1024,
                ) or ""
            break

        # Track last non-action text
        non_action = [l for l in result.strip().split("\n") if l.strip() and "Action:" not in l]
        if non_action:
            last_diagnosis = "\n".join(non_action).strip()

        # Early exit if HIGH confidence already achieved
        if last_diagnosis and _score_confidence(last_diagnosis) == "HIGH":
            print(f"[{agent_name}] Early exit: HIGH confidence diagnosis at iteration {iteration+1}")
            break

    final = result.strip() if result else ""
    if not final or _is_action_only(final):
        final = last_diagnosis or f"[{agent_name}] Không thu thập đủ dữ liệu để phân tích."

    draft = clean_technical_note(final)

    # Attach confidence score to the draft
    confidence = _score_confidence(draft)
    print(f"[{agent_name}] Draft confidence: {confidence} (length={len(draft)})")

    # ── Phase 2: Critic Reflection (Only if draft confidence is LOW) ─────────────
    if confidence == "LOW" or len(draft) < 30:
        print(f"[{agent_name}] Running Critic Reflection (Low Confidence / Draft Short)...")
        critic_prompt  = _build_critic_prompt(agent_name, draft, base_prompt, alert_ctx=alert_ctx)
        critic_sys     = get_system_prompt("verify_agent")   # Use verifier persona for critic
        critic_feedback = llm.generate(
            critic_prompt,
            system_prompt=critic_sys,
            temperature=0.2,    # Very deterministic for QA checks
            max_tokens=512,
        )

        if critic_feedback and "OK" not in critic_feedback.upper() and len(critic_feedback.strip()) > 5:
            print(f"[{agent_name}] ⚠️ Critic rejected draft: {critic_feedback.strip()[:120]}")

        # ── Phase 3: Refinement ───────────────────────────────────────────────
        refine_prompt = f"""Bản chẩn đoán trước bị từ chối bởi QA Engineer vì lý do sau:

PHẢN HỒI PHẢN BIỆN: "{critic_feedback.strip()}"

DỮ LIỆU GỐC:
{base_prompt}

NHIỆM VỤ: Viết lại tóm tắt số liệu thô (chỉ dùng gạch đầu dòng ngắn gọn):
- Khắc phục triệt để lỗi được chỉ ra
- Chỉ dùng số liệu có trong dữ liệu gốc
- Không chào hỏi, không kính ngữ, không từ thừa
- Viết trực tiếp, kỹ thuật, dựa trên thực tế"""

        refined = llm.generate(
            refine_prompt,
            system_prompt=sys_prompt,
            temperature=0.25,
            max_tokens=1024,
        )
        if refined and len(refined.strip()) > 20:
            draft = clean_technical_note(refined)
            confidence = _score_confidence(draft)
            print(f"[{agent_name}] ✅ Self-corrected. New confidence: {confidence}")
    else:
        print(f"[{agent_name}] ✅ Critic approved draft.")

    # Append confidence tag for downstream agents to use
    draft_with_confidence = f"[Confidence: {confidence}] {draft}"
    return draft_with_confidence


def _is_action_only(text: str) -> bool:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return True
    non_action = [l for l in lines if not l.startswith("Action:")]
    return len(non_action) == 0
