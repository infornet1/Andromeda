#!/usr/bin/env python3
"""
Data Management Pipeline for ADX Strategy v2.0
Integrates API, ADX calculations, and database storage
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.api.bingx_api import BingXAPI
from src.indicators.adx_engine import ADXEngine
from src.data.db_manager import DatabaseManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataManager:
    """
    Data Management Pipeline

    Features:
    - Fetch kline data from BingX
    - Calculate ADX indicators
    - Store signals in database
    - Retrieve historical data
    - Manage data cache
    """

    def __init__(self, api: BingXAPI, adx_engine: ADXEngine, db: DatabaseManager):
        """
        Initialize data manager

        Args:
            api: BingX API instance
            adx_engine: ADX calculation engine
            db: Database manager
        """
        self.api = api
        self.adx_engine = adx_engine
        self.db = db

        logger.info("Data Manager initialized")

    def fetch_and_analyze(self, symbol: str = "BTC-USDT",
                         interval: str = "5m",
                         limit: int = 100) -> pd.DataFrame:
        """
        Fetch kline data and calculate ADX indicators

        Args:
            symbol: Trading pair
            interval: Timeframe
            limit: Number of candles

        Returns:
            DataFrame with OHLCV and ADX indicators
        """
        logger.info(f"Fetching {limit} {interval} candles for {symbol}")

        # 1. Fetch kline data
        klines = self.api.get_kline_data(symbol, interval, limit)

        # 2. Convert to DataFrame
        df = pd.DataFrame(klines)

        # 3. Calculate ADX indicators
        df = self.adx_engine.analyze_dataframe(df)

        logger.info(f"Analysis complete: {len(df)} candles processed")
        return df

    def save_signal_to_db(self, signal_data: Dict) -> int:
        """
        Save signal to database

        Args:
            signal_data: Signal dictionary

        Returns:
            Signal ID
        """
        return self.db.insert_signal(signal_data)

    def get_latest_signal(self, symbol: str = "BTC-USDT",
                         interval: str = "5m") -> Dict:
        """
        Get latest ADX signal with all indicators

        Args:
            symbol: Trading pair
            interval: Timeframe

        Returns:
            Latest signal dictionary
        """
        # Fetch and analyze recent data
        df = self.fetch_and_analyze(symbol, interval, limit=50)

        # Get latest row
        signal = self.adx_engine.get_latest_signal(df)

        # Add symbol and timeframe
        signal['symbol'] = symbol
        signal['timeframe'] = interval

        return signal

    def scan_for_signals(self, symbol: str = "BTC-USDT",
                        interval: str = "5m",
                        save_to_db: bool = False) -> List[Dict]:
        """
        Scan for ADX signals in recent data

        Args:
            symbol: Trading pair
            interval: Timeframe
            save_to_db: Whether to save signals to database

        Returns:
            List of signal dictionaries
        """
        logger.info(f"Scanning for signals: {symbol} {interval}")

        # Fetch and analyze data
        df = self.fetch_and_analyze(symbol, interval, limit=100)

        # Find BUY/SELL signals (not HOLD or EXIT)
        signals = []

        for idx, row in df.iterrows():
            if row.get('adx_signal') in ['BUY', 'SELL']:
                signal = {
                    'timestamp': row.get('datetime'),
                    'symbol': symbol,
                    'timeframe': interval,
                    'open': row.get('open'),
                    'high': row.get('high'),
                    'low': row.get('low'),
                    'close': row.get('close'),
                    'volume': row.get('volume'),
                    'adx': row.get('adx'),
                    'plus_di': row.get('plus_di'),
                    'minus_di': row.get('minus_di'),
                    'adx_slope': row.get('adx_slope'),
                    'di_spread': row.get('di_spread'),
                    'trend_strength': row.get('trend_strength'),
                    'signal_type': row.get('adx_signal'),
                    'confidence': row.get('confidence'),
                    'entry_condition': f"ADX={row.get('adx'):.2f}, +DI={row.get('plus_di'):.2f}, -DI={row.get('minus_di'):.2f}"
                }

                signals.append(signal)

                if save_to_db:
                    self.save_signal_to_db(signal)

        logger.info(f"Found {len(signals)} signals")
        return signals

    def get_historical_data(self, symbol: str = "BTC-USDT",
                           interval: str = "5m",
                           days: int = 7) -> pd.DataFrame:
        """
        Get historical data for backtesting

        Args:
            symbol: Trading pair
            interval: Timeframe
            days: Number of days of history

        Returns:
            DataFrame with historical OHLCV and ADX data
        """
        # Calculate number of candles needed
        # 5m = 288 candles/day, 1h = 24 candles/day, etc.
        candles_per_day = {
            '1m': 1440,
            '5m': 288,
            '15m': 96,
            '30m': 48,
            '1h': 24,
            '4h': 6,
            '1d': 1
        }

        candles_needed = days * candles_per_day.get(interval, 288)

        # BingX limit is 1440 per request
        if candles_needed > 1440:
            logger.warning(f"Requested {candles_needed} candles, limiting to 1440")
            candles_needed = 1440

        logger.info(f"Fetching {days} days of {interval} data ({candles_needed} candles)")

        return self.fetch_and_analyze(symbol, interval, limit=candles_needed)

    def validate_data_quality(self, df: pd.DataFrame) -> Dict:
        """
        Validate data quality

        Args:
            df: DataFrame to validate

        Returns:
            Data quality report
        """
        report = {
            'total_candles': len(df),
            'missing_values': df.isnull().sum().sum(),
            'adx_valid': (~df['adx'].isnull()).sum(),
            'adx_coverage': (~df['adx'].isnull()).sum() / len(df) * 100 if len(df) > 0 else 0,
            'date_range': {
                'start': str(df['datetime'].iloc[0]) if len(df) > 0 else None,
                'end': str(df['datetime'].iloc[-1]) if len(df) > 0 else None
            }
        }

        logger.info(f"Data quality: {report['adx_coverage']:.1f}% ADX coverage")
        return report

    def get_realtime_update(self, symbol: str = "BTC-USDT") -> Dict:
        """
        Get real-time price and ADX update

        Args:
            symbol: Trading pair

        Returns:
            Real-time data dictionary
        """
        # Get latest ticker
        ticker = self.api.get_ticker_price(symbol)

        # Get latest signal
        signal = self.get_latest_signal(symbol)

        return {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'price': ticker['price'],
            'adx': signal.get('adx'),
            'plus_di': signal.get('plus_di'),
            'minus_di': signal.get('minus_di'),
            'trend_strength': signal.get('trend_strength'),
            'signal': signal.get('adx_signal'),
            'confidence': signal.get('confidence')
        }


if __name__ == "__main__":
    # Test script
    from dotenv import load_dotenv

    load_dotenv('config/.env')

    print("=" * 70)
    print("Testing Data Management Pipeline")
    print("=" * 70)

    # Initialize components
    print("\n1. Initializing components...")

    api = BingXAPI(
        api_key=os.getenv('BINGX_API_KEY'),
        api_secret=os.getenv('BINGX_API_SECRET')
    )

    adx_engine = ADXEngine(period=14)

    db = DatabaseManager(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        database=os.getenv('DB_NAME', 'bitcoin_trading'),
        user=os.getenv('DB_USER', 'trader'),
        password=os.getenv('DB_PASSWORD')
    )

    dm = DataManager(api, adx_engine, db)
    print("✅ All components initialized")

    # Test 2: Fetch and analyze
    print("\n2. Fetching and analyzing data...")
    df = dm.fetch_and_analyze("BTC-USDT", "5m", limit=50)
    print(f"✅ Fetched and analyzed {len(df)} candles")

    # Test 3: Validate data quality
    print("\n3. Validating data quality...")
    quality = dm.validate_data_quality(df)
    print(f"✅ Data quality: {quality['adx_coverage']:.1f}% ADX coverage")
    print(f"   Date range: {quality['date_range']['start']} to {quality['date_range']['end']}")

    # Test 4: Get latest signal
    print("\n4. Getting latest signal...")
    signal = dm.get_latest_signal("BTC-USDT", "5m")
    print(f"✅ Latest Signal:")
    print(f"   Price: ${signal.get('close_price'):,.2f}")
    print(f"   ADX: {signal.get('adx'):.2f}")
    print(f"   Signal: {signal.get('adx_signal')}")
    print(f"   Trend: {signal.get('trend_strength')}")
    print(f"   Confidence: {signal.get('confidence'):.2%}")

    # Test 5: Scan for signals
    print("\n5. Scanning for recent signals...")
    signals = dm.scan_for_signals("BTC-USDT", "5m", save_to_db=False)
    print(f"✅ Found {len(signals)} signals in last 100 candles")
    if signals:
        print(f"   Latest: {signals[-1].get('signal_type')} at ${signals[-1].get('close'):.2f}")

    # Test 6: Get real-time update
    print("\n6. Getting real-time update...")
    rt_data = dm.get_realtime_update("BTC-USDT")
    print(f"✅ Real-time:")
    print(f"   Price: ${rt_data['price']:,.2f}")
    print(f"   Signal: {rt_data['signal']}")
    print(f"   Confidence: {rt_data['confidence']:.2%}")

    print("\n" + "=" * 70)
    print("✅ Data Management Pipeline Test Complete!")
    print("=" * 70)
