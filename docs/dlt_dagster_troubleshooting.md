# dlt + Dagster 통합 트러블슈팅 기록

> dlt 파이프라인을 Dagster multi-asset으로 통합하면서 발생한 이슈와 해결 과정을 기록합니다.

---

## Issue #1: DuckDB — NOT NULL 컬럼 추가 불가

**시점**: dlt 파이프라인 최초 실행
**에러 메시지**:
```
dlt.destinations.exceptions.DatabaseTransientException:
Parser Error: Adding columns with constraints not yet supported
```

**원인**:
기존 `load_raw_to_duckdb.py`로 생성된 raw 테이블이 DuckDB에 이미 존재.
dlt가 `_dlt_load_id`(NOT NULL), `_dlt_id`(NOT NULL + UNIQUE) 메타데이터 컬럼을 `ALTER TABLE ADD COLUMN`으로 추가하려 했으나,
DuckDB는 **제약조건이 있는 컬럼의 ALTER TABLE ADD를 지원하지 않음**.

**해결**:
`_drop_raw_tables()` 함수를 추가하여 파이프라인 실행 전 기존 raw 테이블을 DROP.
```python
def _drop_raw_tables() -> int:
    con = duckdb.connect(str(DB_PATH))
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
    ).fetchall()
    for (t,) in rows:
        con.execute(f'DROP TABLE IF EXISTS raw."{t}"')
    con.close()
    return len(rows)
```

**교훈**: dlt는 자체 메타데이터 컬럼(`_dlt_id`, `_dlt_load_id`)을 자동 추가. 기존 비-dlt 테이블 위에 dlt를 overlay할 때는 반드시 기존 테이블을 정리해야 함.

---

## Issue #2: dev_mode=True가 schema 이름 변경

**시점**: Issue #1 해결 직후
**증상**: 파이프라인 성공했으나 데이터가 `raw` 스키마가 아닌 `raw_20260330012444`에 적재됨.

**원인**:
`dlt.pipeline(dev_mode=True)`가 dataset 이름에 타임스탬프를 자동 suffix로 붙임.
dbt는 `raw` 스키마를 기대하므로 테이블을 찾지 못함.

**해결**: `dev_mode=True` 제거.
```python
pipeline = dlt.pipeline(
    pipeline_name="olist_raw_load",
    destination=dlt.destinations.duckdb(str(DB_PATH)),
    dataset_name="raw",  # dev_mode 없이 고정
)
```

**교훈**: `dev_mode=True`는 개발 시 스키마 격리에 유용하지만, 다른 도구(dbt)와 연동할 때는 schema 이름이 변경되지 않도록 주의.

---

## Issue #3: Dagster context type hint 거부

**시점**: dlt_assets.py를 Dagster Definitions에 등록
**에러 메시지**:
```
DagsterInvalidDefinitionError:
Cannot annotate `context` parameter with type AssetExecutionContext.
`context` must be annotated with AssetExecutionContext, AssetCheckExecutionContext,
OpExecutionContext, or left blank.
```

**원인**:
Dagster 1.12.20에서 `@multi_asset` 데코레이터 함수의 `context` 파라미터에 `AssetExecutionContext` 타입 힌트를 사용하면 validation 에러 발생. `OpExecutionContext`도 동일 에러.
Dagster 버전별로 허용하는 type hint가 다름.

**해결**: context 파라미터의 type annotation을 제거.
```python
# Before (에러)
def dlt_raw_ingest(context: AssetExecutionContext):
def dlt_raw_ingest(context: OpExecutionContext):

# After (정상)
def dlt_raw_ingest(context):
```

**교훈**: Dagster 버전에 따라 context type hint 호환성이 다름. 에러 발생 시 annotation을 제거하는 것이 가장 안전한 방법.

---

## Issue #4: multi_asset subset 선택 시 MaterializeResult 충돌

**시점**: Dagster CLI로 단일 asset materialize 시도
**에러 메시지**:
```
DagsterInvariantViolationError:
Asset key raw/olist_order_items not found in AssetsDefinition
```

**원인**:
`@multi_asset(can_subset=True)`로 설정했으나, 함수 내에서 **모든 8개 테이블에 대해 무조건 MaterializeResult를 yield**.
subset으로 `raw/olist_orders` 하나만 선택했을 때, 선택되지 않은 `raw/olist_order_items` 등의 MaterializeResult까지 반환하려다 실패.

**해결**: `context.selected_output_names`를 확인하여 선택된 asset에 대해서만 결과 반환.
```python
selected = context.selected_output_names
for table in RAW_TABLES:
    if table not in selected:
        continue
    count = _row_count(table)
    yield MaterializeResult(asset_key=["raw", table], ...)
```

**교훈**: `can_subset=True` multi-asset에서는 반드시 `context.selected_output_names`를 확인해야 함. 그렇지 않으면 **subset 실행 시에도 전체 output을 yield**하려다 asset key mismatch 에러 발생.

---

## Issue #5: definitions.py 구문 오류 (닫는 괄호 중복)

**시점**: formatter가 파일을 자동 정리한 후
**에러 메시지**:
```
SyntaxError: unmatched ')'
```

**원인**: 파일 편집 과정에서 `Definitions(...)` 블록 끝에 닫는 괄호 `)` 가 중복 추가됨.

**해결**: 중복 괄호 제거.

**교훈**: 여러 차례 편집이 반복되면 구문 오류가 쌓일 수 있으므로, 편집 후 반드시 import 테스트(`python -c "from module import ..."`)를 수행.

---

## 최종 검증 결과

| 테스트 | 결과 |
|--------|------|
| Dagster definitions 로딩 | ✅ 22 assets (raw 8 + stg 5 + int 1 + gold 7 + dim_date) |
| 단일 asset materialize (`raw/olist_orders`) | ✅ RUN_SUCCESS |
| 전체 asset materialize (8 tables) | ✅ RUN_SUCCESS, 모든 테이블 row_count 반환 |
| dbt build (dlt 적재 데이터 기반) | ✅ PASS=77 WARN=0 ERROR=0 |

## 아키텍처 요약

```
[dlt multi-asset]         [dbt assets]
raw/olist_orders     →    stg/stg_orders     →    int/int_orders_enriched  →  gold/fct_orders
raw/olist_customers  →    stg/stg_customers  →                               gold/dim_customer
raw/olist_products   →    stg/stg_products   →                               gold/dim_product
...                       ...                                                 gold/fct_daily_sales
```

**Dagster UI**: http://127.0.0.1:3000 에서 ingestion → transform → gold 전체 리니지 확인 가능.
