#!/usr/bin/env python3
"""
ADX Hourly Market Report System
Sends detailed market analysis emails every hour
"""
import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd
import json

logger = logging.getLogger('ADXHourlyReporter')


class ADXHourlyReporter:
    """Generates and sends hourly ADX market analysis reports"""

    def __init__(self, config_file='email_config.json'):
        """Initialize hourly reporter with email configuration"""
        self.load_config(config_file)
        logger.info("Hourly Reporter initialized")

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
                "recipient_email": "perdomo.gustavo@gmail.com"
            }

        self.smtp_server = config.get('smtp_server')
        self.smtp_port = config.get('smtp_port')
        self.smtp_use_tls = config.get('smtp_use_tls', True)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.sender_email = config.get('sender_email')
        self.recipient_email = config.get('recipient_email')

    def generate_hourly_report(self, df: pd.DataFrame, paper_trader=None, position_manager=None) -> str:
        """
        Generate comprehensive hourly market report

        Args:
            df: DataFrame with OHLCV and ADX indicators
            paper_trader: PaperTrader instance (optional)
            position_manager: PositionManager instance (optional)

        Returns:
            str: Formatted report text
        """
        latest = df.iloc[-1]
        prev_hour = df.iloc[-12] if len(df) >= 12 else df.iloc[0]  # 12 candles = 1 hour (5min TF)

        current_price = latest['close']
        adx = latest['adx']
        plus_di = latest['plus_di']
        minus_di = latest['minus_di']
        adx_slope = latest['adx_slope']
        di_spread = plus_di - minus_di

        # Price change
        price_change = current_price - prev_hour['close']
        price_change_pct = (price_change / prev_hour['close']) * 100

        # ADX change
        adx_change = adx - prev_hour['adx']

        # Build report
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        report = f"""ADX STRATEGY v2.0 - HOURLY MARKET REPORT

{'='*80}
REPORT TIMESTAMP: {timestamp}
{'='*80}

{'='*80}
📊 CURRENT MARKET CONDITIONS
{'='*80}
BTC Price:           ${current_price:,.2f}
1-Hour Change:       ${price_change:+,.2f} ({price_change_pct:+.2f}%)
24h High/Low:        ${df['high'].tail(288).max():,.2f} / ${df['low'].tail(288).min():,.2f}

{'='*80}
📈 ADX INDICATOR STATUS
{'='*80}
ADX Value:           {adx:.2f}  {'✅ STRONG TREND' if adx >= 25 else '⚠️  WEAK TREND'} (threshold: 25)
ADX Change (1h):     {adx_change:+.2f} points ({'RISING' if adx_change > 0 else 'FALLING'})
ADX Slope:           {adx_slope:+.4f} ({'ACCELERATING' if adx_slope > 0 else 'DECELERATING'})

+DI (Plus DI):       {plus_di:.2f}
-DI (Minus DI):      {minus_di:.2f}
DI Spread:           {di_spread:+.2f}  ({'BULLISH' if di_spread > 0 else 'BEARISH'})
DI Spread Status:    {'✅ STRONG' if abs(di_spread) >= 5 else '⚠️  WEAK'} (threshold: 5)

"""

        # Market state analysis
        if adx < 20:
            market_state = "📊 RANGING / CHOPPY"
            market_desc = "Low trend strength - market consolidating"
            recommendation = "WAIT - Avoid trading in choppy conditions"
        elif adx < 25:
            market_state = "🔄 BUILDING MOMENTUM"
            market_desc = "Trend beginning to form"
            recommendation = "WATCH CLOSELY - Near signal threshold"
        elif adx < 40:
            market_state = "💪 TRENDING"
            market_desc = "Strong directional movement"
            recommendation = "ACTIVE - Good conditions for signals"
        else:
            market_state = "🔥 EXTREME TREND"
            market_desc = "Very strong momentum"
            recommendation = "CAUTION - May be overextended"

        report += f"""{'='*80}
🎯 MARKET STATE ANALYSIS
{'='*80}
Current State:       {market_state}
Description:         {market_desc}
Trading Status:      {recommendation}

"""

        # Signal proximity analysis
        report += f"""{'='*80}
🔍 SIGNAL REQUIREMENTS CHECK
{'='*80}

"""

        # LONG signal check
        long_checks = {
            'ADX > 25': (adx > 25, adx, 25),
            '+DI > -DI': (plus_di > minus_di, plus_di - minus_di, 0),
            'ADX Rising': (adx_slope > 0, adx_slope, 0),
            'DI Spread > 5': (abs(di_spread) > 5, abs(di_spread), 5)
        }

        report += "🟢 LONG Signal Status:\n"
        long_score = 0
        for check, (passed, value, threshold) in long_checks.items():
            status = "✅" if passed else "❌"
            if passed:
                long_score += 1
            report += f"  {status} {check}\n"

        report += f"\n  LONG Score: {long_score}/4 checks passed"

        if long_score == 4:
            report += " - 🚀 READY FOR LONG SIGNAL!"
        elif long_score >= 2:
            report += f" - 🔄 {4-long_score} more checks needed"
        else:
            report += " - ⏳ Not ready yet"

        # SHORT signal check
        short_checks = {
            'ADX > 25': (adx > 25, adx, 25),
            '-DI > +DI': (minus_di > plus_di, minus_di - plus_di, 0),
            'ADX Rising': (adx_slope > 0, adx_slope, 0),
            'DI Spread > 5': (abs(di_spread) > 5, abs(di_spread), 5)
        }

        report += "\n\n🔴 SHORT Signal Status:\n"
        short_score = 0
        for check, (passed, value, threshold) in short_checks.items():
            status = "✅" if passed else "❌"
            if passed:
                short_score += 1
            report += f"  {status} {check}\n"

        report += f"\n  SHORT Score: {short_score}/4 checks passed"

        if short_score == 4:
            report += " - 🚀 READY FOR SHORT SIGNAL!"
        elif short_score >= 2:
            report += f" - 🔄 {4-short_score} more checks needed"
        else:
            report += " - ⏳ Not ready yet"

        # Distance to signal
        report += f"""

{'='*80}
📏 DISTANCE TO NEXT SIGNAL
{'='*80}
"""

        if adx < 25:
            adx_gap = 25 - adx
            report += f"ADX Gap:             -{adx_gap:.2f} points ({adx_gap/25*100:.1f}% below threshold)\n"
        else:
            report += f"ADX Status:          ✅ Above threshold (+{adx-25:.2f} points)\n"

        if abs(di_spread) < 5:
            spread_gap = 5 - abs(di_spread)
            report += f"DI Spread Gap:       -{spread_gap:.2f} points (needs more separation)\n"
        else:
            report += f"DI Spread Status:    ✅ Sufficient separation (+{abs(di_spread)-5:.2f} points)\n"

        # Recent history table
        report += f"""
{'='*80}
📊 RECENT ADX TREND (Last 12 candles / 1 hour)
{'='*80}
Time Ago      Price           ADX     +DI     -DI   Spread   Trend
{'-'*80}
"""

        for i in range(max(0, len(df)-12), len(df)):
            row = df.iloc[i]
            spread = row['plus_di'] - row['minus_di']
            minutes_ago = (len(df) - 1 - i) * 5
            marker = " ← NOW" if i == len(df)-1 else ""

            if minutes_ago == 0:
                time_label = "NOW      "
            else:
                time_label = f"{minutes_ago:2d} min ago"

            # Determine trend arrow
            if i > 0:
                prev_adx = df.iloc[i-1]['adx']
                if row['adx'] > prev_adx + 0.5:
                    trend = "↑"
                elif row['adx'] < prev_adx - 0.5:
                    trend = "↓"
                else:
                    trend = "→"
            else:
                trend = "•"

            report += f"{time_label}  ${row['close']:>10,.2f}  {row['adx']:>6.2f}  {row['plus_di']:>6.2f}  {row['minus_di']:>6.2f}  {spread:>+6.2f}    {trend}{marker}\n"

        # Add account status if available
        if paper_trader:
            stats = paper_trader.get_performance_stats()
            account = paper_trader.get_account_status()

            balance = account['balance']
            equity = account['equity']
            pnl = equity - paper_trader.initial_balance
            pnl_pct = (pnl / paper_trader.initial_balance) * 100

            # Handle zero trades case
            profit_factor = stats.get('profit_factor', 0.0)
            win_rate = stats.get('win_rate', 0.0) * 100
            total_trades = stats.get('total_trades', 0)

            report += f"""
{'='*80}
💰 TRADING ACCOUNT STATUS
{'='*80}
Balance:             ${balance:.2f}
Equity:              ${equity:.2f}
Total P&L:           ${pnl:+.2f} ({pnl_pct:+.2f}%)
Open Positions:      {len(position_manager.get_open_positions()) if position_manager else 0}

Total Trades:        {total_trades}
Win Rate:            {win_rate:.1f}%
Profit Factor:       {profit_factor:.2f}
"""

        # Forecast
        report += f"""
{'='*80}
🔮 NEXT HOUR OUTLOOK
{'='*80}
"""

        # Calculate ADX momentum
        adx_last_5 = df.iloc[-5:]['adx'].values
        adx_momentum = adx_last_5[-1] - adx_last_5[0]

        if adx_momentum > 1:
            outlook = "📈 STRENGTHENING - ADX rising, trend developing"
            signal_prob = "MODERATE - Watch for signal in next 1-2 hours"
        elif adx_momentum < -1:
            outlook = "📉 WEAKENING - ADX falling, trend fading"
            signal_prob = "LOW - May need several hours for setup"
        else:
            outlook = "➡️  STABLE - ADX steady, no clear direction"
            signal_prob = "LOW - Waiting for momentum shift"

        report += f"Trend Direction:     {outlook}\n"
        report += f"Signal Probability:  {signal_prob}\n"

        # Key levels to watch
        report += f"""
{'='*80}
🎯 KEY LEVELS TO WATCH
{'='*80}
Resistance:          ${df['high'].tail(12).max():,.2f} (1-hour high)
Support:             ${df['low'].tail(12).min():,.2f} (1-hour low)
Breakout Above:      Watch for move > ${df['high'].tail(12).max() + 100:,.2f}
Breakdown Below:     Watch for move < ${df['low'].tail(12).min() - 100:,.2f}

{'='*80}
📧 ALERT STATUS
{'='*80}
Next Hourly Report:  {(datetime.now().replace(minute=0, second=0) + pd.Timedelta(hours=1)).strftime('%H:%M')}
Signal Alerts:       ✅ Active (will send immediately when detected)
Email Recipient:     {self.recipient_email}

{'='*80}
⚠️  DISCLAIMER
{'='*80}
This is an automated market analysis report for informational purposes only.
NOT financial advice. Paper trading only. DYOR before any trading decisions.

---
ADX Strategy v2.0 Hourly Market Report
Generated: {timestamp}
"""

        return report

    def send_hourly_report(self, df: pd.DataFrame, paper_trader=None, position_manager=None) -> bool:
        """
        Generate and send hourly report email

        Args:
            df: DataFrame with market data and indicators
            paper_trader: PaperTrader instance (optional)
            position_manager: PositionManager instance (optional)

        Returns:
            bool: True if email sent successfully
        """
        try:
            # Generate report
            report_body = self.generate_hourly_report(df, paper_trader, position_manager)

            # Create subject
            latest = df.iloc[-1]
            adx = latest['adx']
            price = latest['close']
            hour = datetime.now().strftime('%H:%M')

            if adx >= 25:
                subject = f"[ADX-HOURLY] ✅ Strong Trend - ADX {adx:.1f} @ {hour}"
            elif adx >= 20:
                subject = f"[ADX-HOURLY] 🔄 Building - ADX {adx:.1f} @ {hour}"
            else:
                subject = f"[ADX-HOURLY] 📊 Ranging - ADX {adx:.1f} @ {hour}"

            # Send email
            success = self._send_email(subject, report_body)

            if success:
                logger.info(f"Hourly report sent successfully - ADX: {adx:.2f}, Price: ${price:,.2f}")
            else:
                logger.error("Failed to send hourly report")

            return success

        except Exception as e:
            logger.error(f"Error generating/sending hourly report: {e}", exc_info=True)
            return False

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


# CLI interface for testing
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from src.api.bingx_api import BingXAPI
    from src.indicators.adx_engine import ADXEngine

    load_dotenv('config/.env')

    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("Generating test hourly report...")

        # Fetch data
        api_key = os.getenv('BINGX_API_KEY')
        api_secret = os.getenv('BINGX_API_SECRET')

        api = BingXAPI(api_key=api_key, api_secret=api_secret)
        adx_engine = ADXEngine(period=14)

        klines = api.get_kline_data(symbol='BTC-USDT', interval='5m', limit=200)
        df = pd.DataFrame(klines)
        df = adx_engine.analyze_dataframe(df)

        # Create reporter and send
        reporter = ADXHourlyReporter()
        success = reporter.send_hourly_report(df)

        if success:
            print("✅ Test hourly report sent successfully!")
        else:
            print("❌ Failed to send test report")
            sys.exit(1)
    else:
        print("Usage: python adx_hourly_reporter.py test")
        print("This will generate and send a test hourly report.")
