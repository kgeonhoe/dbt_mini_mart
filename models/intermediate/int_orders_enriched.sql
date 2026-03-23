with base as (
    select * from {{ ref('stg_orders') }}
),
payment_by_order as (
    select
        order_id,
        sum(cast(payment_value as double)) as payment_total_value
    from {{ source('raw', 'olist_order_payments') }}
    group by 1
),
payment_type_ranked as (
    select
        order_id,
        payment_type,
        sum(cast(payment_value as double)) as payment_type_value,
        row_number() over (
            partition by order_id
            order by sum(cast(payment_value as double)) desc, payment_type
        ) as rn
    from {{ source('raw', 'olist_order_payments') }}
    group by 1, 2
),
primary_payment_type as (
    select
        order_id,
        payment_type as primary_payment_type
    from (
        select * from payment_type_ranked
    ) p
    where rn = 1
),
review_by_order as (
    select
        order_id,
        avg(cast(review_score as double)) as avg_review_score
    from {{ source('raw', 'olist_order_reviews') }}
    group by 1
),
item_count as (
    select
        order_id,
        count(*) as order_item_count
    from base
    group by 1
)
select
    b.order_line_id,
    b.order_id,
    b.customer_id,
    b.seller_id,
    b.order_purchase_ts,
    b.order_date,
    b.order_status,
    b.product_id,
    b.order_item_id,
    b.item_price,
    b.freight_value,
    b.gross_item_amount,
    ic.order_item_count,
    coalesce(pbo.payment_total_value, 0) as payment_total_value,
    coalesce(ppt.primary_payment_type, 'unknown') as primary_payment_type,
    rb.avg_review_score
from base b
left join payment_by_order pbo on b.order_id = pbo.order_id
left join primary_payment_type ppt on b.order_id = ppt.order_id
left join review_by_order rb on b.order_id = rb.order_id
left join item_count ic on b.order_id = ic.order_id
