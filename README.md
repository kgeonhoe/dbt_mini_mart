# dbt_mini_mart

Olist 공개 e-커머스 데이터를 DuckDB에 적재하고, dbt로 **raw → staging → intermediate → gold** 레이어를 구성하여 스타스키마 기반 미니 데이터 마트를 구축하는 프로젝트입니다.

## Highlights
- **Source 기반 적재** — dbt seed 대신 Python 스크립트로 CSV를 DuckDB raw 스키마에 직접 벌크 로드
- **4 레이어 아키텍처** — Raw / Staging(view) / Intermediate(view) / Gold(table)
- **스타스키마** — 5개 차원 + 2개 팩트(주문 아이템 + 일별 매출 집계)
- **63개 데이터 테스트** — unique, not_null, FK relationships, accepted_range, reconciliation singular tests
- **재사용 매크로** — `generate_order_line_id`, `date_range_start/end`로 로직 중앙 집중화
- **전체 문서화** — raw/stg/int/gold 모든 컬럼에 description, doc blocks, lineage 점검 완료

## Stack
| 도구 | 용도 |
|---|---|
| dbt-core 1.11 | 데이터 변환 오케스트레이션 |
| dbt-duckdb | DuckDB 어댑터 |
| DuckDB | 로컬 OLAP 웨어하우스 |
| uv | Python 환경·패키지 관리 |

## Quick Start
1. uv 가상환경 및 의존성 설치

```bash
uv venv
source .venv/bin/activate
uv sync
```

2. Olist CSV 준비

Kaggle Olist 데이터셋에서 아래 파일을 준비합니다.

- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `product_category_name_translation.csv`

기본 경로는 `data/common`이며, 다른 경로는 환경변수로 지정합니다.

```bash
export MINI_MART_SOURCE_DIR=/path/to/common_csv_dir
```

3. (옵션) 샘플 데이터 생성

```bash
uv run python scripts/generate_raw_csv.py
```

샘플 데이터는 `data/raw`에 생성됩니다. (테이블명은 Olist 스키마 기준)

4. DuckDB raw 스키마에 적재(dbt seed 사용 안 함)

```bash
uv run python scripts/load_raw_to_duckdb.py
```

5. dbt 실행

```bash
export DBT_PROFILES_DIR=$(pwd)
uv run dbt deps
uv run dbt run
uv run dbt test
uv run dbt docs generate
uv run dbt docs serve --port 8080
```

## Project Layout
```
models/
├── raw/
│   └── raw_sources.yml          # 8개 source 테이블 정의·컬럼 설명
├── staging/
│   ├── stg_customers.sql        # 고객 마스터
│   ├── stg_orders.sql           # 주문-아이템 조인 (order line grain)
│   ├── stg_payments.sql         # 결제 내역
│   ├── stg_products.sql         # 상품 + 영문 카테고리
│   ├── stg_reviews.sql          # 리뷰
│   ├── stg_sellers.sql          # 판매자
│   └── stg_schema.yml           # 모든 컬럼 description + 테스트
├── intermediate/
│   ├── int_orders_enriched.sql  # 결제·리뷰·아이템수 결합
│   └── int_schema.yml           # 컬럼 description
├── gold/
│   ├── dim_customer.sql
│   ├── dim_date.sql             # date_spine (2016-2018)
│   ├── dim_payment_type.sql
│   ├── dim_product.sql
│   ├── dim_seller.sql
│   ├── fct_orders.sql           # 주문 아이템 grain 팩트
│   ├── fct_daily_sales.sql      # 일별·판매자 집계 팩트
│   └── gold_schema.yml          # FK relationships + 테스트
└── docs.md                      # 레이어·grain·비즈니스 로직 doc blocks

macros/
├── generate_order_line_id.sql   # PK 생성 매크로
└── date_range.sql               # 날짜 범위 중앙 관리

tests/
├── assert_daily_sales_reconciles.sql   # 일별 매출 ↔ 주문 합계 검증
├── assert_daily_line_count_matches.sql # 라인 수 정합성 검증
└── assert_orders_within_date_range.sql # 날짜 범위 이탈 검증
```

## Layering
| 레이어 | Materialization | 역할 |
|---|---|---|
| **Raw** | source (DuckDB `raw` 스키마) | 원천 CSV 그대로 적재 |
| **Staging** | view (`stg` 스키마) | 타입 캐스팅, 리네이밍, 단순 조인 |
| **Intermediate** | view (`int` 스키마) | 비즈니스 로직 결합 (결제·리뷰·아이템수) |
| **Gold** | table (`gold` 스키마) | 스타스키마: 차원 + 팩트 |

## Star Schema (Gold)
```
            ┌──────────────┐
            │  dim_date    │
            └──────┬───────┘
                   │
┌────────────┐     │     ┌─────────────────┐
│dim_customer├─────┼─────┤dim_payment_type │
└────────────┘     │     └─────────────────┘
                   │
            ┌──────┴───────┐
            │  fct_orders  │──── fct_daily_sales
            └──────┬───────┘     (date + seller 집계)
                   │
┌────────────┐     │     ┌────────────┐
│dim_product ├─────┘     │ dim_seller │
└────────────┘           └────────────┘
```

- **Fact**: `fct_orders` — 주문 아이템(order line) grain
- **Fact Aggregate**: `fct_daily_sales` — 일자/판매자 기준 집계
- **Dimensions**: `dim_customer`, `dim_product`, `dim_seller`, `dim_payment_type`, `dim_date`

## DAG Lineage
```
raw sources ─→ stg_customers  ─→ dim_customer
             ─→ stg_orders    ─┐
             ─→ stg_payments  ─┼→ int_orders_enriched ─→ fct_orders ─→ fct_daily_sales
             ─→ stg_reviews   ─┘
             ─→ stg_products  ─→ dim_product
             ─→ stg_sellers   ─→ dim_seller
             ─→ stg_payments  ─→ dim_payment_type
                                  dim_date (standalone, date_spine)
```

## Testing Strategy
| 테스트 유형 | 개수 | 대상 |
|---|---|---|
| unique + not_null | 30+ | 모든 PK 컬럼 |
| relationships (FK) | 5 | fct_orders → 5개 차원 |
| accepted_range | 7 | 금액·무게·점수 범위 |
| accepted_values | 1 | 결제수단 코드 |
| unique_combination | 1 | fct_daily_sales 복합키 |
| singular (reconciliation) | 3 | 팩트 간 합계·건수 정합성 |
| **총계** | **63** | |