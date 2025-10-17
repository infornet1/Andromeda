#!/usr/bin/env python3
"""
Test database connectivity for ADX Strategy v2.0
"""

import sys
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('config/.env')

def test_connection():
    """Test MariaDB connection"""

    config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'database': os.getenv('DB_NAME', 'bitcoin_trading'),
        'user': os.getenv('DB_USER', 'trader'),
        'password': os.getenv('DB_PASSWORD', 'SecureTrader2025!@#')
    }

    print("=" * 60)
    print("ADX Strategy v2.0 - Database Connection Test")
    print("=" * 60)
    print(f"\nTesting connection to:")
    print(f"  Host: {config['host']}:{config['port']}")
    print(f"  Database: {config['database']}")
    print(f"  User: {config['user']}")
    print(f"  Password: {'*' * len(config['password'])}")

    try:
        # Attempt connection
        print("\n[1/5] Connecting to database...", end=" ")
        connection = mysql.connector.connect(**config)
        print("✅ SUCCESS")

        if connection.is_connected():
            # Get database info
            print("[2/5] Checking database info...", end=" ")
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            db_version = cursor.fetchone()[0]
            print(f"✅ MariaDB {db_version}")

            # Check tables
            print("[3/5] Verifying tables exist...", end=" ")
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]
            expected_tables = ['adx_signals', 'adx_trades', 'adx_strategy_params',
                             'adx_performance', 'adx_system_logs']

            missing = [t for t in expected_tables if t not in tables]
            if missing:
                print(f"❌ MISSING: {missing}")
                return False
            print(f"✅ All {len(expected_tables)} tables found")

            # Check parameters
            print("[4/5] Loading strategy parameters...", end=" ")
            cursor.execute("SELECT COUNT(*) FROM adx_strategy_params")
            param_count = cursor.fetchone()[0]
            print(f"✅ {param_count} parameters loaded")

            # Test insert capability
            print("[5/5] Testing write access...", end=" ")
            test_query = """
                INSERT INTO adx_system_logs (log_level, component, message)
                VALUES ('INFO', 'TEST', 'Connection test successful')
            """
            cursor.execute(test_query)
            connection.commit()

            # Delete test log
            cursor.execute("DELETE FROM adx_system_logs WHERE component='TEST'")
            connection.commit()
            print("✅ Write access confirmed")

            cursor.close()
            connection.close()

            print("\n" + "=" * 60)
            print("✅ DATABASE CONNECTION TEST PASSED")
            print("=" * 60)
            print("\nDatabase Details:")
            print(f"  Tables: {', '.join(tables[:5])}...")
            print(f"  Parameters: {param_count}")
            print(f"  Status: Ready for ADX strategy")
            print("\nNext steps:")
            print("  - Configure .env file with BingX API credentials")
            print("  - Begin Phase 2: Data Collection & ADX Engine")
            print("=" * 60)
            return True

    except Error as e:
        print(f"❌ FAILED")
        print(f"\n❌ Database connection error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if MariaDB is running: sudo systemctl status mariadb")
        print("  2. Verify credentials in config/.env")
        print("  3. Check database exists: sudo mysql -e 'SHOW DATABASES;'")
        return False

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
