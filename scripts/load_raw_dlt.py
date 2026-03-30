"""CSV → DuckDB 적재를 dlt 파이프라인으로 수행합니다.

기존 load_raw_to_duckdb.py의 dlt 대체 버전입니다.
- dlt의 filesystem source 대신 직접 CSV를 읽어 resource로 yield
- destination: duckdb (mini_mart.duckdb, schema=raw)
- _loaded_at 컬럼 자동 추가 (dbt source freshness 연동)
- write_disposition: replace (매번 전체 교체)
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

import dlt
import duckdb
from dlt.sources import DltResource
from generate_seeds import RAW_TABLES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMMON_DIR = ROOT / "data" / "common"
DEFAULT_FALLBACK_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "mini_mart.duckdb"

SOURCE_FILE_CANDIDATES: dict[str, list[str]] = {
    "olist_orders": ["olist_orders.csv", "olist_orders_dataset.csv"],
    "olist_order_items": ["olist_order_items.csv", "olist_order_items_dataset.csv"],
    "olist_order_payments": ["olist_order_payments.csv", "olist_order_payments_dataset.csv"],
    "olist_order_reviews": ["olist_order_reviews.csv", "olist_order_reviews_dataset.csv"],
    "olist_customers": ["olist_customers.csv", "olist_customers_dataset.csv"],
    "olist_products": ["olist_products.csv", "olist_products_dataset.csv"],
    "olist_sellers": ["olist_sellers.csv", "olist_sellers_dataset.csv"],
    "product_category_name_translation": ["product_category_name_translation.csv"],
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


def _resolve_csv_path(table: str, source_dir: Path) -> Path:
    candidates = SOURCE_FILE_CANDIDATES.get(table, [f"{table}.csv"])
    for filename in candidates:
        p = source_dir / filename
        if p.exists():
            return p
    raise FileNotFoundError(
        f"missing csv for table={table}. expected one of: {', '.join(candidates)}"
    )


def _read_csv_rows(csv_path: Path) -> list[dict]:
    """CSV를 dict 리스트로 읽습니다."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


@dlt.source(name="olist_raw")
def olist_raw_source(source_dir: Path):
    """Olist CSV 파일들을 dlt resource로 생성합니다."""
    loaded_at = datetime.now(timezone.utc).isoformat()

    for table in RAW_TABLES:
        csv_path = _resolve_csv_path(table, source_dir)

        @dlt.resource(
            name=table,
            write_disposition="replace",
            primary_key=None,
        )
        def _load_table(path: Path = csv_path, ts: str = loaded_at):
            rows = _read_csv_rows(path)
            for row in rows:
                row["_loaded_at"] = ts
                yield row

        yield _load_table


def _drop_existing_raw_tables() -> None:
    """기존 raw 스키마 테이블을 DROP합니다 (dlt 메타데이터 컬럼 충돌 방지)."""
    if not DB_PATH.exists():
        return
    con = duckdb.connect(str(DB_PATH))
    try:
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
        ).fetchall()
        for (table_name,) in tables:
            con.execute(f'DROP TABLE IF EXISTS raw."{table_name}"')
        if tables:
            print(f"dropped {len(tables)} existing table(s) in raw schema")
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="dlt pipeline: CSV → DuckDB (raw schema)")
    parser.add_argument(
        "--source-dir",
        default=None,
        help="CSV directory path. default: MINI_MART_SOURCE_DIR or data/common or data/raw",
    )
    args = parser.parse_args()

    source_dir = resolve_source_dir(args.source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"csv source directory not found: {source_dir}")

    _drop_existing_raw_tables()

    pipeline = dlt.pipeline(
        pipeline_name="olist_raw_load",
        destination=dlt.destinations.duckdb(str(DB_PATH)),
        dataset_name="raw",
    )

    source = olist_raw_source(source_dir=source_dir)
    load_info = pipeline.run(source)

    print(f"dlt pipeline finished: {load_info}")
    print(f"loaded {len(RAW_TABLES)} tables from {source_dir} into {DB_PATH} (schema=raw)")


if __name__ == "__main__":
    main()
