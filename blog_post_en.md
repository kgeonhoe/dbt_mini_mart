# Building a Local Star Schema Data Mart with dbt + DuckDB + Dagster

> Using the Olist e-commerce public dataset to implement a 4-layer dbt modeling pipeline → star schema → Dagster orchestration.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack and Design Choices](#2-tech-stack-and-design-choices)
3. [Architecture Design](#3-architecture-design)
4. [Implementation](#4-implementation)
   - [Environment Setup](#4-1-environment-setup)
   - [Raw Layer — Source Data Ingestion](#4-2-raw-layer--source-data-ingestion)
   - [Staging Layer — Type Casting and Cleansing](#4-3-staging-layer--type-casting-and-cleansing)
   - [Intermediate Layer — Business Logic](#4-4-intermediate-layer--business-logic)
   - [Gold Layer — Star Schema](#4-5-gold-layer--star-schema)
   - [Testing and Documentation](#4-6-testing-and-documentation)
   - [Dagster Orchestration](#4-7-dagster-orchestration)
5. [Retrospective](#5-retrospective)

---

## 1. Project Overview

**dbt_mini_mart** is a learning-oriented data mart project using Kaggle's [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

- 8 source CSV tables → **14 dbt models** → final **star schema** data mart
- 5 dimension tables (dim) + 2 fact tables (fct)
- 71 data quality tests + Dagster-based pipeline orchestration

### Source Data Structure

The Olist dataset consists of Brazilian e-commerce order data across 8 tables:

| Table | Description | Grain |
|-------|-------------|-------|
| `olist_orders` | Order header (status, timestamps) | order_id |
| `olist_order_items` | Order line items (price, freight) | order_id + order_item_id |
| `olist_order_payments` | Payment records (method, amount) | order_id + payment_sequential |
| `olist_order_reviews` | Reviews (score) | review_id |
| `olist_customers` | Customer master | customer_id |
| `olist_products` | Product attributes (category, weight) | product_id |
| `olist_sellers` | Seller master | seller_id |
| `product_category_name_translation` | Category name translation (PT → EN) | product_category_name |

---

## 2. Tech Stack and Design Choices

### Full Stack

| Tool | Role | Version |
|------|------|---------|
| **dbt-core** | SQL modeling, testing, documentation | 1.8+ |
| **DuckDB** | Local OLAP warehouse | 1.0+ |
| **Dagster** | Pipeline orchestration | 1.12+ |
| **uv** | Python dependency management | - |
| **dbt_utils** | Utility macros/test package | 1.1+ |

This project focuses on data warehouse design through dbt, so a lightweight local database was chosen.

dbt-DuckDB connection setup:
```yaml
# profiles.yml
mini_mart:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: mini_mart.duckdb
      threads: 4
```

### Why Not dbt seed?

dbt seed works well for small reference tables, but bulk-loading tens of thousands of source rows via seed on every run is inefficient.

- In production, dbt seed is rarely used beyond small dimension tables.

This project **bulk-loads CSV files into DuckDB via a Python script** and references them in dbt through `source()`:

```python
# scripts/load_raw_to_duckdb.py (core logic)
con.execute("""
    create or replace table raw.{table} as
    select *, current_timestamp as _loaded_at
    from read_csv_auto(?, header=true)
""", [str(csv_path)])
```

The **`_loaded_at` column is automatically added** to integrate with dbt's source freshness feature.

### Why Dagster?

Reasons for choosing Dagster over Airflow:

- **Asset-centric paradigm**: dbt models automatically map to Dagster Assets
- **dagster-dbt integration**: Manifest-based DAG auto-generation — no custom operator needed
- **Asset Catalog exposes dbt metadata**: Model descriptions, column info, SQL, and test status from schema.yml are directly visible in the Dagster UI. In Airflow, dbt runs as a plain task, so this metadata is not accessible from the orchestrator.
- **Local development friendly**: A single `dagster dev` command spins up the web UI and execution environment

---

## 3. Architecture Design

### 4-Layer Modeling (Layered Architecture)

```mermaid
flowchart TB
  subgraph Raw_Layer[Raw Layer]
    raw_orders[olist_orders]
    raw_items[olist_order_items]
    raw_payments[olist_order_payments]
    raw_reviews[olist_order_reviews]
    raw_customers[olist_customers]
    raw_products[olist_products]
    raw_sellers[olist_sellers]
    raw_trans[product_category_name_translation]
  end

  subgraph Staging_Layer[Staging Layer]
    stg_orders[stg_orders]
    stg_customers[stg_customers]
    stg_payments[stg_payments]
    stg_products[stg_products]
    stg_reviews[stg_reviews]
    stg_sellers[stg_sellers]
  end

  subgraph Intermediate_Layer[Intermediate Layer]
    int_orders[int_orders_enriched]
  end

  subgraph Gold_Layer[Gold Layer]
    dim_customer[dim_customer]
    dim_product[dim_product]
    dim_payment[dim_payment_type]
    dim_seller[dim_seller]
    dim_date[dim_date]
    fct_orders[fct_orders]
    fct_daily[fct_daily_sales]
  end

  raw_orders --> stg_orders
  raw_items --> stg_orders
  raw_customers --> stg_customers
  raw_payments --> stg_payments
  raw_products --> stg_products
  raw_trans --> stg_products
  raw_reviews --> stg_reviews
  raw_sellers --> stg_sellers

  stg_orders --> int_orders
  stg_payments --> int_orders
  stg_reviews --> int_orders

  stg_customers --> dim_customer
  stg_products --> dim_product
  stg_payments --> dim_payment
  stg_sellers --> dim_seller

  int_orders --> fct_orders
  dim_date --> fct_orders
  dim_customer --> fct_orders
  dim_product --> fct_orders
  dim_payment --> fct_orders
  dim_seller --> fct_orders

  fct_orders --> fct_daily
```

**Role of each layer:**

| Layer | Materialization | Role |
|-------|----------------|------|
| **Raw** | Table (Python load) | CSV → DuckDB bulk load. Auto-adds `_loaded_at` |
| **Staging** | View | Type casting, column renaming, simple joins |
| **Intermediate** | View | Combines multiple staging models, applies business logic |
| **Gold** | Table | Final star schema for analytics (dim + fct) |

### Star Schema Design

```
              dim_date
                 │
dim_customer ────┤
                 │
dim_product  ────┼──── fct_orders ──── fct_daily_sales
                 │                         (aggregated)
dim_seller   ────┤
                 │
dim_payment_type─┘
```

**fct_orders** (Grain: order item)
- 1 row = 1 order line item
- 5 dimension FKs: customer_id, product_id, seller_id, payment_type, date_key
- Measures: item_price, freight_value, gross_item_amount, payment_total_value, avg_review_score

**fct_daily_sales** (Grain: date + seller)
- Aggregated from fct_orders
- Measures: order_count, line_count, item_sales, freight_sales, gross_sales

### Grain Design Decision

The most critical design decision in this project was **setting the analysis grain to "order item"**.

In the Olist dataset, a single order (order_id) can contain multiple items. By choosing **order items (order_items)** as the grain instead of order headers (orders), per-product and per-seller analysis becomes possible.

The PK was designed as `order_line_id = order_id || '-' || order_item_id`, extracted into a macro:

```sql
-- macros/generate_order_line_id.sql
{% macro generate_order_line_id(order_id_col, item_id_col) %}
    concat({{ order_id_col }}, '-', cast({{ item_id_col }} as varchar))
{% endmacro %}
```

---

## 4. Implementation

### 4-1. Environment Setup

#### Python Environment (uv)

```bash
# Initialize project with uv
uv init dbt_mini_mart
cd dbt_mini_mart

# Add dependencies
uv add dbt-duckdb "duckdb>=1.0,<2.0"
uv add dagster dagster-dbt dagster-webserver
```

#### dbt Project Configuration

```yaml
# dbt_project.yml
name: mini_mart
version: 1.0.0
config-version: 2
profile: mini_mart

models:
  mini_mart:
    staging:
      +materialized: view       # Minimize transformation cost
      +schema: stg
    intermediate:
      +materialized: view       # Keep intermediate results as views
      +schema: int
    gold:
      +materialized: table      # Materialize final analytics layer
      +schema: gold
```

> **Materialization strategy**: Staging/Intermediate use views to reduce cost since they are simple transformations. Gold uses tables for analytics query performance.

#### Package Installation

```yaml
# packages.yml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.1.0", "<2.0.0"]
```

```bash
dbt deps
```

Features used from `dbt_utils`:
- `date_spine()`: Generate dim_date
- `unique_combination_of_columns`: Composite PK uniqueness test
- `accepted_range`: Value range validation

---

### 4-2. Raw Layer — Source Data Ingestion

Since dbt seed is designed for small reference tables, source data is **bulk-loaded directly into DuckDB via a Python script**.

```python
# scripts/load_raw_to_duckdb.py
con = duckdb.connect(str(DB_PATH))
con.execute("create schema if not exists raw")

for table in RAW_TABLES:
    csv_path = resolve_csv_path(table, source_dir)
    con.execute("""
        create or replace table raw.{table} as
        select *, current_timestamp as _loaded_at
        from read_csv_auto(?, header=true)
    """, [str(csv_path)])
```

**Design points:**

1. **Auto-adds `_loaded_at`** — Integrates with dbt source freshness
2. **Filename candidate mapping** — Supports both Kaggle originals (`*_dataset.csv`) and processed files (`*.csv`)
3. **Source directory priority** — CLI arg → env var (`MINI_MART_SOURCE_DIR`) → `data/common` → `data/raw`

dbt references the raw layer via `source()`:

```yaml
# models/raw/raw_sources.yml
sources:
  - name: raw
    schema: raw
    loaded_at_field: _loaded_at
    freshness:
      warn_after: { count: 24, period: hour }
      error_after: { count: 72, period: hour }
    tables:
      - name: olist_orders
        columns:
          - name: order_id
            tests: [unique, not_null]
      # ... all 8 tables defined
```

Execution:

```bash
# Load CSV → DuckDB
python scripts/load_raw_to_duckdb.py

# Check freshness
dbt source freshness
```

---

### 4-3. Staging Layer — Type Casting and Cleansing

Staging principle: **Only reshape the source data's "form" — no business logic.**

#### stg_orders — Grain Change Is Key

```sql
-- models/staging/stg_orders.sql
with orders as (
    select * from {{ source('raw', 'olist_orders') }}
),
lines as (
    select * from {{ source('raw', 'olist_order_items') }}
)
select
    {{ generate_order_line_id('l.order_id', 'l.order_item_id') }}
        as order_line_id,
    o.order_id,
    o.customer_id,
    l.seller_id,
    cast(o.order_purchase_timestamp as timestamp) as order_purchase_ts,
    cast(o.order_purchase_timestamp as date)      as order_date,
    o.order_status,
    l.product_id,
    cast(l.order_item_id as integer) as order_item_id,
    cast(l.price as double)          as item_price,
    cast(l.freight_value as double)  as freight_value,
    cast(l.price as double) + cast(l.freight_value as double) as gross_item_amount
from lines l
join orders o on l.order_id = o.order_id
```

Key decisions here:
- **Inner join** between `olist_orders` (order header) and `olist_order_items` (line items)
- Grain changes from `order_id` → `order_line_id` (order item)
- Derived column `gross_item_amount = item_price + freight_value`

#### stg_products — Translation Table Join

```sql
-- models/staging/stg_products.sql
select
    p.product_id,
    p.product_category_name,
    t.product_category_name_english,   -- Portuguese → English
    cast(p.product_weight_g as integer) as product_weight_g,
    -- ...
from {{ source('raw', 'olist_products') }} p
left join {{ source('raw', 'product_category_name_translation') }} t
    on p.product_category_name = t.product_category_name
```

**LEFT JOIN is used** to avoid dropping products with untranslated categories.

#### Other Staging Models

| Model | Core Transformation |
|-------|-------------------|
| `stg_customers` | Cast zip_code as varchar (preserve leading zeros) |
| `stg_payments` | payment_value → double, payment_sequential → integer |
| `stg_reviews` | review_score → integer, exclude text comments |
| `stg_sellers` | Cast zip_code as varchar |

---

### 4-4. Intermediate Layer — Business Logic

`int_orders_enriched` combines multiple staging models to create derived columns for analysis.

```sql
-- models/intermediate/int_orders_enriched.sql (core logic)

-- 1. Total payment per order
payment_by_order as (
    select order_id, sum(payment_value) as payment_total_value
    from {{ ref('stg_payments') }}
    group by 1
),

-- 2. Primary payment type selection (highest amount)
payment_type_ranked as (
    select
        order_id, payment_type,
        row_number() over (
            partition by order_id
            order by sum(payment_value) desc, payment_type
        ) as rn
    from {{ ref('stg_payments') }}
    group by 1, 2
),

-- 3. Average review score per order
review_by_order as (
    select order_id, avg(cast(review_score as double)) as avg_review_score
    from {{ ref('stg_reviews') }}
    group by 1
),

-- 4. Item count per order
item_count as (
    select order_id, count(*) as order_item_count
    from base
    group by 1
)
```

**Derived columns summary:**

| Column | Logic | Default |
|--------|-------|---------|
| `payment_total_value` | Sum of all payments for the order | 0 |
| `primary_payment_type` | Payment method with highest total amount | 'unknown' |
| `avg_review_score` | Average review score for the order | NULL |
| `order_item_count` | Number of items in the order | — |

> **Design intent**: `primary_payment_type` handles the case where an order uses multiple payment methods. The method with the highest total amount is selected as the representative value. Ties are broken alphabetically by payment_type.

---

### 4-5. Gold Layer — Star Schema

The Gold layer constructs the final star schema. Materialization is set to **table** for analytics query performance.

#### Dimension Tables

| Dimension | Source | Grain | Notes |
|-----------|--------|-------|-------|
| `dim_customer` | stg_customers | customer_id | pass-through |
| `dim_product` | stg_products | product_id | Includes English category |
| `dim_seller` | stg_sellers | seller_id | pass-through |
| `dim_payment_type` | stg_payments | payment_type | DISTINCT extraction + label |
| `dim_date` | dbt_utils.date_spine | date_key | 2016-01-01 ~ 2019-01-01 |

**dim_date** uses `dbt_utils.date_spine()` with project-wide macros:

```sql
-- macros/date_range.sql
{% macro date_range_start() %}
    cast('2016-01-01' as date)
{% endmacro %}

{% macro date_range_end() %}
    cast('2019-01-01' as date)
{% endmacro %}
```

```sql
-- models/gold/dim_date.sql
with spine as (
    {{ dbt_utils.date_spine(
        datepart='day',
        start_date=date_range_start(),
        end_date=date_range_end()
    ) }}
)
select
    cast(date_day as date) as date_key,
    extract(year from date_day) as year_num,
    extract(month from date_day) as month_num,
    extract(day from date_day) as day_num,
    strftime(date_day, '%Y-%m') as year_month,
    case when extract(dow from date_day) in (0, 6) then true else false end as is_weekend
from spine
```

> **Centralizing the date range in macros** ensures dim_date and data validation tests reference the same range, preventing mismatches.

#### Fact Tables

**fct_orders** — Order item grain

```sql
-- models/gold/fct_orders.sql
select
    o.order_line_id,
    o.order_date          as date_key,       -- → dim_date
    o.customer_id,                            -- → dim_customer
    o.product_id,                             -- → dim_product
    o.seller_id,                              -- → dim_seller
    o.primary_payment_type as payment_type,   -- → dim_payment_type
    o.order_status,
    o.order_item_id,
    o.order_item_count,
    o.item_price,
    o.freight_value,
    o.gross_item_amount,
    o.payment_total_value,
    o.avg_review_score
from {{ ref('int_orders_enriched') }} o
```

**fct_daily_sales** — Daily seller aggregation

```sql
-- models/gold/fct_daily_sales.sql
select
    date_key,
    seller_id,
    count(distinct order_id) as order_count,
    count(*)                 as line_count,
    sum(item_price)          as item_sales,
    sum(freight_value)       as freight_sales,
    sum(gross_item_amount)   as gross_sales
from {{ ref('fct_orders') }}
group by 1, 2
```

---

### 4-6. Testing and Documentation

#### Testing Strategy (71 tests)

This project uses **3 types of tests**:

**1) Generic Tests (Schema Tests)** — 63

Declaratively defined in each model's `_schema.yml`:

```yaml
# models/gold/gold_schema.yml (example)
models:
  - name: fct_orders
    columns:
      - name: order_line_id
        tests: [unique, not_null]
      - name: customer_id
        tests:
          - relationships:
              to: ref('dim_customer')
              field: customer_id
      - name: item_price
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
```

Test types breakdown:

| Type | Count | Example |
|------|-------|---------|
| unique / not_null | 20+ | PK integrity |
| relationships | 5 | FK referential integrity (fct_orders → 5 dims) |
| accepted_values | 2 | payment_type allowed values |
| accepted_range | 6 | Amount >= 0, review score 1~5 |
| unique_combination_of_columns | 1 | fct_daily_sales composite PK |

**2) Source Freshness** — 8

```yaml
freshness:
  warn_after: { count: 24, period: hour }
  error_after: { count: 72, period: hour }
```

Applied to all raw tables. Monitors data freshness based on the `_loaded_at` column.

**3) Singular Tests (Custom Validations)** — 3

```sql
-- tests/assert_daily_sales_reconciles.sql
-- Validates reconciliation between fct_daily_sales and fct_orders totals
with daily as (
    select sum(gross_sales) as total from {{ ref('fct_daily_sales') }}
),
orders as (
    select sum(gross_item_amount) as total from {{ ref('fct_orders') }}
)
select *
from daily cross join orders
where abs(daily.total - orders.total) > 0.01   -- tolerance for floating point
```

| Test | Validation |
|------|-----------|
| `assert_daily_line_count_matches` | fct_daily_sales line_count sum = fct_orders total rows |
| `assert_daily_sales_reconciles` | fct_daily_sales gross_sales sum = fct_orders gross_item_amount sum |
| `assert_orders_within_date_range` | All order dates fall within dim_date range (2016~2019) |

#### Documentation

dbt docs blocks keep business context alongside code:

```markdown
<!-- models/docs.md -->
{% docs grain_order_line %}
The grain of this model is **order line (order item)**.
A single order (order_id) can contain multiple items.
`order_line_id = order_id || '-' || order_item_id` serves as the PK.
{% enddocs %}

{% docs primary_payment_type %}
An order can use multiple payment methods.
`primary_payment_type` selects the method with the highest payment total.
Ties are broken alphabetically by payment_type.
{% enddocs %}
```

```bash
dbt docs generate && dbt docs serve
```

---

### 4-7. Dagster Orchestration

dbt models are automatically mapped to Dagster Assets, enabling DAG visualization and execution from the web UI.

#### Project Setup

```python
# dagster_mini_mart/project.py
from dagster_dbt import DbtProject

dbt_project = DbtProject(
    project_dir=DAGSTER_DBT_PROJECT_DIR,
    target_path=DAGSTER_DBT_PROJECT_DIR / "target",
)
dbt_project.prepare_if_dev()
```

#### Asset Definition

```python
# dagster_mini_mart/assets.py
from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_mini_mart_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
```

The `@dbt_assets` decorator reads the dbt manifest to auto-generate **14 dbt models + 8 sources = 22 Dagster Assets**. `dbt build` runs model builds and tests in DAG order.

#### Asset Catalog — How dbt Metadata Surfaces in Dagster UI

When `@dbt_assets(manifest=...)` parses the manifest, it reads descriptions, column info, test lists, and raw SQL from dbt schema.yml and registers them as Dagster Asset metadata.

This means the Dagster UI Asset Catalog shows:

- Per-model **Description** (including docs blocks)
- **Raw SQL** source
- Per-column descriptions and **Generic Data Tests** status

— all without opening the code repository.

In Airflow, dbt runs as a task through `BashOperator` or Cosmos, and model-level descriptions, SQL, and test metadata are not exposed in the Airflow UI. This difference was one of the most practical reasons for choosing Dagster for a dbt project.

#### Definitions

```python
# dagster_mini_mart/definitions.py
defs = Definitions(
    assets=[dbt_mini_mart_dbt_assets],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project),
    },
)
```

#### Execution

```bash
dagster dev
# → http://localhost:3000 to view and run the Asset DAG
```

---

## 5. Retrospective

### What Went Well

- **Defining the grain first drove every downstream decision.** Choosing order_line_id as the PK became the foundation for all joins and aggregations.
- **Centralizing logic in macros maintained consistency.** Referencing `date_range_start/end` in both dim_date and tests eliminated range mismatch bugs at the source.
- **DuckDB enabled rapid iteration.** Testing tens of thousands of rows locally with zero cloud cost.

### Challenges

- **Handling the 1:N payment relationship**: An order can use multiple payment methods, requiring `primary_payment_type` selection logic.
- **Drawing the line between cleansing and business logic in Staging**: The guiding principle was "the moment information from two or more tables is combined, it moves to Intermediate."

### Future Improvements

- Incremental model adoption (large-scale scenarios)
- dbt Metrics / Semantic Layer introduction
- CI/CD automation for `dbt build` + `dagster asset materialize`

---

## Project Links

- **GitHub**: [kgeonhoe/dbt_mini_mart](https://github.com/kgeonhoe/dbt_mini_mart)
- **Dataset**: [Olist Brazilian E-Commerce Dataset (Kaggle)](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
