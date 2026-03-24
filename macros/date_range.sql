{% macro date_range_start() %}
    cast('2016-01-01' as date)
{% endmacro %}

{% macro date_range_end() %}
    cast('2019-01-01' as date)
{% endmacro %}
