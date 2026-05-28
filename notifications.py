import asyncio
import logging

import resend

from config import settings

logger = logging.getLogger(__name__)


def _send_signup_notification(email: str, user_id: str, created_at: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping signup notification")
        return
    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [settings.NOTIFICATION_EMAIL],
            "subject": f"New signup: {email}",
            "html": f"""
            <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;
                        padding:32px 24px;color:#1e293b;">
                <h2 style="font-size:1.2rem;font-weight:700;margin-bottom:4px;">
                    New user signed up
                </h2>
                <p style="color:#64748b;font-size:0.85rem;margin-top:0;margin-bottom:24px;">
                    Quote Me · /handshake
                </p>
                <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
                    <tr>
                        <td style="padding:8px 0;color:#64748b;width:110px;">Email</td>
                        <td style="padding:8px 0;font-weight:600;">{email}</td>
                    </tr>
                    <tr>
                        <td style="padding:8px 0;color:#64748b;">User ID</td>
                        <td style="padding:8px 0;font-family:monospace;font-size:0.8rem;">{user_id}</td>
                    </tr>
                    <tr>
                        <td style="padding:8px 0;color:#64748b;">Signed up</td>
                        <td style="padding:8px 0;">{created_at}</td>
                    </tr>
                </table>
            </div>
            """,
        })
        logger.info(f"Admin signup notification sent for {email}")
    except Exception as e:
        logger.error(f"Failed to send admin signup notification: {e}")


def _send_contact_notification(
    user_email: str | None,
    telegram_id: int,
    telegram_username: str | None,
    message: str,
) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping contact notification")
        return
    display_user = user_email or f"Telegram ID {telegram_id}"
    username_line = f"@{telegram_username}" if telegram_username else "(no username)"
    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [settings.NOTIFICATION_EMAIL],
            "subject": f"Contact message from {display_user}",
            "html": f"""
            <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;
                        padding:32px 24px;color:#1e293b;">
                <h2 style="font-size:1.2rem;font-weight:700;margin-bottom:4px;">
                    New contact message
                </h2>
                <p style="color:#64748b;font-size:0.85rem;margin-top:0;margin-bottom:24px;">
                    Quote Me · /contact (Telegram)
                </p>
                <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
                    <tr>
                        <td style="padding:8px 0;color:#64748b;width:130px;">Email</td>
                        <td style="padding:8px 0;font-weight:600;">{user_email or "(not linked)"}</td>
                    </tr>
                    <tr>
                        <td style="padding:8px 0;color:#64748b;">Telegram ID</td>
                        <td style="padding:8px 0;font-family:monospace;font-size:0.8rem;">{telegram_id}</td>
                    </tr>
                    <tr>
                        <td style="padding:8px 0;color:#64748b;">Username</td>
                        <td style="padding:8px 0;">{username_line}</td>
                    </tr>
                </table>
                <div style="margin-top:24px;padding:16px 20px;background:#f8fafc;
                            border-left:3px solid #3b82f6;border-radius:0 8px 8px 0;">
                    <p style="margin:0;color:#1e293b;font-size:0.95rem;
                              white-space:pre-wrap;word-break:break-word;">{message}</p>
                </div>
            </div>
            """,
        })
        logger.info(f"Admin contact notification sent for telegram_id={telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send admin contact notification: {e}")


async def notify_new_signup(email: str, user_id: str, created_at: str) -> None:
    try:
        await asyncio.to_thread(_send_signup_notification, email, user_id, created_at)
    except Exception as e:
        logger.error(f"notify_new_signup task failed: {e}")


async def notify_contact_message(
    user_email: str | None,
    telegram_id: int,
    telegram_username: str | None,
    message: str,
) -> None:
    try:
        await asyncio.to_thread(
            _send_contact_notification,
            user_email,
            telegram_id,
            telegram_username,
            message,
        )
    except Exception as e:
        logger.error(f"notify_contact_message task failed: {e}")
