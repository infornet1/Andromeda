#!/usr/bin/env python3
"""
ADX Strategy Email Notification System
Sends email alerts for trading signals detected by ADX Strategy v2.0
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json

logger = logging.getLogger('ADXEmailNotifier')


class ADXEmailNotifier:
    """Email notification service for ADX trading alerts"""

    def __init__(self, config_file='email_config.json'):
        """Initialize email notifier with configuration"""
        self.load_config(config_file)
        logger.info(f"Email service initialized - Server: {self.smtp_server}:{self.smtp_port}")
        self.last_alert_time = {}

    def load_config(self, config_file):
        """Load email configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            # Default configuration
            config = {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_use_tls": True,
                "sender_email": "finanzas@ueipab.edu.ve",
                "smtp_username": "finanzas@ueipab.edu.ve",
                "smtp_password": "hcoe hawe gwwn mcvc",
                "recipient_email": "perdomo.gustavo@gmail.com",
                "alert_cooldown_minutes": 15
            }

        self.smtp_server = config.get('smtp_server')
        self.smtp_port = config.get('smtp_port')
        self.smtp_use_tls = config.get('smtp_use_tls', True)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.sender_email = config.get('sender_email')
        self.recipient_email = config.get('recipient_email')
        self.alert_cooldown = config.get('alert_cooldown_minutes', 15) * 60  # Convert to seconds

    def should_send_alert(self, signal_id: str) -> bool:
        """Check if alert should be sent based on cooldown"""
        now = datetime.now().timestamp()
        last_sent = self.last_alert_time.get(signal_id, 0)

        if (now - last_sent) < self.alert_cooldown:
            return False

        return True

    def send_signal_alert(self, signal: dict, current_price: float, adx_data: dict = None) -> bool:
        """
        Send trading signal alert email

        Args:
            signal: Signal dictionary with side, confidence, stop_loss, take_profit
            current_price: Current BTC price
            adx_data: ADX indicator values (optional)

        Returns:
            bool: True if email sent successfully
        """
        signal_id = f"{signal['side']}_{datetime.now().strftime('%Y%m%d')}"

        if not self.should_send_alert(signal_id):
            logger.info("Signal alert suppressed due to cooldown")
            return False

        try:
            # Determine subject
            side_emoji = "🟢" if signal['side'] == 'LONG' else "🔴"
            confidence = signal.get('confidence', 0) * 100

            subject = f"[ADX-STRATEGY] {side_emoji} {signal['side']} Signal - {confidence:.0f}% Confidence"

            # Build email body
            body = self._build_signal_body(signal, current_price, adx_data)

            # Send email
            success = self._send_email(subject, body)

            if success:
                # Update last alert time
                self.last_alert_time[signal_id] = datetime.now().timestamp()
                logger.info(f"Signal alert email sent: {signal['side']} @ ${current_price:,.2f}")

            return success

        except Exception as e:
            logger.error(f"Failed to send signal alert email: {e}")
            return False

    def _build_signal_body(self, signal: dict, current_price: float, adx_data: dict = None) -> str:
        """Build formatted email body with signal details"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        side = signal['side']
        confidence = signal.get('confidence', 0) * 100

        side_emoji = "🟢 LONG" if side == 'LONG' else "🔴 SHORT"

        body = f"""ADX Strategy v2.0 - Trading Signal Detected!

{'='*70}
{side_emoji} SIGNAL DETECTED
{'='*70}
Time: {timestamp}
Direction: {side}
Confidence: {confidence:.1f}%
Current Price: ${current_price:,.2f}

{'='*70}
📊 TRADE PARAMETERS
{'='*70}
Entry Price: ${current_price:,.2f}
Stop Loss: ${signal['stop_loss']:,.2f} ({((signal['stop_loss'] - current_price) / current_price * 100):.2f}%)
Take Profit: ${signal['take_profit']:,.2f} ({((signal['take_profit'] - current_price) / current_price * 100):.2f}%)
Risk/Reward: {abs((signal['take_profit'] - current_price) / (signal['stop_loss'] - current_price)):.2f}
"""

        # Add ADX data if available
        if adx_data:
            body += f"""
{'='*70}
📈 ADX INDICATOR VALUES
{'='*70}
ADX Value: {adx_data.get('adx', 0):.2f} (Trend Strength)
+DI: {adx_data.get('plus_di', 0):.2f}
-DI: {adx_data.get('minus_di', 0):.2f}
DI Spread: {adx_data.get('di_spread', 0):.2f}
ADX Slope: {adx_data.get('adx_slope', 0):.2f}
"""

        body += f"""
{'='*70}
💡 RECOMMENDED ACTION
{'='*70}
"""

        if side == 'LONG':
            body += f"""→ Enter LONG position at current market price
→ Set stop loss at ${signal['stop_loss']:,.2f}
→ Set take profit at ${signal['take_profit']:,.2f}
→ Use 2% risk per trade (max)
→ Leverage: 5x recommended
"""
        else:
            body += f"""→ Enter SHORT position at current market price
→ Set stop loss at ${signal['stop_loss']:,.2f}
→ Set take profit at ${signal['take_profit']:,.2f}
→ Use 2% risk per trade (max)
→ Leverage: 5x recommended
"""

        body += f"""
{'='*70}
⚠️  RISK MANAGEMENT REMINDERS
{'='*70}
• This is a paper trading alert - verify signal before live trading
• Only risk 2% of capital per trade
• Always use stop-loss orders
• Monitor position actively
• Account for exchange fees
• This is NOT financial advice - DYOR

{'='*70}
📧 Alert Settings
{'='*70}
Cooldown: {self.alert_cooldown // 60} minutes between alerts
Recipient: {self.recipient_email}

---
ADX Strategy v2.0 - Live Trading Bot
Sent: {timestamp}
"""

        return body

    def _send_email(self, subject: str, body: str) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            # Create SMTP session
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)

            if self.smtp_use_tls:
                server.starttls()

            # Login if credentials provided
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)

            # Send email
            server.sendmail(self.sender_email, self.recipient_email, msg.as_string())
            server.quit()

            logger.info(f"Email sent successfully to {self.recipient_email}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False

    def send_test_email(self) -> bool:
        """Send test email to verify configuration"""
        subject = "[ADX-STRATEGY] 📧 Test Email - System Configuration"

        body = f"""This is a test email from the ADX Strategy v2.0 Trading Bot.

System Information:
• SMTP Server: {self.smtp_server}:{self.smtp_port}
• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• Recipient: {self.recipient_email}

If you received this email, the notification system is working correctly.

Alert Cooldown: {self.alert_cooldown // 60} minutes between similar alerts

System Status: Email configuration verified ✅

---
ADX Strategy v2.0 - Live Trading Bot
"""

        return self._send_email(subject, body)


# CLI interface for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("Sending test email...")
        email_service = ADXEmailNotifier()
        success = email_service.send_test_email()

        if success:
            print("✅ Test email sent successfully!")
        else:
            print("❌ Failed to send test email")
            sys.exit(1)
    else:
        print("Usage: python adx_email_notifier.py test")
        print("This will send a test email to verify configuration.")
