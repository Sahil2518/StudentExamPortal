"""
services/ai_assistant_service.py
Omnipresent AI Assistant, Doubt Solver & Exam Integrity Proctor Service.

Dual Core Capabilities:
1. Malpractice & Exam Activity Monitor:
   - Tracks real-time exam telemetry (tab switches, focus loss, rapid guessing, camera state).
   - Enforces an Academic Integrity Shield during live entrance exams (blocks ABCD answer leakage,
     issues formal proctoring warnings, and logs malpractice attempts to session telemetry).
2. Doubt Solver & Pedagogical Guide:
   - Solves academic doubts before, during practice, and after exams.
   - Generates step-by-step derivations with rich LaTeX math ($...$ and $$...$$).
   - Diagnoses student misconceptions from their test results and MIRT cognitive ability vectors.
   - Provides portal guidance (CAT adaptive algorithm, marking schemes, review queues).
"""

import os
import re
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cheating / Malpractice Detection Heuristics
# ---------------------------------------------------------------------------

CHEAT_PATTERNS = [
    r"\b(what is|tell me|give me|show me)\s+(the\s+)?(correct\s+)?(answer|option)\b",
    r"\b(is it|which option|which one is)\s+(a|b|c|d|option a|option b|option c|option d)\b",
    r"\b(option\s+[a-d]|opt\s+[a-d])\s*(is correct|\?)\b",
    r"\b(solve this question|solve it for me and give answer)\b",
    r"\b(tell me whether a or b|is the answer a|is the answer b|is the answer c|is the answer d)\b",
    r"\b(cheat|bypass proctor|leak answer|hack exam)\b",
]

COMPILED_CHEAT_REGEX = [re.compile(p, re.IGNORECASE) for p in CHEAT_PATTERNS]


def detect_cheat_attempt(message: str) -> bool:
    """Detect if student is attempting to extract the direct answer during a live exam."""
    msg = message.strip().lower()
    return any(regex.search(msg) for regex in COMPILED_CHEAT_REGEX)


# ---------------------------------------------------------------------------
# Built-in Offline Expert Knowledge Base (Instant Fallback)
# ---------------------------------------------------------------------------

OFFLINE_KNOWLEDGE = {
    "marking": (
        "### 🏛️ Standardized Entrance Exam Marking Scheme\n\n"
        "- **Correct Answer:** $+4$ marks\n"
        "- **Incorrect Answer:** $-1$ mark (negative marking penalty)\n"
        "- **Unanswered / Marked for Review without answer:** $0$ marks\n\n"
        "**Strategic Advice:** Never blind-guess on $+4/-1$ papers unless you can eliminate at least 2 options, "
        "as the expected value of random guessing on a 4-option question is negative ($-0.25$ marks per guess)."
    ),
    "malpractice": (
        "### 🛡️ Examination Malpractice & Integrity Guidelines\n\n"
        "1. **Full-Screen Compliance:** Tab switches (`visibilitychange`) and focus losses (`blur`) are logged.\n"
        "2. **Continuous Webcam Proctoring:** Camera must remain unobstructed with a single candidate visible.\n"
        "3. **Rapid Guess Telemetry:** Answering questions in under $3$ seconds triggers telemetry flags.\n"
        "4. **Academic Integrity Shield:** AI Assistant is strictly barred from leaking live exam answers. Attempting to elicit answers is recorded as an integrity event."
    ),
    "mirt": (
        "### 🧠 Multidimensional IRT (MIRT) 3D Ability Profile\n\n"
        "Instead of a flat percentage score, MIRT estimates your ability across three orthogonal cognitive dimensions:\n\n"
        "- **$\\theta_{conceptual}$ (Conceptual Understanding):** Grasp of fundamental laws, principles, and theoretical foundations.\n"
        "- **$\\theta_{numerical}$ (Numerical Problem-Solving):** Calculation accuracy, formula application, and quantitative speed.\n"
        "- **$\\theta_{analytical}$ (Analytical Reasoning):** Multi-concept synthesis, derivation logic, and boundary condition evaluation.\n\n"
        "Scores are standard normal logits centered at $0.0$. Scores $> +1.0$ represent competitive percentiles ($>84\\text{th}$ percentile)."
    ),
    "cat": (
        "### 🎯 Thompson Sampling Computerized Adaptive Testing (CAT)\n\n"
        "Our practice exams use **Bayesian Multi-Armed Bandit Thompson Sampling** combined with **Bayesian Knowledge Tracing (BKT)**. "
        "Each question difficulty is chosen dynamically to maximize information gain around your current skill mastery threshold."
    )
}


# ---------------------------------------------------------------------------
# LLM Core Dispatcher
# ---------------------------------------------------------------------------

def generate_ai_response(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Generate an AI Assistant response considering exam state, proctoring guards, and pedagogical goals.

    Returns:
        {
            "response": str (markdown with KaTeX math delimiters),
            "mode": str ("malpractice_shield" | "doubt_solver" | "exam_guide"),
            "integrity_flag": bool,
            "proactive_tip": Optional[str],
            "provider": str
        }
    """
    ctx = context or {}
    route = str(ctx.get("route", ""))
    exam_type = str(ctx.get("exam_type", ""))
    is_live_exam = (exam_type == "live" or "/exam/session" in route) and not ctx.get("is_finished", False)

    # 1. LIVE EXAM INTEGRITY SHIELD CHECK
    if is_live_exam and detect_cheat_attempt(user_message):
        logger.warning("Academic Integrity Shield triggered for live exam query: '%s'", user_message[:80])
        return {
            "response": (
                "### 🛡️ Academic Integrity Notice\n\n"
                "> [!WARNING]\n"
                "> **Live Examination Active:** You are currently taking a standardized competitive entrance examination.\n\n"
                "In strict compliance with examination protocol, revealing direct solutions, option letters ($A, B, C, D$), "
                "or verifying answer keys is **prohibited** and logged in your session's integrity audit trail.\n\n"
                "**What I CAN help you with right now:**\n"
                "- Clarifying definitions of scientific terms (e.g. *adiabatic*, *moment of inertia*, *electronegativity*)\n"
                "- Reviewing exam navigation, marking scheme ($+4 / -1$), and time-budgeting strategy\n"
                "- General exam relaxation & focus techniques\n\n"
                "Please specify which scientific concept or exam rule you would like clarified."
            ),
            "mode": "malpractice_shield",
            "integrity_flag": True,
            "proactive_tip": "Maintain focus on the question scenario. Eliminate clearly incorrect extremes first.",
            "provider": "integrity_guard"
        }

    # 2. DETERMINE SYSTEM PROMPT BASED ON ROUTE & CONTEXT
    if is_live_exam:
        system_prompt = (
            "You are Aura, an official Exam Proctor and Academic Integrity Guide for a live standardized examination. "
            "The candidate is actively taking a timed test.\n"
            "CRITICAL SECURITY MANDATE:\n"
            "1. NEVER reveal the correct answer, option letters (A, B, C, D), or exact numerical solutions to any question.\n"
            "2. If asked about the active question, you may ONLY clarify general terminology, explain official scientific definitions, "
            "or guide the student's thinking socratically without solving the question.\n"
            "3. Remind the candidate of time limits and the +4 / -1 negative marking penalty when appropriate.\n"
            "4. Use LaTeX notation ($...$ inline, $$...$$ block) for all scientific equations.\n"
            "5. Keep responses concise, objective, and professional."
        )
        current_mode = "exam_guide"
    else:
        system_prompt = (
            "You are Aura, an elite AI Academic Mentor, Doubt Solver, and Entrance Exam Coach for competitive examinations "
            "(JEE, NEET, CAT, GATE, SAT, UPSC). You guide students before, during practice, and after exams.\n\n"
            "TEACHING GUIDELINES:\n"
            "1. Thorough Doubt Resolution: Provide clear, structured, step-by-step mathematical and conceptual derivations.\n"
            "2. Rich LaTeX Math: Format ALL equations, formulas, variables, and units using LaTeX: "
            "$...$ for inline math (e.g. $E = \\frac{1}{2}mv^2$, $PV = nRT$, $pH = -\\log_{10}[H^+]$) "
            "and $$...$$ for standalone display equations.\n"
            "3. Misconception Diagnosis: If the student asks why an answer was wrong, explain the exact mathematical or conceptual trap "
            "in the distractors and how to avoid it.\n"
            "4. Multidimensional Intelligence: Relate advice to cognitive dimensions: conceptual mastery, numerical problem-solving, "
            "and analytical synthesis.\n"
            "5. Encouraging & Rigorous: Be warm, rigorous, and intellectually inspiring."
        )
        current_mode = "doubt_solver"

    # Assemble contextual context block
    context_notes = []
    if ctx.get("domain"):
        context_notes.append(f"Domain / Subject: {ctx['domain']}")
    if ctx.get("skill"):
        context_notes.append(f"Topic / Skill: {ctx['skill']}")
    if ctx.get("active_question_text"):
        context_notes.append(f"Current Question Text: {ctx['active_question_text']}")
    if ctx.get("options") and not is_live_exam:
        context_notes.append(f"Question Options: {ctx['options']}")
    if ctx.get("selected_answer"):
        context_notes.append(f"Student Selected: {ctx['selected_answer']}")
    if ctx.get("correct_answer") and not is_live_exam:
        context_notes.append(f"Correct Answer: {ctx['correct_answer']}")
    if ctx.get("explanation") and not is_live_exam:
        context_notes.append(f"Stored Question Explanation: {ctx['explanation']}")
    if ctx.get("mirt_theta"):
        context_notes.append(f"Student MIRT Ability Vector: {ctx['mirt_theta']}")
    if ctx.get("fatigue_detected"):
        context_notes.append("Cognitive Fatigue Alert: Student showed accuracy decline in final third of exam.")

    context_str = "\n".join(context_notes) if context_notes else "General portal browsing"

    user_full_prompt = (
        f"Active Session Context:\n{context_str}\n\n"
        f"Student Query: {user_message}"
    )

    # 3. CALL LLM (Groq -> Gemini -> Fallback)
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    providers = []
    if groq_key:
        providers.append(("Groq-Qwen", "https://api.groq.com/openai/v1/chat/completions", groq_key, "qwen/qwen3.8-27b"))
        providers.append(("Groq-GPT-OSS", "https://api.groq.com/openai/v1/chat/completions", groq_key, "openai/gpt-oss-20b"))
        providers.append(("Groq-Advanced", "https://api.groq.com/openai/v1/chat/completions", groq_key, "openai/gpt-oss-120b"))
    if openai_key:
        providers.append(("OpenAI", "https://api.openai.com/v1/chat/completions", openai_key, "gpt-4o-mini"))

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history[-6:]:  # Keep recent history
            r = item.get("role")
            c = item.get("content")
            if r in ("user", "assistant") and c:
                messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": user_full_prompt})

    for prov_name, api_url, api_key, model_name in providers:
        try:
            with httpx.Client(timeout=12.0) as client:
                res = client.post(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.4,
                        "max_tokens": 800
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    ans = data["choices"][0]["message"]["content"].strip()
                    logger.info("Aura assistant answered query via %s (%s)", prov_name, model_name)
                    return {
                        "response": ans,
                        "mode": current_mode,
                        "integrity_flag": False,
                        "proactive_tip": None,
                        "provider": prov_name
                    }
                else:
                    logger.warning("Provider %s returned status %s: %s", prov_name, res.status_code, res.text[:100])
        except Exception as exc:
            logger.warning("Call to provider %s failed: %s", prov_name, exc)

    # 4. FALLBACK RESOLUTION
    low_msg = user_message.lower()
    fallback_response = None
    for keyword, text in OFFLINE_KNOWLEDGE.items():
        if keyword in low_msg:
            fallback_response = text
            break

    if not fallback_response:
        if is_live_exam:
            fallback_response = (
                "### ℹ️ Live Examination Guidance\n\n"
                "You are currently taking a timed entrance examination.\n"
                "- Keep an eye on the countdown timer at the top-right.\n"
                "- Review marked questions using the Question Palette.\n"
                "- Each incorrect answer costs $-1$ mark, while a correct answer yields $+4$ marks.\n"
                "Take a deep breath and work through the calculations steadily!"
            )
        else:
            fallback_response = (
                f"### 💡 Doubt Resolution & Concept Review\n\n"
                f"Thank you for asking about **'{user_message}'**.\n\n"
                "To master this concept for competitive exams:\n"
                "1. **Core Law:** Identify the fundamental governing principle or conservation equation.\n"
                "2. **Mathematical Formulation:** Write out the standard formula with all units clearly defined.\n"
                "3. **Boundary Conditions:** Test extreme limits (e.g., $t \\to 0$, $v \\to c$, or $x \\to \\infty$).\n\n"
                "Would you like to practice a targeted question on this topic or explore a step-by-step worked example?"
            )

    return {
        "response": fallback_response,
        "mode": current_mode,
        "integrity_flag": False,
        "proactive_tip": "Review your MIRT cognitive breakdown after submitting to see your conceptual vs numerical rating.",
        "provider": "offline_knowledge_engine"
    }


# ---------------------------------------------------------------------------
# Proctoring & Malpractice Telemetry Calculator
# ---------------------------------------------------------------------------

def calculate_integrity_score(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute a candidate integrity trust score (0-100%) and malpractice breakdown
    from session proctoring telemetry events.
    """
    score = 100
    tab_switches = 0
    focus_losses = 0
    camera_blocked = 0
    cheat_attempts = 0
    clipboard_pastes = 0

    timeline = []
    for ev in events:
        etype = ev.get("event_type", "")
        occurred = ev.get("occurred_at") or ev.get("created_at")
        time_str = occurred.isoformat() if hasattr(occurred, "isoformat") else str(occurred or "")

        if etype == "tab_switch":
            tab_switches += 1
            score -= 10
            timeline.append({"type": "tab_switch", "label": "Switched browser tab / window", "time": time_str, "severity": "medium"})
        elif etype == "focus_lost":
            focus_losses += 1
            score -= 4
            timeline.append({"type": "focus_lost", "label": "Window focus lost", "time": time_str, "severity": "low"})
        elif etype == "camera_blocked":
            camera_blocked += 1
            score -= 15
            timeline.append({"type": "camera_blocked", "label": "Webcam stream lost or blocked", "time": time_str, "severity": "high"})
        elif etype == "assistant_cheat_attempt":
            cheat_attempts += 1
            score -= 20
            timeline.append({"type": "cheat_attempt", "label": "Attempted live answer retrieval", "time": time_str, "severity": "high"})
        elif etype == "clipboard_paste":
            clipboard_pastes += 1
            score -= 8
            timeline.append({"type": "paste", "label": "Clipboard paste detected", "time": time_str, "severity": "medium"})

    score = max(0, min(100, score))

    if score >= 90:
        verdict = "clean"
        status_label = "Clean & Verified"
        status_color = "green"
    elif score >= 70:
        verdict = "caution"
        status_label = "Caution: Minor Anomalies"
        status_color = "yellow"
    else:
        verdict = "flagged"
        status_label = "Flagged for Reviewer Audit"
        status_color = "red"

    return {
        "integrity_score": score,
        "verdict": verdict,
        "status_label": status_label,
        "status_color": status_color,
        "breakdown": {
            "tab_switches": tab_switches,
            "focus_losses": focus_losses,
            "camera_blocked": camera_blocked,
            "cheat_attempts": cheat_attempts,
            "clipboard_pastes": clipboard_pastes,
            "total_incidents": tab_switches + focus_losses + camera_blocked + cheat_attempts + clipboard_pastes
        },
        "recent_incidents": timeline[-10:]  # Last 10 incidents
    }
