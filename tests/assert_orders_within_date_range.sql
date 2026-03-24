-- fct_orders의 모든 주문 날짜가 dim_date의 범위 안에 있는지 검증
with date_bounds as (
    select min(date_key) as min_dt, max(date_key) as max_dt
    from {{ ref('dim_date') }}
)
select
    f.order_line_id,
    f.date_key
from {{ ref('fct_orders') }} f
cross join date_bounds b
where f.date_key < b.min_dt
   or f.date_key > b.max_dt
