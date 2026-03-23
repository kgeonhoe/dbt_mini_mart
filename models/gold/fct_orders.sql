select
    o.order_line_id,
    o.order_id,
    o.order_date as date_key,
    o.customer_id,
    o.product_id,
    o.seller_id,
    o.primary_payment_type as payment_type,
    o.order_status,
    o.order_item_id,
    o.order_item_count,
    o.item_price,
    o.freight_value,
    o.gross_item_amount,
    o.payment_total_value,
    o.avg_review_score
from {{ ref('int_orders_enriched') }} o
