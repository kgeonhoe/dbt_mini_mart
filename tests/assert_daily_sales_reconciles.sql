-- fct_daily_sales의 gross_sales 합계가 fct_orders의 gross_item_amount 합계와 일치하는지 검증
with daily as (
    select sum(gross_sales) as total from {{ ref('fct_daily_sales') }}
),
orders as (
    select sum(gross_item_amount) as total from {{ ref('fct_orders') }}
)
select
    daily.total as daily_total,
    orders.total as orders_total,
    abs(daily.total - orders.total) as diff
from daily
cross join orders
where abs(daily.total - orders.total) > 0.01
