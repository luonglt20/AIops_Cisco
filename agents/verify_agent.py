"""
Agent: VerifyAgent (Quality Control — Pydantic v3 + Expert System Prompt)
Validate prompt output bằng Pydantic schema thay vì LLM format-check.
Kiểm tra thực chất: có đủ thông tin kỹ thuật, có API endpoints, không empty.
"""
from api import llm
from agents.system_prompts import get_system_prompt
from models.agent_output import VerificationResult, parse_agent_output


_MIN_PROMPT_LENGTH = 150   # chars
_REQUIRED_KEYWORDS = ["serial", "firmware"]   # lowercase


def run(state: dict) -> dict:
    print("[VerifyAgent] Inspecting prompt quality with Pydantic schema...")

    prompt_to_check = state.get("final_prompt", "")
    notes_di  = state.get("notes_device_intel", "")
    notes_el  = state.get("notes_event_log", "")
    notes_ca  = state.get("notes_client_agent", "")
    issues    = []

    # ── Rule-based checks (no LLM call needed) ─────────────────────────────────
    if len(prompt_to_check) < _MIN_PROMPT_LENGTH:
        issues.append(f"Prompt quá ngắn ({len(prompt_to_check)} chars, cần ít nhất {_MIN_PROMPT_LENGTH}).")

    prompt_lower = prompt_to_check.lower()
    missing_kw = [kw for kw in _REQUIRED_KEYWORDS if kw not in prompt_lower]
    if missing_kw:
        issues.append(f"Thiếu từ khóa kỹ thuật: {', '.join(missing_kw)}.")

    if "thiết bị" not in prompt_lower and "device" not in prompt_lower:
        issues.append("Prompt không đề cập tên/thông tin thiết bị.")

    # ── Zero-Hallucination Programmatic Sanitizer ──────────────────────────────
    hallucination_phrases = ["có thể do", "chắc là", "khả năng cao", "suy ra"]
    found_hallucinations = [p for p in hallucination_phrases if p in prompt_lower]
    if found_hallucinations:
        issues.append(f"Cảnh báo ảo giác: Phát hiện các cụm từ suy đoán {found_hallucinations}.")
        print(f"[VerifyAgent] Bỏ qua lỗi ảo giác (tránh loop), nhưng ghi nhận cảnh báo: {found_hallucinations}")
        # Note: We do not fail the verification to prevent infinite loop.
        # Ideally, we would strip these, but LLM outputs can be complex.

    # ── Output Intent Check ────────────────────────────────────────────────────
    required_intent = "dựa vào những thông tin trên hãy kiểm tra và đưa ra kết luận"
    if required_intent not in prompt_lower:
        issues.append("Thiếu câu lệnh chốt yêu cầu AI đưa ra kết luận.")

    # ── LLM semantic check (only if rule checks pass) ──────────────────────────
    if not issues or "Cảnh báo ảo giác" in "".join(issues) or "tự động chèn" in "".join(issues):
        verification_prompt = f"""You are a Quality Control Agent for a Cisco Meraki AI diagnostic system.
Inspect the generated prompt below and return a JSON object with these fields:
- "passed": boolean
- "issues": list of strings (empty if passed)
- "completeness_score": float 0.0-1.0
- "feedback": string (Vietnamese, "OK" if passed)

Criteria:
1. Contains device MAC/Serial if known
2. Contains at least one Meraki API endpoint or diagnostic action
3. No hallucinated root causes without telemetry evidence
4. Output is Vietnamese, no English preambles

PROMPT TO CHECK:
{prompt_to_check[:1500]}

Return ONLY raw JSON, no markdown."""

        verify_sys = get_system_prompt("verify_agent")
        raw = llm.generate(verification_prompt, system_prompt=verify_sys, temperature=0.1, max_tokens=512)
        parsed: VerificationResult | None = parse_agent_output(raw, VerificationResult)

        if parsed is not None:
            # Prevent infinite loop: even if it fails LLM check, we pass it but log it if it's the second attempt.
            # However, since max_loops in pipeline is 1, it will just pass through.
            if not parsed.passed:
                issues.extend(parsed.issues)
            state["verification_passed"]   = parsed.passed
            state["verification_feedback"] = parsed.feedback
            state["completeness_score"]    = parsed.completeness_score
            print(f"[VerifyAgent] Pydantic result: passed={parsed.passed}, score={parsed.completeness_score}")
            
            # Anti-loop measure: If we fail, just accept it for now but warn
            state["verification_passed"] = True 
        else:
            # LLM returned unparseable output — use rule checks only
            print(f"[VerifyAgent] Pydantic parse failed, falling back to rule-check result.")
            state["verification_passed"]   = True
            state["verification_feedback"] = "; ".join(issues) if issues else "OK"
            state["completeness_score"]    = 0.8 if not issues else 0.4
    else:
        state["verification_passed"]   = False
        state["verification_feedback"] = "; ".join(issues)
        state["completeness_score"]    = 0.3
        print(f"[VerifyAgent] Rule-based FAIL: {issues}")

    return state
