"""
Database Initialization Script using Python (No psql CLI required).
Executes sql/setup.sql directly against PostgreSQL using psycopg.
"""

import sys
import logging
from config import RDS_HOST, RDS_PORT, RDS_DATABASE, RDS_USER
from db.connection import get_connection

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("init_db")


def initialize_database():
    print("=" * 70)
    print(" [DB-INIT] Initializing PostgreSQL Schema & Extensions via Python")
    print("=" * 70)
    print(f"Target Host:     {RDS_HOST}")
    print(f"Target Port:     {RDS_PORT}")
    print(f"Database:        {RDS_DATABASE}")
    print(f"User:            {RDS_USER}")
    print("-" * 70)

    try:
        with open("sql/setup.sql", "r", encoding="utf-8") as f:
            sql_script = f.read()
    except Exception as exc:
        print(f"❌ Could not read sql/setup.sql: {exc}")
        return 1

    try:
        print("Connecting to PostgreSQL...")
        conn = get_connection(autocommit=True)
        with conn.cursor() as cur:
            print("Executing sql/setup.sql...")
            cur.execute(sql_script)
        conn.close()

        print("✅ Database setup completed successfully!")
        print("   - Created schema 'dba_ai'")
        print("   - Created table 'dba_ai.health_history'")
        print("   - Created table 'dba_ai.incidents'")
        print("   - Seeded initial DBA incident records")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"❌ Database initialization failed: {exc}")
        print("\n💡 Troubleshooting Tips:")
        print("  1. Verify credentials and host in your .env file.")
        print("  2. If using an AWS internal endpoint (*.ec2.internal), ensure you have network routing / VPN into the VPC, or use the public RDS endpoint (*.rds.amazonaws.com).")
        print("  3. Ensure your RDS security group allows inbound traffic on port 5432.")
        return 1


if __name__ == "__main__":
    sys.exit(initialize_database())
