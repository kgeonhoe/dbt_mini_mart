select
    seller_id,
    cast(seller_zip_code_prefix as varchar) as seller_zip_code_prefix,
    seller_city,
    seller_state
from {{ source('raw', 'olist_sellers') }}
