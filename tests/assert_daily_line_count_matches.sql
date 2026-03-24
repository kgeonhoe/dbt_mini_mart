-- fct_orders의 line_count와 fct_daily_sales의 line_count가 일치하는지 검증
with daily as (
    select sum(line_count) as total_lines from {{ ref('fct_daily_sales') }}
),
orders as (
    select count(*) as total_lines from {{ ref('fct_orders') }}
)
select
    daily.total_lines as daily_lines,
    orders.total_lines as orders_lines
from daily
cross join orders
where daily.total_lines != orders.total_lines
