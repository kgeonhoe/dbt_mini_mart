select distinct
    payment_type,
    replace(payment_type, '_', ' ') as payment_type_label
from {{ source('raw', 'olist_order_payments') }}