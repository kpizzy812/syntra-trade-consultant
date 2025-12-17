"""
Resend Email Service для Magic Link Authentication

Отправляет passwordless login emails через Resend API
https://resend.com/docs/send-with-python
"""

import os
from typing import Optional
from loguru import logger

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("⚠️ Resend SDK not installed. Run: pip install resend")


class ResendEmailService:
    """
    Email service для отправки magic links через Resend API

    Resend - современный email сервис для разработчиков (2024-2025)
    Free tier: 3,000 emails/month, 100 emails/day
    """

    def __init__(self):
        """
        Initialize Resend client
        """
        self.api_key = os.getenv('RESEND_API_KEY')
        self.from_email = os.getenv('RESEND_FROM_EMAIL', 'noreply@syntratrade.xyz')
        self.from_name = os.getenv('RESEND_FROM_NAME', 'Syntra AI')

        if not RESEND_AVAILABLE:
            logger.error("❌ Resend SDK not available - install with: pip install resend")
            self.client = None
            return

        if not self.api_key:
            logger.warning("⚠️ RESEND_API_KEY not set - email service disabled")
            self.client = None
        else:
            # Set global API key for Resend SDK
            resend.api_key = self.api_key
            self.client = resend
            logger.info("✅ Resend email service initialized")

    def is_available(self) -> bool:
        """
        Check if email service is configured and ready

        Returns:
            True if Resend is configured, False otherwise
        """
        return self.client is not None and RESEND_AVAILABLE

    async def send_magic_link(
        self,
        to_email: str,
        magic_link_url: str,
        language: str = "en"
    ) -> bool:
        """
        Send magic link email via Resend

        Args:
            to_email: Recipient email address
            magic_link_url: Full URL with magic link token
            language: Email language (en or ru)

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.is_available():
            logger.error("❌ Resend not configured - cannot send email")
            return False

        try:
            # Email content based on language
            if language == "ru":
                subject = "Вход в Syntra AI - Magic Link"
                html_content = self._get_magic_link_template_ru(magic_link_url)
            else:
                subject = "Sign in to Syntra AI - Magic Link"
                html_content = self._get_magic_link_template_en(magic_link_url)

            # Create email params
            params: resend.Emails.SendParams = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "tags": [
                    {"name": "type", "value": "magic_link"},
                    {"name": "language", "value": language},
                ]
            }

            # Send email via Resend
            response = resend.Emails.send(params)

            # Check response (Resend returns dict with 'id' on success)
            if response and 'id' in response:
                logger.info(f"✅ Magic link email sent to {to_email} (id: {response['id']})")
                return True
            else:
                logger.error(f"❌ Failed to send email: {response}")
                return False

        except Exception as e:
            logger.exception(f"❌ Error sending magic link email via Resend: {e}")
            return False

    def _get_magic_link_template_en(self, magic_link_url: str) -> str:
        """
        Get HTML template for magic link email (English)

        Args:
            magic_link_url: Magic link URL

        Returns:
            HTML email template
        """
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in to Syntra AI</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
            padding: 40px 20px;
        }}
        .email-wrapper {{
            max-width: 600px;
            margin: 0 auto;
        }}
        .container {{
            background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
            border-radius: 16px;
            padding: 48px 40px;
            box-shadow: 0 20px 60px rgba(14, 165, 233, 0.15);
            border: 1px solid rgba(14, 165, 233, 0.2);
        }}
        .logo {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .logo-image {{
            width: 80px;
            height: 80px;
            margin: 0 auto 20px;
        }}
        .logo h1 {{
            background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
            font-size: 36px;
            font-weight: 800;
            letter-spacing: -0.02em;
        }}
        .logo-subtitle {{
            color: #9ca3af;
            font-size: 14px;
            margin-top: 8px;
        }}
        h2 {{
            color: #ffffff;
            font-size: 24px;
            margin-bottom: 16px;
            text-align: center;
        }}
        p {{
            color: #d1d5db;
            font-size: 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .button-container {{
            text-align: center;
            margin: 40px 0;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
            color: #ffffff !important;
            padding: 18px 48px;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 700;
            font-size: 18px;
            box-shadow: 0 10px 30px rgba(14, 165, 233, 0.4);
            transition: all 0.3s ease;
            letter-spacing: 0.02em;
        }}
        .button:hover {{
            box-shadow: 0 15px 40px rgba(14, 165, 233, 0.6);
            transform: translateY(-2px);
        }}
        .divider {{
            text-align: center;
            margin: 30px 0;
            color: #6b7280;
            font-size: 14px;
        }}
        .link-box {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(14, 165, 233, 0.2);
            border-radius: 8px;
            padding: 16px;
            word-break: break-all;
            font-size: 12px;
            color: #9ca3af;
            font-family: 'Courier New', monospace;
            margin: 20px 0;
        }}
        .warning {{
            background: rgba(245, 158, 11, 0.1);
            border-left: 4px solid #f59e0b;
            padding: 16px;
            margin: 30px 0;
            border-radius: 8px;
        }}
        .warning strong {{
            color: #fbbf24;
            font-size: 15px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 30px;
            border-top: 1px solid rgba(75, 85, 99, 0.5);
            text-align: center;
        }}
        .footer p {{
            font-size: 14px;
            color: #6b7280;
            margin-bottom: 8px;
        }}
        .footer a {{
            color: #0ea5e9;
            text-decoration: none;
        }}
        .footer a:hover {{
            color: #3b82f6;
        }}
        .security-note {{
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 8px;
            padding: 12px;
            margin-top: 24px;
            text-align: center;
        }}
        .security-note p {{
            color: #6ee7b7;
            font-size: 13px;
            margin: 0;
        }}
    </style>
</head>
<body>
    <div class="email-wrapper">
        <div class="container">
            <!-- Logo Section -->
            <div class="logo">
                <div style="font-size: 64px; margin-bottom: 16px;">🤖</div>
                <h1>SYNTRA AI</h1>
                <p class="logo-subtitle">AI-Powered Crypto Analytics</p>
            </div>

            <!-- Main Content -->
            <h2>Sign in to your account</h2>
            <p>Click the button below to securely sign in to Syntra AI. No password needed!</p>

            <!-- CTA Button -->
            <div class="button-container">
                <a href="{magic_link_url}" class="button">✨ Sign In to Syntra AI</a>
            </div>

            <!-- Divider -->
            <div class="divider">
                ━━━━━━━━━━━━━━━━━━━━━━━━
            </div>

            <!-- Alternative Link -->
            <p style="font-size: 14px; color: #9ca3af;">Or copy and paste this link in your browser:</p>
            <div class="link-box">{magic_link_url}</div>

            <!-- Warning -->
            <div class="warning">
                <strong>⏰ This link expires in 15 minutes</strong> and can only be used once for security.
            </div>

            <!-- Security Note -->
            <div class="security-note">
                <p>🔒 Secure passwordless authentication powered by Syntra AI</p>
            </div>

            <!-- Footer -->
            <div class="footer">
                <p>If you didn't request this email, you can safely ignore it.</p>
                <p>
                    <a href="https://ai.syntratrade.xyz">ai.syntratrade.xyz</a>
                </p>
                <p style="font-size: 12px; margin-top: 20px;">
                    © 2025 Syntra AI. All rights reserved.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
        """.strip()

    def _get_magic_link_template_ru(self, magic_link_url: str) -> str:
        """
        Get HTML template for magic link email (Russian)

        Args:
            magic_link_url: Magic link URL

        Returns:
            HTML email template
        """
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в Syntra AI</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
            padding: 40px 20px;
        }}
        .email-wrapper {{
            max-width: 600px;
            margin: 0 auto;
        }}
        .container {{
            background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
            border-radius: 16px;
            padding: 48px 40px;
            box-shadow: 0 20px 60px rgba(14, 165, 233, 0.15);
            border: 1px solid rgba(14, 165, 233, 0.2);
        }}
        .logo {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .logo-image {{
            width: 80px;
            height: 80px;
            margin: 0 auto 20px;
        }}
        .logo h1 {{
            background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
            font-size: 36px;
            font-weight: 800;
            letter-spacing: -0.02em;
        }}
        .logo-subtitle {{
            color: #9ca3af;
            font-size: 14px;
            margin-top: 8px;
        }}
        h2 {{
            color: #ffffff;
            font-size: 24px;
            margin-bottom: 16px;
            text-align: center;
        }}
        p {{
            color: #d1d5db;
            font-size: 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .button-container {{
            text-align: center;
            margin: 40px 0;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
            color: #ffffff !important;
            padding: 18px 48px;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 700;
            font-size: 18px;
            box-shadow: 0 10px 30px rgba(14, 165, 233, 0.4);
            transition: all 0.3s ease;
            letter-spacing: 0.02em;
        }}
        .button:hover {{
            box-shadow: 0 15px 40px rgba(14, 165, 233, 0.6);
            transform: translateY(-2px);
        }}
        .divider {{
            text-align: center;
            margin: 30px 0;
            color: #6b7280;
            font-size: 14px;
        }}
        .link-box {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(14, 165, 233, 0.2);
            border-radius: 8px;
            padding: 16px;
            word-break: break-all;
            font-size: 12px;
            color: #9ca3af;
            font-family: 'Courier New', monospace;
            margin: 20px 0;
        }}
        .warning {{
            background: rgba(245, 158, 11, 0.1);
            border-left: 4px solid #f59e0b;
            padding: 16px;
            margin: 30px 0;
            border-radius: 8px;
        }}
        .warning strong {{
            color: #fbbf24;
            font-size: 15px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 30px;
            border-top: 1px solid rgba(75, 85, 99, 0.5);
            text-align: center;
        }}
        .footer p {{
            font-size: 14px;
            color: #6b7280;
            margin-bottom: 8px;
        }}
        .footer a {{
            color: #0ea5e9;
            text-decoration: none;
        }}
        .footer a:hover {{
            color: #3b82f6;
        }}
        .security-note {{
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 8px;
            padding: 12px;
            margin-top: 24px;
            text-align: center;
        }}
        .security-note p {{
            color: #6ee7b7;
            font-size: 13px;
            margin: 0;
        }}
    </style>
</head>
<body>
    <div class="email-wrapper">
        <div class="container">
            <!-- Logo Section -->
            <div class="logo">
                <div style="font-size: 64px; margin-bottom: 16px;">🤖</div>
                <h1>SYNTRA AI</h1>
                <p class="logo-subtitle">Криптоаналитика на основе ИИ</p>
            </div>

            <!-- Main Content -->
            <h2>Вход в ваш аккаунт</h2>
            <p>Нажмите на кнопку ниже, чтобы безопасно войти в Syntra AI. Пароль не нужен!</p>

            <!-- CTA Button -->
            <div class="button-container">
                <a href="{magic_link_url}" class="button">✨ Войти в Syntra AI</a>
            </div>

            <!-- Divider -->
            <div class="divider">
                ━━━━━━━━━━━━━━━━━━━━━━━━
            </div>

            <!-- Alternative Link -->
            <p style="font-size: 14px; color: #9ca3af;">Или скопируйте и вставьте эту ссылку в браузер:</p>
            <div class="link-box">{magic_link_url}</div>

            <!-- Warning -->
            <div class="warning">
                <strong>⏰ Ссылка действительна 15 минут</strong> и может быть использована только один раз для безопасности.
            </div>

            <!-- Security Note -->
            <div class="security-note">
                <p>🔒 Безопасная авторизация без пароля от Syntra AI</p>
            </div>

            <!-- Footer -->
            <div class="footer">
                <p>Если вы не запрашивали это письмо, можете его проигнорировать.</p>
                <p>
                    <a href="https://ai.syntratrade.xyz">ai.syntratrade.xyz</a>
                </p>
                <p style="font-size: 12px; margin-top: 20px;">
                    © 2025 Syntra AI. Все права защищены.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
        """.strip()


# Singleton instance
_email_service: Optional[ResendEmailService] = None


def get_resend_service() -> ResendEmailService:
    """
    Get singleton Resend email service instance

    Returns:
        ResendEmailService instance
    """
    global _email_service
    if _email_service is None:
        _email_service = ResendEmailService()
    return _email_service
