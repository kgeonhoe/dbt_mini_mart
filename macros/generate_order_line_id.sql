{% macro generate_order_line_id(order_id_col, item_id_col) %}
    concat({{ order_id_col }}, '-', cast({{ item_id_col }} as varchar))
{% endmacro %}
