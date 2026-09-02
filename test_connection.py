"""
Diagnostic CLI Script to Verify PostgreSQL & RDS Connectivity.
Tests connection parameters, extensions (pg_stat_statements, pgvector), and health collectors.
"""

import sys
import logging

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import RDS_HOST, RDS_PORT, RDS_DATABASE, RDS_USER, RDS_SSLMODE, USE_SECRETS_MANAGER
from db.connection import check_database_connection
from db.health import collect_health, get_installed_extensions

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main():
    print("=" * 70)
    print(" [RDS-CHECK] AI PostgreSQL DBA Assistant - RDS Connectivity Diagnostic")
    print("=" * 70)
    print(f"Target Host:     {RDS_HOST}")
    print(f"Target Port:     {RDS_PORT}")
    print(f"Database:        {RDS_DATABASE}")
    print(f"User:            {RDS_USER}")
    print(f"SSL Mode:        {RDS_SSLMODE}")
    print(f"Secrets Manager: {'ENABLED' if USE_SECRETS_MANAGER else 'DISABLED'}")
    print("-" * 70)

    print("\n1. Testing Raw PostgreSQL Connection...")
    status = check_database_connection()

    if not status["connected"]:
        print(f"❌ Connection Failed: {status['error']}")
        print("\n💡 Troubleshooting Tips:")
        print("  - Verify your RDS Security Group allows inbound traffic on port 5432 from your current IP.")
        print("  - Confirm RDS Public Accessibility is enabled if testing from outside VPC.")
        print("  - Verify credentials in .env or AWS Secrets Manager.")
        print("  - You can run the application in DEMO_MODE=true in .env to test the dashboard offline.")
        return 1

    print(f"✅ Connected successfully!")
    print(f"   PostgreSQL Version: {status['version']}")
    print(f"   Database Name:      {status['database']}")
    print(f"   Server Time:        {status['server_time']}")

    print("\n2. Checking PostgreSQL Extensions...")
    exts = get_installed_extensions()
    ext_names = [e["extname"] for e in exts]
    print(f"   - pg_stat_statements: {'✅ Installed' if 'pg_stat_statements' in ext_names else '⚠️ Missing (run sql/setup.sql)'}")
    print(f"   - pgvector (vector):  {'✅ Installed' if 'vector' in ext_names else '⚠️ Missing (run sql/setup.sql)'}")

    print("\n3. Collecting Health Telemetry...")
    try:
        metrics = collect_health()
        print(f"✅ Health collection successful!")
        print(f"   - Health Score:       {metrics['health_score']}/100 ({metrics['status']})")
        print(f"   - Active Backends:    {metrics['connections']} / {metrics['max_connections']}")
        print(f"   - Database Size:      {metrics['database_size_gb']} GB")
        print(f"   - Cache Hit Ratio:    {metrics['cache_hit_ratio']}%")
        print(f"   - Long Queries:       {metrics['long_running_queries']}")
        print(f"   - Blocking Sessions:  {metrics['blocking_sessions']}")
        print(f"   - Max XID Age:        {metrics['xid_age']}")
    except Exception as exc:
        print(f"❌ Health collection error: {exc}")

    print("\n" + "=" * 70)
    print(" 🎉 Diagnostic check complete!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
