{% docs project_overview %}
mini_mart는 Olist 공개 CSV를 raw 계층에 적재한 뒤, dbt에서 source 기반으로 스타스키마를 구성하는 학습 프로젝트입니다.

- Grain: 주문 아이템(order item)
- Fact: fct_orders
- Dimensions: dim_customer, dim_product, dim_seller, dim_payment_type, dim_date
- Warehouse: DuckDB
{% enddocs %}

{% docs layer_raw %}
### Raw 계층
DuckDB `raw` 스키마에 적재된 Olist 원천 CSV 데이터입니다.
`scripts/load_raw_to_duckdb.py`로 벌크 로드하며, dbt에서는 `source()`로 참조합니다.
이 계층의 테이블은 원천 그대로 유지하고, 변환은 staging에서 수행합니다.
{% enddocs %}

{% docs layer_staging %}
### Staging 계층
Raw source를 읽어 타입 캐스팅, 컬럼 리네이밍, 단순 조인만 수행하는 뷰입니다.

- 네이밍: `stg_<entity>`
- Materialization: view
- 비즈니스 로직은 포함하지 않습니다.
{% enddocs %}

{% docs layer_intermediate %}
### Intermediate 계층
여러 staging 모델을 결합하여 비즈니스 로직(주결제수단 선정, 리뷰 평균, 아이템 수 계산)을 적용하는 중간 모델입니다.

- 네이밍: `int_<domain>_<verb>`
- Materialization: view
- 외부에 직접 노출하지 않고 gold 계층에서만 참조합니다.
{% enddocs %}

{% docs layer_gold %}
### Gold 계층
최종 분석용 스타스키마 모델입니다. 차원(dim_*)과 팩트(fct_*)로 구성됩니다.

- Materialization: table
- fct_orders: 주문 아이템 grain의 중심 팩트
- fct_daily_sales: 날짜·판매자 기준 집계 팩트
- 5개 차원: customer, product, seller, payment_type, date
{% enddocs %}

{% docs grain_order_line %}
이 모델의 Grain은 **주문 아이템(order line)**입니다.
한 주문(order_id)에 여러 아이템이 포함될 수 있으며, `order_line_id = order_id || '-' || order_item_id`가 PK입니다.
{% enddocs %}

{% docs primary_payment_type %}
한 주문에 복수 결제수단이 사용될 수 있습니다.
`primary_payment_type`은 결제 금액 합계가 가장 큰 수단을 선정하며,
동점 시 payment_type의 알파벳 순으로 결정됩니다.
결제 정보가 없으면 `'unknown'`으로 기본값이 설정됩니다.
{% enddocs %}
