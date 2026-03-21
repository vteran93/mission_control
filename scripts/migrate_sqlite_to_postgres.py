#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import load_settings
from data_migration import (
    assert_tables_empty,
    build_engine,
    copy_all_tables,
    default_table_names,
)


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    default_source = settings.instance_path / "mission_control.db"
    parser = argparse.ArgumentParser(
        description="Copy Mission Control data from SQLite to Postgres.",
    )
    parser.add_argument(
        "--source-sqlite",
        default=str(default_source),
        help="Path to the source SQLite database file.",
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("DATABASE_URL", ""),
        help="SQLAlchemy URL for the target Postgres database.",
    )
    parser.add_argument(
        "--allow-non-empty-target",
        action="store_true",
        help="Skip the empty target validation before copying rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = Path(args.source_sqlite)

    if not source_path.exists():
        raise SystemExit(f"Source SQLite database not found: {source_path}")
    if not args.target_url:
        raise SystemExit("Missing --target-url or DATABASE_URL")

    table_names = default_table_names()
    source_engine = build_engine(f"sqlite:///{source_path}")
    target_engine = build_engine(args.target_url)

    if not args.allow_non_empty_target:
        assert_tables_empty(target_engine, table_names)

    copied = copy_all_tables(source_engine, target_engine, table_names)

    print("✅ Migration completed")
    for table_name, row_count in copied.items():
        print(f"   - {table_name}: {row_count} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
