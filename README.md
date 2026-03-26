# dbt_mini_mart

Olist 공개 e-커머스 데이터를 DuckDB에 적재하고, dbt로 **raw → staging → intermediate → gold** 레이어를 구성하여 스타스키마 기반 미니 데이터 마트를 구축하는 프로젝트입니다.

## Highlights
- **Source 기반 적재** — dbt seed 대신 Python 스크립트로 CSV를 DuckDB raw 스키마에 직접 벌크 로드
- **4 레이어 아키텍처** — Raw / Staging(view) / Intermediate(view) / Gold(table)
- **스타스키마** — 5개 차원 + 2개 팩트(주문 아이템 + 일별 매출 집계)
- **63개 데이터 테스트** — unique, not_null, FK relationships, accepted_range, reconciliation singular tests
- **재사용 매크로** — `generate_order_line_id`, `date_range_start/end`로 로직 중앙 집중화
- **Dagster 오케스트레이션** — dbt 모델 → Asset, dbt 테스트 → Asset Check 자동 매핑, UI에서 lineage·품질 한눈에 확인
- **전체 문서화** — raw/stg/int/gold 모든 컬럼에 description, doc blocks, lineage 점검 완료

## Stack
| 도구 | 용도 |
|---|---|
| dbt-core 1.11 | 데이터 변환 오케스트레이션 |
| dbt-duckdb | DuckDB 어댑터 |
| DuckDB | 로컬 OLAP 웨어하우스 |
| Dagster 1.12 + dagster-dbt | Asset 기반 오케스트레이션 |
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
uv run dbt build          # 모델 빌드 + 테스트 (DAG 순서)
uv run dbt docs generate
uv run dbt docs serve --port 8080
```

6. Dagster 실행

```bash
# Dagster dev server 시작 (기본 포트 3000)
uv run dagster dev

# 특정 포트 지정
uv run dagster dev -p 3000
```

Dagster UI(`http://localhost:3000`)에서 22개 asset(8 source + 14 model)의 lineage, materialization 상태, Asset Check 결과를 확인할 수 있습니다.

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

dagster_mini_mart/               # Dagster code location
├── __init__.py
├── project.py                   # DbtProject 경로 설정
├── assets.py                    # @dbt_assets 정의
└── definitions.py               # Definitions (assets + resources)

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
| **Raw** | source (DuckDB `raw` 스키마) | 원천 CSV 그대로 적재 + `_loaded_at` freshness 컬럼 |
| **Staging** | view (`stg` 스키마) | 타입 캐스팅, 리네이밍, 단순 조인 |
| **Intermediate** | view (`int` 스키마) | 비즈니스 로직 결합 (결제·리뷰·아이템수) |
| **Gold** | table (`gold` 스키마) | 스타스키마: 차원 + 팩트 |

## Raw → Staging 설계 근거

Staging 계층의 원칙: **Raw 그대로 두고, 타입 정리·컬럼 선별·최소한의 조인만 수행**.

| Staging 모델 | Raw 소스 | 왜 이렇게 만들었나 |
|---|---|---|
| **stg_orders** | `olist_orders` + `olist_order_items` | 분석 grain이 '주문 아이템'이므로, 헤더와 아이템을 inner join하여 1행=1아이템으로 플랫하게 만듦. `order_line_id`(PK) 생성, timestamp→date 캐스팅, 불필요 컬럼(shipping_limit_date 등) 제외 |
| **stg_customers** | `olist_customers` | 원천 grain 유지(customer_id 1행). zip_code를 varchar로 캐스팅(앞자리 0 보존). customer_unique_id를 살려 재구매 추적 기반 확보 |
| **stg_products** | `olist_products` + `product_category_name_translation` | 포르투갈어 카테고리를 영문으로 번역하기 위해 left join(매핑 없는 상품도 보존). 원천 오타(`product_name_lenght`) 교정. 물리 속성 integer 캐스팅 |
| **stg_payments** | `olist_order_payments` | 원천 grain 유지(order_id + sequential). integer/double 캐스팅. accepted_values로 결제수단 코드 유효성 보장. intermediate에서 주결제수단 선정·합계 집계의 기초 |
| **stg_reviews** | `olist_order_reviews` | 정량 분석만 필요하므로 comment 텍스트 제외, score·날짜만 캐스팅. intermediate에서 주문별 평균 점수 집계에 사용 |
| **stg_sellers** | `olist_sellers` | 원천 grain 유지. zip_code varchar 캐스팅만 수행. dim_seller 차원의 직접 기초 |

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
| source freshness | 8 | 모든 raw 테이블 (24h warn / 72h error) |
| **총계** | **63 data + 8 freshness** | |

### 테스트 실행 방식

```bash
# 1. 전체 빌드: 모델 실행 → 해당 모델의 테스트 즉시 실행 (의존성 순서)
dbt build

# 2. 모델만 실행
dbt run

# 3. 테스트만 실행 (이미 빌드된 모델 대상)
dbt test

# 4. source freshness 점검 (raw 테이블이 최근에 적재됐는지 확인)
dbt source freshness
```

### 의존성 관리와 테스트 실행 순서

dbt는 DAG(방향 비순환 그래프) 기반으로 의존성을 자동 관리합니다.

1. **`dbt build`의 실행 순서**: `source` → `stg_*`(view) → `int_*`(view) → `gold dim/fct`(table) 순서로 빌드하되, 각 모델이 완성되면 **해당 모델의 테스트를 즉시 실행**합니다. 만약 `stg_orders`의 unique 테스트가 실패하면, 이를 참조하는 `int_orders_enriched` 이후 모델은 **SKIP** 처리됩니다.

2. **`ref()` / `source()` 함수**: `{{ ref('stg_orders') }}`는 단순 문자열 치환이 아니라, dbt가 DAG 노드 간 의존 간선을 자동 등록합니다. 이를 통해 빌드 순서, 병렬 실행, 선택적 실행(`--select +fct_orders`)이 가능합니다.

3. **Source freshness**: `dbt source freshness`는 raw 테이블의 `_loaded_at` 컬럼에서 `max()`를 조회하여, 마지막 적재 시각이 현재 시각 대비 threshold(warn: 24h, error: 72h)를 초과하면 경고/실패를 반환합니다. **raw 테이블이 갱신되지 않으면 파이프라인이 실패하도록** 하는 안전장치입니다.

### 테스트가 잡아내는 문제 유형

| 문제 상황 | 잡아내는 테스트 |
|---|---|
| PK 중복 (같은 주문 아이템이 2번 들어옴) | `unique` on order_line_id |
| FK 불일치 (fct_orders에 없는 고객 ID) | `relationships` → dim_customer |
| 금액 음수 (환불 오류, 적재 버그) | `accepted_range` ≥ 0 |
| 알 수 없는 결제수단 등장 | `accepted_values` on payment_type |
| fct_daily_sales 집계 ↔ fct_orders 합계 불일치 | singular `assert_daily_sales_reconciles` |
| 주문 날짜가 dim_date 범위 밖 | singular `assert_orders_within_date_range` |
| raw 테이블이 오래 전에 적재되어 갱신 안 됨 | `source freshness` (warn 24h / error 72h) |

## 오케스트레이션: 왜 Dagster인가 (vs Airflow + Cosmos)

### 후보 비교

| 기준 | GitHub Actions | Airflow + Cosmos | **Dagster + dagster-dbt** |
|---|---|---|---|
| 셋업 | yaml 1개 | 웹서버+스케줄러+메타DB 필요 | `pip install dagster dagster-dbt` |
| dbt 통합 | CLI 직접 호출 | Cosmos가 DAG 자동 생성 | **manifest 파싱 → 모델별 Asset 자동 생성** |
| 모니터링 UI | 없음 (로그만) | DAG 실행 상태 | **Asset lineage + 테스트 결과 + freshness 시각화** |
| 테스트 매핑 | exit code만 | Task 성공/실패 | **모델별 Asset Check로 개별 표시** |
| freshness | 별도 파싱 필요 | 직접 구현 | **Source Asset에 자동 연결** |
| 로컬 실행 | 불가 (CI 전용) | Docker Compose 필요 | **`dagster dev` 한 줄** |

### Dagster를 선택한 이유

1. **Asset 중심 패러다임**
   - Airflow는 "이 Task를 이 순서로 실행해라" (Task 중심)
   - Dagster는 "이 데이터를 만들어라" (Asset 중심)
   - dbt 모델 자체가 "데이터 산출물"이므로 Asset 개념과 자연스럽게 일치

2. **dbt 테스트 = Asset Check 자동 매핑**
   - Cosmos(Airflow): dbt 테스트를 별도 Task로 실행. 실패해도 "어떤 모델의 어떤 품질 문제인지" 직관적이지 않음
   - Dagster: `unique_fct_orders_order_line_id` → `fct_orders` asset의 체크 탭에 표시. **어떤 자산에 어떤 품질 문제가 있는지** UI에서 바로 파악

3. **Source Freshness 네이티브 지원**
   - Dagster는 raw source를 Observable Source Asset으로 인식
   - freshness policy를 붙이면 **"이 소스가 stale인데, 이걸 참조하는 하위 모델도 영향받음"**이 lineage 위에서 시각적으로 표현됨
   - Airflow에서는 이걸 보려면 별도 대시보드를 만들어야 함

4. **로컬 DuckDB 환경과의 궁합**
   - Airflow는 production-grade 스케줄러라 로컬에서 띄우기 무거움 (Docker Compose, PostgreSQL 메타DB)
   - Dagster는 `dagster dev`로 단일 프로세스 실행, DuckDB 파일 하나와 자연스럽게 동작

5. **Cosmos의 한계**
   - Cosmos는 Airflow 위에서 dbt를 편하게 쓰는 어댑터이지, 모니터링 자체를 개선하지는 않음
   - 결국 Airflow UI의 "Task 성공/실패" 뷰에서 벗어나지 못함

### Dagster에서의 dbt 매핑 구조

```
dbt model (fct_orders)     →  Dagster Asset
dbt test (unique, not_null) →  Asset Check (해당 asset에 부착)
dbt source (olist_orders)   →  Source Asset
source freshness            →  Freshness Policy on Source Asset
singular test               →  Asset Check (관련 asset에 연결)
```

```
┌─────────────────────────────────────────────┐
│  Dagster UI — Asset Lineage                 │
│                                             │
│  [olist_orders] → [stg_orders] → [int_...] → [fct_orders] → [fct_daily_sales]
│   freshness:✅     checks:✅      checks:✅    checks:✅      checks:✅
│                                             │
│  Asset Detail: fct_orders                   │
│  ├─ Materialized: 2026-03-24 13:37          │
│  ├─ Check: unique_order_line_id       ✅    │
│  ├─ Check: not_null_order_id          ✅    │
│  ├─ Check: relationships → dim_customer ✅  │
│  └─ Check: reconciliation             ✅    │
└─────────────────────────────────────────────┘
```

### Dagster 프로젝트 구조

```
dagster_mini_mart/
├── project.py      # DbtProject: dbt 프로젝트 경로·manifest 위치 설정
├── assets.py       # @dbt_assets: manifest를 파싱하여 dbt model → Dagster Asset 매핑
└── definitions.py  # Definitions: asset + DbtCliResource 등록 → dagster dev 진입점
```

`pyproject.toml`의 `[tool.dagster]` 섹션에서 code location 모듈을 지정합니다:

```toml
[tool.dagster]
module_name = "dagster_mini_mart.definitions"
```
```