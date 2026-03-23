select
    date_key,
    seller_id,
    count(distinct order_id) as order_count,
    count(*) as line_count,
    sum(item_price) as item_sales,
    sum(freight_value) as freight_sales,
    sum(gross_item_amount) as gross_sales
from {{ ref('fct_orders') }}
group by 1, 2
