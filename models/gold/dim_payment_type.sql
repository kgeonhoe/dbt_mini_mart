select distinct
    payment_type,
    replace(payment_type, '_', ' ') as payment_type_label
from {{ ref('stg_payments') }}