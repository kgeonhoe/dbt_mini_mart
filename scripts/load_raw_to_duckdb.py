from __future__ import annotations

import argparse
import os
from pathlib import Path

import duckdb

from generate_seeds import RAW_TABLES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMMON_DIR = ROOT / "data" / "common"
DEFAULT_FALLBACK_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "mini_mart.duckdb"

SOURCE_FILE_CANDIDATES = {
    "olist_orders": ["olist_orders.csv", "olist_orders_dataset.csv"],
    "olist_order_items": ["olist_order_items.csv", "olist_order_items_dataset.csv"],
    "olist_order_payments": ["olist_order_payments.csv", "olist_order_payments_dataset.csv"],
    "olist_order_reviews": ["olist_order_reviews.csv", "olist_order_reviews_dataset.csv"],
    "olist_customers": ["olist_customers.csv", "olist_customers_dataset.csv"],
    "olist_products": ["olist_products.csv", "olist_products_dataset.csv"],
    "olist_sellers": ["olist_sellers.csv", "olist_sellers_dataset.csv"],
    "product_category_name_translation": [
        "product_category_name_translation.csv"
    ],
}


def resolve_source_dir(cli_source: str | None) -> Path:
    if cli_source:
        return Path(cli_source).resolve()

    env_source = os.getenv("MINI_MART_SOURCE_DIR")
    if env_source:
        return Path(env_source).resolve()

    if DEFAULT_COMMON_DIR.exists():
        return DEFAULT_COMMON_DIR

    return DEFAULT_FALLBACK_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        default=None,
        help="CSV directory path. default: MINI_MART_SOURCE_DIR or data/common or data/raw",
    )
    args = parser.parse_args()

    source_dir = resolve_source_dir(args.source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"csv source directory not found: {source_dir}")

    con = duckdb.connect(str(DB_PATH))
    con.execute("create schema if not exists raw")

    for table in RAW_TABLES:
        candidates = SOURCE_FILE_CANDIDATES.get(table, [f"{table}.csv"])
        csv_path = None
        for filename in candidates:
            candidate_path = source_dir / filename
            if candidate_path.exists():
                csv_path = candidate_path
                break
        if csv_path is None:
            raise FileNotFoundError(
                f"missing csv for table={table}. expected one of: {', '.join(candidates)}"
            )

        con.execute(
            f"""
            create or replace table raw.{table} as
            select *, current_timestamp as _loaded_at
            from read_csv_auto(?, header=true)
            """,
            [str(csv_path)],
        )

    con.close()
    print(f"loaded {len(RAW_TABLES)} tables from {source_dir} into {DB_PATH} (schema=raw)")


if __name__ == "__main__":
    main()