# dbt_mini_mart

Olist 공개 데이터를 raw 레이어로 적재한 뒤, dbt에서 staging/intermediate/gold와 스타스키마를 보여주는 mini mart 프로젝트입니다.

## Stack
- dbt-core (via dbt-duckdb)
- DuckDB
- uv

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
- `data/common`: Olist 원천 CSV 위치(권장)
- `data/raw`: Olist 형태 샘플 CSV 생성 위치
- `scripts/load_raw_to_duckdb.py`: CSV -> DuckDB raw 적재
- `models/raw`: source 정의
- `models/staging`: 컬럼 정리/그레인 정렬
- `models/intermediate`: 비즈니스 로직 결합
- `models/gold`: 스타스키마 및 분석용 팩트
- `models/gold/gold_schema.yml`: 모델 테스트
- `models/docs.md`: 문서 블록

## Layering
- Raw: DuckDB `raw` 스키마의 source 테이블
- Staging: `stg_orders`
- Intermediate: `int_orders_enriched`
- Gold: 차원/팩트 + 요약 지표

## Star Schema (Gold)
- Fact: `fct_orders` (주문 아이템 기준)
- Fact Aggregate: `fct_daily_sales` (일자/판매자 기준)
- Dimensions:
	- `dim_customer`
	- `dim_product`
	- `dim_seller`
	- `dim_payment_type`
	- `dim_date`

## 12일 완성 플랜(권장)
1. Day 1-2: 소스 이해, raw 적재, 기본 모델 작성
2. Day 3-4: 스타스키마 완성 및 키/그레인 확정
3. Day 5-6: 테스트(중복, null, FK) 강화
4. Day 7-8: 문서화와 lineage 점검
5. Day 9-10: 품질 매크로/재사용 SQL 정리
6. Day 11-12: 성능 점검 + 포트폴리오 README 정리