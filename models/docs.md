{% docs project_overview %}
mini_mart는 Olist 공개 CSV를 raw 계층에 적재한 뒤, dbt에서 source 기반으로 스타스키마를 구성하는 학습 프로젝트입니다.

- Grain: 주문 아이템(order item)
- Fact: fct_orders
- Dimensions: dim_customer, dim_product, dim_seller, dim_payment_type, dim_date
- Warehouse: DuckDB
{% enddocs %}
