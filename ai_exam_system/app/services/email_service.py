"""
services/email_service.py
Email delivery service for verification codes, password resets, and notifications.

Primary:  Resend API (HTTPS-based, works on Render free tier)
Fallback: SMTP (Gmail, SendGrid, etc.) if RESEND_API_KEY not set
Dev mode: Logs OTP to console and returns dev_otp in response if neither configured
"""

import os
import sys
import logging
from typing import Dict, Any
from fastapi import HTTPException
from email_validator import validate_email, EmailNotValidError

logger = logging.getLogger(__name__)

# List of known temporary/disposable burner domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "throwawaymail.com", "yopmail.com", "sharklasers.com", "dispostable.com",
    "trashmail.com", "getairmail.com", "mohmal.com", "fakeinbox.com",
    "temp-mail.org", "10minutesmail.com", "burnermail.io", "trashmail.net",
}

# ---------------------------------------------------------------------------
# Known email aliases mapping alternate addresses to their canonical account email
# ---------------------------------------------------------------------------
def _load_email_aliases() -> Dict[str, str]:
    import json
    aliases = {
        "sahil47947@gmail.com": "sahilagarwal1691@gmail.com",
    }
    env_aliases = os.getenv("EMAIL_ALIASES_JSON", "")
    if env_aliases:
        try:
            extra = json.loads(env_aliases)
            if isinstance(extra, dict):
                for k, v in extra.items():
                    aliases[str(k).strip().lower()] = str(v).strip().lower()
        except Exception:
            pass
    return aliases

EMAIL_ALIASES = _load_email_aliases()

def canonicalize_email(raw_email: str) -> str:
    """
    Normalizes an email address and resolves known alias accounts to their single
    canonical address.
    For example:
        sahil47947@gmail.com -> sahilagarwal1691@gmail.com
    Ensures single profile, session records, and authentication across aliases.
    """
    clean = str(raw_email or "").strip().lower()
    return EMAIL_ALIASES.get(clean, clean)

def validate_candidate_email(raw_email: str) -> str:
    """
    Validates that an email actually exists:
    1. Checks syntax according to RFC standards.
    2. Blocks temporary / burner / disposable email domains.
    3. Performs DNS MX lookup to ensure the domain actually exists and accepts email.
    """
    clean = str(raw_email or "").strip().lower()
    if not clean or "@" not in clean:
        raise HTTPException(status_code=400, detail="Invalid email address format. Please enter a valid email address.")

    domain = clean.split("@")[-1]
    if domain in DISPOSABLE_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail="Temporary and disposable email addresses are not allowed. Please enter your real, permanent email address."
        )

    # Allow mock domains in automated unit test environment
    is_testing = "pytest" in sys.modules or os.getenv("ENVIRONMENT") == "testing"
    check_dns = not (is_testing and domain in ("example.com", "test.com", "test.invalid"))

    try:
        validated = validate_email(clean, check_deliverability=check_dns)
        return validated.normalized
    except EmailNotValidError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid email address: {str(exc)}. Please verify your email and try again."
        )

# ---------------------------------------------------------------------------
# Email HTML template
# ---------------------------------------------------------------------------

def _build_html(user_name: str, otp_code: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Password Reset Code</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; margin: 0; padding: 24px; color: #111827;">
  <div style="max-width: 520px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="text-align: center; margin-bottom: 24px;">
      <h1 style="font-size: 24px; font-weight: bold; color: #1d4ed8; margin: 0;">Intelligent Exam Portal</h1>
      <p style="color: #6b7280; font-size: 14px; margin-top: 4px;">Academic &amp; Adaptive Examination System</p>
    </div>

    <p style="font-size: 16px; line-height: 24px; margin-bottom: 16px;">
      Hello <strong>{user_name}</strong>,
    </p>

    <p style="font-size: 15px; line-height: 22px; color: #374151; margin-bottom: 24px;">
      We received a request to reset your password. Use the verification code below to proceed:
    </p>

    <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
      <span style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #1e40af; font-family: monospace;">
        {otp_code}
      </span>
      <p style="margin: 8px 0 0 0; font-size: 13px; color: #6b7280;">
        Valid for <strong>10 minutes</strong>
      </p>
    </div>

    <p style="font-size: 14px; line-height: 20px; color: #4b5563; margin-bottom: 24px;">
      If you did not request this password reset, please disregard this email. Your current password remains completely unchanged.
    </p>

    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;" />

    <p style="font-size: 12px; color: #9ca3af; text-align: center; margin: 0;">
      This is an automated system email. Please do not reply directly to this message.
    </p>
  </div>
</body>
</html>"""


def _build_plain(user_name: str, otp_code: str) -> str:
    return f"""Hello {user_name},

You requested to reset your password for your Intelligent Exam Portal account.
Your 6-digit verification code is:

    {otp_code}

This code is valid for 10 minutes.

If you did not request a password reset, please ignore this email. Your account remains secure.

Best regards,
Intelligent Exam Portal Team
"""


# ---------------------------------------------------------------------------
# Brevo delivery (primary — HTTPS API, works on Render free tier, no domain needed)
# ---------------------------------------------------------------------------

def _send_via_brevo(to_email: str, otp_code: str, user_name: str) -> Dict[str, Any]:
    import httpx  # already in requirements

    api_key   = os.getenv("BREVO_API_KEY", "").strip()
    from_email = os.getenv("BREVO_FROM_EMAIL", os.getenv("SMTP_FROM_EMAIL", "sahilagarwal1691@gmail.com")).strip()
    subject   = f"Your Password Reset Code: {otp_code} - Intelligent Exam Portal"

    payload = {
        "sender": {"name": "Intelligent Exam Portal", "email": from_email},
        "to": [{"email": to_email, "name": user_name}],
        "subject": subject,
        "htmlContent": _build_html(user_name, otp_code),
        "textContent": _build_plain(user_name, otp_code),
    }

    response = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=15.0,
    )
    response.raise_for_status()
    logger.info("Password reset OTP email delivered via Brevo to %s", to_email)
    return {
        "success": True,
        "delivered": True,
        "mode": "brevo",
        "message": "Verification code email sent successfully.",
    }


# ---------------------------------------------------------------------------
# Resend delivery (secondary fallback)
# ---------------------------------------------------------------------------

def _send_via_resend(to_email: str, otp_code: str, user_name: str) -> Dict[str, Any]:
    import resend  # pip install resend

    resend.api_key = os.getenv("RESEND_API_KEY", "")
    subject = f"Your Password Reset Code: {otp_code} - Intelligent Exam Portal"

    params = {
        "from": "Intelligent Exam Portal <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "html": _build_html(user_name, otp_code),
        "text": _build_plain(user_name, otp_code),
    }

    response = resend.Emails.send(params)
    logger.info("Password reset OTP email delivered via Resend to %s (id=%s)", to_email, response.get("id"))
    return {
        "success": True,
        "delivered": True,
        "mode": "resend",
        "message": "Verification code email sent successfully.",
    }


# ---------------------------------------------------------------------------
# SMTP delivery (fallback)
# ---------------------------------------------------------------------------

def _send_via_smtp(to_email: str, otp_code: str, user_name: str) -> Dict[str, Any]:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_host     = os.getenv("SMTP_HOST", "").strip()
    smtp_port     = int(os.getenv("SMTP_PORT", "587").strip())
    smtp_user     = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from     = os.getenv("SMTP_FROM_EMAIL", smtp_user).strip()
    smtp_use_tls  = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    smtp_use_ssl  = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")

    subject = f"Your Password Reset Code: {otp_code} - Intelligent Exam Portal"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_from
    msg["To"]      = to_email
    msg.attach(MIMEText(_build_plain(user_name, otp_code), "plain", "utf-8"))
    msg.attach(MIMEText(_build_html(user_name, otp_code),  "html",  "utf-8"))

    if smtp_use_ssl or smtp_port == 465:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12.0)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=12.0)
        if smtp_use_tls:
            server.starttls()

    server.login(smtp_user, smtp_password)
    server.send_message(msg)
    server.quit()

    logger.info("Password reset OTP email delivered via SMTP to %s", to_email)
    return {
        "success": True,
        "delivered": True,
        "mode": "smtp",
        "message": "Verification code email sent successfully.",
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def send_password_reset_otp_email(to_email: str, otp_code: str, user_name: str = "Student") -> Dict[str, Any]:
    """
    Send a 6-digit OTP for password reset.

    Priority:
      1. Resend API  (RESEND_API_KEY env var)
      2. SMTP        (SMTP_HOST + SMTP_USER + SMTP_PASSWORD env vars)
      3. Dev fallback (logs OTP, returns dev_otp in response)
    """
    brevo_key   = os.getenv("BREVO_API_KEY", "").strip()
    resend_key  = os.getenv("RESEND_API_KEY", "").strip()
    smtp_host   = os.getenv("SMTP_HOST", "").strip()
    smtp_user   = os.getenv("SMTP_USER", "").strip()
    smtp_pass   = os.getenv("SMTP_PASSWORD", "").strip()

    # --- 1. Try Brevo (recommended — no domain needed) ---
    if brevo_key:
        try:
            return _send_via_brevo(to_email, otp_code, user_name)
        except Exception as exc:
            logger.error("Brevo delivery failed for %s: %s", to_email, exc)
            return {
                "success": False,
                "delivered": False,
                "mode": "error",
                "error": str(exc),
                "message": "Failed to send verification email via Brevo.",
            }

    # --- 2. Try Resend ---
    if resend_key:
        try:
            return _send_via_resend(to_email, otp_code, user_name)
        except Exception as exc:
            logger.error("Resend delivery failed for %s: %s", to_email, exc)
            return {
                "success": False,
                "delivered": False,
                "mode": "error",
                "error": str(exc),
                "message": "Failed to send verification email via Resend.",
            }

    # --- 3. Try SMTP ---
    if smtp_host and smtp_user and smtp_pass:
        try:
            return _send_via_smtp(to_email, otp_code, user_name)
        except Exception as exc:
            logger.error("Failed to send OTP email via SMTP to %s: %s", to_email, exc)
            return {
                "success": False,
                "delivered": False,
                "mode": "error",
                "error": str(exc),
                "message": "Failed to send verification email. Please check server SMTP configuration.",
            }

    # --- 3. Dev fallback ---
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    logger.warning(
        "[EMAIL SERVICE - DEV/FALLBACK] No email provider configured. "
        "Password Reset OTP for %s: [%s] (expires in 10 min). "
        "Set RESEND_API_KEY (recommended) or SMTP_* vars to send real emails.",
        to_email, otp_code,
    )
    return {
        "success": True,
        "delivered": False,
        "mode": "simulated",
        "message": "Verification code generated. (No email provider configured; code logged to server logs)",
        "dev_otp": otp_code if not is_production else None,
    }
