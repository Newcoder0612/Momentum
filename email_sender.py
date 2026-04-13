"""
email_sender.py
───────────────
Handles sending emails via Gmail's SMTP server.

SMTP = Simple Mail Transfer Protocol
     = the standard language computers use to send emails to each other

Think of it like a post office:
  - Your Gmail account = your return address
  - smtplib = the postal worker who delivers the letter
  - smtp.gmail.com:587 = the post office building
  - TLS encryption = a sealed envelope (nobody can read it in transit)
"""

import smtplib
import os
from email.mime.text        import MIMEText
from email.mime.multipart   import MIMEMultipart

# ── These come from environment variables (safer than hardcoding) ──────────────
# Set these in your terminal before running the server:
#   Windows:  set GMAIL_USER=you@gmail.com
#             set GMAIL_PASS=your-app-password
#   Mac/Linux: export GMAIL_USER=you@gmail.com
#              export GMAIL_PASS=your-app-password
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "")  # Gmail App Password, NOT your real password


def send_reset_email(to_email: str, username: str, reset_link: str) -> bool:
    """
    Sends a password reset email.
    Returns True if sent successfully, False if it failed.

    Parameters:
      to_email   - the user's email address
      username   - shown in the email body so it feels personal
      reset_link - the full URL with the token, e.g. http://127.0.0.1:5000/reset?token=abc123
    """
    if not GMAIL_USER or not GMAIL_PASS:
        # If no email credentials set, print the link to terminal instead
        # Useful for local development/testing without real email setup
        print(f"\n{'='*60}")
        print(f"[DEV MODE] Password reset link for {to_email}:")
        print(f"{reset_link}")
        print(f"{'='*60}\n")
        return True  # Pretend it worked so the app flow continues

    try:
        # Build the email as a MIME message
        # MIME = Multipurpose Internet Mail Extensions
        # It lets us send both plain text AND HTML versions of the same email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Momentum — Reset Your Password"
        msg["From"]    = GMAIL_USER
        msg["To"]      = to_email

        # Plain text version (for email clients that don't support HTML)
        plain = f"""
Hi {username},

You requested a password reset for your Momentum account.

Click the link below to set a new password. This link expires in 30 minutes.

{reset_link}

If you didn't request this, you can safely ignore this email.
Your password will not change.

— The Momentum Team
        """.strip()

        # HTML version (prettier, shown in modern email clients)
        html = f"""
<!DOCTYPE html>
<html>
<body style="background:#0f0e0c; font-family:'DM Sans',sans-serif; padding:2rem;">
  <div style="max-width:480px; margin:0 auto; background:#181714;
              border:1px solid #2d2a25; border-top:3px solid #e8b86d;
              border-radius:12px; padding:2rem;">

    <div style="text-align:center; margin-bottom:1.5rem;">
      <span style="font-size:2rem; color:#e8b86d;">◈</span>
      <h1 style="color:#f0e6d0; font-size:1.5rem; margin:.5rem 0 0;">Momentum</h1>
    </div>

    <p style="color:#a89f8c; font-size:.9rem;">Hi <strong style="color:#f0e6d0;">{username}</strong>,</p>

    <p style="color:#a89f8c; font-size:.9rem; line-height:1.6;">
      You requested a password reset. Click the button below to choose a new password.
      This link expires in <strong style="color:#e8b86d;">30 minutes</strong>.
    </p>

    <div style="text-align:center; margin:2rem 0;">
      <a href="{reset_link}"
         style="background:#e8b86d; color:#000; font-weight:600;
                padding:.75rem 2rem; border-radius:999px;
                text-decoration:none; font-size:.95rem;">
        Reset My Password
      </a>
    </div>

    <p style="color:#5c564d; font-size:.75rem; text-align:center;">
      If you didn't request this, ignore this email. Your password won't change.
    </p>
  </div>
</body>
</html>
        """.strip()

        # Attach both versions — email client picks the best one it supports
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html,  "html"))

        # Connect to Gmail's SMTP server
        # Port 587 = TLS (encrypted) connection
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()           # Say hello to the server
            server.starttls()       # Upgrade to encrypted connection
            server.login(GMAIL_USER, GMAIL_PASS)   # Authenticate
            server.sendmail(GMAIL_USER, to_email, msg.as_string())

        return True

    except Exception as e:
        print(f"[Email error] {e}")
        return False
