#!/usr/bin/env python3
"""
test_db_connection.py — Test database connectivity independently.

Use this to verify your MySQL database is reachable, credentials work,
and the expected tables exist — without touching the Spotify API at all.

Usage:
    python test_db_connection.py               # Test DB connection and schema
    python test_db_connection.py --verbose      # With debug logging
"""

import argparse
import logging
import os
import sys

# Ensure the project root is on the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="Test database connectivity.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable DEBUG-level logging.")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("test_db_connection")

    logger.info("=" * 60)
    logger.info("  Database Connection Test")
    logger.info("=" * 60)

    # ── Check environment variables ────────────────────────────────────────────
    db_vars = ["DB_HOST", "DB_USERNAME", "DB_PASSWORD", "DB_NAME", "DB_PORT"]
    missing = [var for var in db_vars if not os.getenv(var)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)
    logger.info("✅ All DB environment variables are present.")

    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USERNAME")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT")

    logger.info("  DB_HOST: %s", db_host)
    logger.info("  DB_USERNAME: %s", db_user)
    logger.info("  DB_NAME: %s", db_name)
    logger.info("  DB_PORT: %s", db_port)

    # ── Attempt connection ─────────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Attempting MySQL connection...")
    logger.info("-" * 60)

    try:
        import mysql.connector
        db = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=os.getenv("DB_PASSWORD"),
            database=db_name,
            port=db_port,
        )
        cursor = db.cursor()
        logger.info("✅ Connected to MySQL successfully!")
    except Exception as e:
        logger.error("❌ Failed to connect to MySQL: %s", e, exc_info=True)
        sys.exit(1)

    # ── Check expected tables ──────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Checking for expected tables...")
    logger.info("-" * 60)

    expected_tables = ["tracks", "artists", "albums"]
    cursor.execute("SHOW TABLES")
    existing_tables = [row[0] for row in cursor.fetchall()]
    logger.info("  Tables found in '%s': %s", db_name, ", ".join(existing_tables) if existing_tables else "(none)")

    for table in expected_tables:
        if table in existing_tables:
            logger.info("  ✅ Table '%s' exists.", table)

            # Show row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info("     Row count: %d", count)

            # Show columns
            cursor.execute(f"DESCRIBE {table}")
            columns = cursor.fetchall()
            col_names = [col[0] for col in columns]
            logger.info("     Columns: %s", ", ".join(col_names))
        else:
            logger.warning("  ⚠️  Table '%s' NOT found!", table)

    # ── Cleanup ────────────────────────────────────────────────────────────────
    cursor.close()
    db.close()
    logger.info("-" * 60)
    logger.info("✅ Database connection test complete.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
