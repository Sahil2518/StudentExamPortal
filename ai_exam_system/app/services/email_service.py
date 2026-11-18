"""
services/email_service.py
Email delivery service for verification codes, password resets, and notifications.

Supports standard SMTP providers (Gmail, SendGrid, Amazon SES, Mailgun, Outlook, etc.).
If SMTP credentials are not configured in the environment, logs the verification code
prominently to the server logs and returns simulated delivery status without crashing.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any

logger = logging.getLogger(__name__)


def send_password_reset_otp_email(to_email: str, otp_code: str, user_name: str = "Student") -> Dict[str, Any]:
    """
    Sends a 6-digit OTP verification code for password reset.
    
    If SMTP credentials are provided in environment:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL
    delivers via SMTP.
    
    Otherwise:
      Logs the OTP clearly to server console for testing/development.
    """
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_str = os.getenv("SMTP_PORT", "587").strip()
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_user or "noreply@examportal.com").strip()
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    smtp_use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        smtp_port = 587

    # Check if SMTP is configured
    if not (smtp_host and smtp_user and smtp_password):
        logger.warning(
            "[EMAIL SERVICE - DEV/FALLBACK] SMTP is not configured in .env. "
            "Generated Password Reset OTP for %s is: [%s] (Expires in 10 minutes). "
            "To send real emails, set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD in .env.",
            to_email, otp_code
        )
        return {
            "success": True,
            "delivered": False,
            "mode": "simulated",
            "message": "Verification code generated. (SMTP not configured on server; code logged to server logs)",
            "dev_otp": otp_code if os.getenv("ENVIRONMENT", "development").lower() != "production" else None
        }

    # Prepare Email Content
    subject = f"Your Password Reset Code: {otp_code} - Intelligent Exam Portal"

    plain_text = f"""Hello {user_name},

You requested to reset your password for your Intelligent Exam Portal account.
Your 6-digit verification code is:

    {otp_code}

This code is valid for 10 minutes.

If you did not request a password reset, please ignore this email. Your account remains secure.

Best regards,
Intelligent Exam Portal Team
"""

    html_content = f"""<!DOCTYPE html>
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
      We received a request to reset your password. Use the verification code below to proceed with setting a new password:
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
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        if smtp_use_ssl or smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12.0)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=12.0)
            if smtp_use_tls:
                server.starttls()

        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        logger.info("Password reset OTP email delivered to %s", to_email)
        return {
            "success": True,
            "delivered": True,
            "mode": "smtp",
            "message": "Verification code email sent successfully."
        }
    except Exception as exc:
        logger.error("Failed to send OTP email via SMTP to %s: %s", to_email, exc)
        return {
            "success": False,
            "delivered": False,
            "mode": "error",
            "error": str(exc),
            "message": "Failed to send verification email. Please check server SMTP configuration."
        }
