#!/usr/bin/env python3
"""
REHU SQLite Database Backup Script.

Uses SQLite's native backup API for safe, consistent backups
without locking the live database.

Usage:
    python scripts/backup_db.py
    python scripts/backup_db.py --backup-dir /backups
"""
import os
import sys
import sqlite3
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def backup_database(db_path: str, backup_dir: str) -> str:
    os.makedirs(backup_dir, exist_ok=True)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"product_hunter_{timestamp}.db")

    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(backup_path)

    try:
        source.backup(dest)
        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"Database backup successful")
        print(f"  Source: {db_path}")
        print(f"  Backup: {backup_path}")
        print(f"  Size:   {size_mb:.2f} MB")
        return backup_path
    finally:
        dest.close()
        source.close()


def main():
    parser = argparse.ArgumentParser(description="Backup REHU SQLite database")
    parser.add_argument(
        "--db", default="data/product_hunter.db",
        help="Path to source database"
    )
    parser.add_argument(
        "--backup-dir", default="data/backups",
        help="Directory for backup files"
    )
    args = parser.parse_args()

    try:
        backup_database(args.db, args.backup_dir)
    except Exception as e:
        print(f"Backup failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()