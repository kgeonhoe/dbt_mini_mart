"""dlt CSV → DuckDB 적재를 Dagster asset으로 래핑합니다.

Dagster UI에서 raw 테이블 8개가 개별 asset으로 나타나며,
dbt staging 모델의 upstream dependency로 연결됩니다.
리니지: [dlt] raw.olist_* → [dbt] stg_* → int_* → dim_*/fct_*
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import dlt
import duckdb
from dagster import (AssetOut, MaterializeResult, MetadataValue,
                     OpExecutionContext, multi_asset)

RAW_TABLES = [
    "olist_orders",
    "olist_order_items",
    "olist_order_payments",
    "olist_order_reviews",
    "olist_customers",
    "olist_products",
    "olist_sellers",
    "product_category_name_translation",
]

PROJECT_DIR = Path(__file__).resolve().parents[1]
CSV_DIR = PROJECT_DIR / "data" / "raw"
DB_PATH = PROJECT_DIR / "mini_mart.duckdb"


def _drop_raw_tables() -> int:
    """기존 raw 스키마 테이블을 DROP (dlt 메타데이터 컬럼 충돌 방지)."""
    if not DB_PATH.exists():
        return 0
    con = duckdb.connect(str(DB_PATH))
    try:
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'raw'"
        ).fetchall()
        for (t,) in rows:
            con.execute(f'DROP TABLE IF EXISTS raw."{t}"')
        return len(rows)
    finally:
        con.close()


def _read_csv_rows(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _row_count(table: str) -> int:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(f'SELECT count(*) FROM raw."{table}"').fetchone()[0]
    finally:
        con.close()


@dlt.source(name="olist_raw")
def _olist_raw_source():
    loaded_at = datetime.now(timezone.utc).isoformat()
    for table in RAW_TABLES:
        csv_path = CSV_DIR / f"{table}.csv"
        if not csv_path.exists():
            csv_path = CSV_DIR / f"{table}_dataset.csv"

        @dlt.resource(name=table, write_disposition="replace", primary_key=None)
        def _load(path: Path = csv_path, ts: str = loaded_at):
            for row in _read_csv_rows(path):
                row["_loaded_at"] = ts
                yield row

        yield _load


# --- Dagster multi-asset -------------------------------------------------

_outs = {
    table: AssetOut(
        key=["raw", table],
        group_name="ingestion",
        is_required=False,
    )
    for table in RAW_TABLES
}


@multi_asset(
    name="dlt_raw_ingest",
    outs=_outs,
    compute_kind="dlt",
    can_subset=True,
)
def dlt_raw_ingest(context):
    """dlt 파이프라인으로 CSV → DuckDB(raw) 적재 후 테이블별 asset 반환."""
    dropped = _drop_raw_tables()
    if dropped:
        context.log.info(f"Dropped {dropped} existing raw table(s)")

    pipeline = dlt.pipeline(
        pipeline_name="olist_raw_load",
        destination=dlt.destinations.duckdb(str(DB_PATH)),
        dataset_name="raw",
    )
    load_info = pipeline.run(_olist_raw_source())
    context.log.info(f"dlt load completed: {load_info}")

    selected = context.selected_output_names
    for table in RAW_TABLES:
        if table not in selected:
            continue
        count = _row_count(table)
        context.log.info(f"  {table}: {count:,} rows")
        yield MaterializeResult(
            asset_key=["raw", table],
            metadata={
                "row_count": MetadataValue.int(count),
                "source": MetadataValue.text(f"data/raw/{table}.csv"),
                "dagster/row_count": MetadataValue.int(count),
            },
        )
