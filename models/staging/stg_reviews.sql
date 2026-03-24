select
    review_id,
    order_id,
    cast(review_score as integer) as review_score,
    cast(review_creation_date as date) as review_creation_date,
    cast(review_answer_timestamp as timestamp) as review_answer_ts
from {{ source('raw', 'olist_order_reviews') }}
