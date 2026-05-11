#!/usr/bin/env python3
"""
Apply all Supabase migrations to the remote database.

Usage:
    python scripts/apply_migrations.py --password YOUR_DB_PASSWORD

The DB password is the one you set when you created the Supabase project.
Find it at: https://supabase.com/dashboard/project/ddjimleyejztfaxjtkjd/settings/database
(under "Database password" or "Connection string")
"""
import argparse
import os
import sys
from pathlib import Path

PROJECT_REF = "ddjimleyejztfaxjtkjd"
MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"
MIGRATION_ORDER = [
    "001_initial_schema.sql",
    "002_rls_policies.sql",
    "003_semantic_search.sql",
    "004_ingestion_sources.sql",
    "005_narrative_momentum.sql",
    "006_notification_channels.sql",
]


def main():
    parser = argparse.ArgumentParser(description="Apply Supabase migrations")
    parser.add_argument("--password", required=True, help="Supabase database password")
    parser.add_argument("--host", default=f"db.{PROJECT_REF}.supabase.co")
    parser.add_argument("--port", type=int, default=5432)
    args = parser.parse_args()

    try:
        import psycopg2
    except ImportError:
        print("Installing psycopg2-binary...")
        os.system(f"{sys.executable} -m pip install psycopg2-binary -q")
        import psycopg2

    print(f"Connecting to {args.host}:{args.port} ...")
    try:
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            dbname="postgres",
            user="postgres",
            password=args.password,
            sslmode="require",
            connect_timeout=15,
        )
        conn.autocommit = True
    except Exception as e:
        print(f"Connection failed: {e}")
        print("\nCheck your password at:")
        print(f"  https://supabase.com/dashboard/project/{PROJECT_REF}/settings/database")
        sys.exit(1)

    cur = conn.cursor()
    print("Connected!\n")

    for filename in MIGRATION_ORDER:
        path = MIGRATIONS_DIR / filename
        if not path.exists():
            print(f"  SKIP  {filename} (file not found)")
            continue
        sql = path.read_text()
        print(f"  Applying {filename} ({len(sql)} chars)...", end=" ", flush=True)
        try:
            cur.execute(sql)
            print("OK")
        except Exception as e:
            err = str(e).strip()
            if "already exists" in err or "duplicate" in err.lower():
                print(f"already applied (skipped)")
                conn.rollback()
            else:
                print(f"FAILED: {err[:200]}")
                conn.rollback()

    conn.close()
    print("\nDone. Run the seed script next:")
    print(f"  cd backend && venv/bin/python3 ../scripts/seed_data.py")


if __name__ == "__main__":
    main()
