"""Olist Mini Mart — Streamlit Dashboard

DuckDB gold 레이어 테이블을 직접 연결하여
매출 트렌드, 결제수단 분포, 카테고리별 매출, 고객 지역 분포를 시각화합니다.

실행: uv run streamlit run streamlit_app.py
"""

from pathlib import Path

import duckdb
import plotly.express as px
import streamlit as st

# ── 설정 ──────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "mini_mart.duckdb"
GOLD = "main_gold"

st.set_page_config(
    page_title="Olist Mini Mart Dashboard",
    page_icon="📊",
    layout="wide",
)


@st.cache_resource
def get_connection():
    return duckdb.connect(str(DB_PATH), read_only=True)


def query(sql: str):
    con = get_connection()
    return con.execute(sql).fetchdf()


# ── KPI 요약 ─────────────────────────────────────────────────────
st.title("📊 Olist Mini Mart Dashboard")
st.caption("dbt gold 레이어 기반 · DuckDB · Streamlit")

kpi = query(f"""
    SELECT
        count(DISTINCT order_id)   AS total_orders,
        count(*)                   AS total_items,
        sum(gross_item_amount)     AS total_revenue,
        avg(avg_review_score)      AS avg_review
    FROM {GOLD}.fct_orders
""")

c1, c2, c3, c4 = st.columns(4)
c1.metric("주문 수", f"{kpi['total_orders'][0]:,}")
c2.metric("주문 아이템 수", f"{kpi['total_items'][0]:,}")
c3.metric("총 매출", f"R$ {kpi['total_revenue'][0]:,.2f}")
c4.metric("평균 리뷰 점수", f"{kpi['avg_review'][0]:.1f} / 5")

st.divider()

# ── Tile 1: 일별 매출 추이 (temporal) ────────────────────────────
st.subheader("📈 일별 매출 추이")

daily = query(f"""
    SELECT
        date_key,
        sum(gross_sales)  AS gross_sales,
        sum(order_count)  AS order_count
    FROM {GOLD}.fct_daily_sales
    GROUP BY date_key
    ORDER BY date_key
""")

fig_daily = px.area(
    daily,
    x="date_key",
    y="gross_sales",
    labels={"date_key": "날짜", "gross_sales": "매출 (R$)"},
    hover_data={"order_count": True},
)
fig_daily.update_layout(hovermode="x unified")
st.plotly_chart(fig_daily, use_container_width=True)

# ── Tile 2: 결제수단 분포 (categorical) ──────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("💳 결제수단별 주문 비율")

    payment = query(f"""
        SELECT
            p.payment_type_label AS payment_type,
            count(*)             AS cnt
        FROM {GOLD}.fct_orders f
        JOIN {GOLD}.dim_payment_type p ON f.payment_type = p.payment_type
        GROUP BY 1
        ORDER BY 2 DESC
    """)

    fig_pay = px.pie(
        payment,
        names="payment_type",
        values="cnt",
        hole=0.4,
    )
    st.plotly_chart(fig_pay, use_container_width=True)

# ── Tile 3: 카테고리별 매출 TOP 10 ──────────────────────────────
with col_right:
    st.subheader("🏷️ 상품 카테고리별 매출 TOP 10")

    category = query(f"""
        SELECT
            coalesce(p.product_category_name_english, 'unknown') AS category,
            sum(f.gross_item_amount) AS revenue
        FROM {GOLD}.fct_orders f
        JOIN {GOLD}.dim_product p ON f.product_id = p.product_id
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10
    """)

    fig_cat = px.bar(
        category,
        x="revenue",
        y="category",
        orientation="h",
        labels={"revenue": "매출 (R$)", "category": ""},
    )
    fig_cat.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_cat, use_container_width=True)

# ── Tile 4: 고객 지역(주) 분포 ───────────────────────────────────
st.subheader("🗺️ 고객 분포 (브라질 주별)")

state = query(f"""
    SELECT
        c.customer_state AS state,
        count(DISTINCT f.order_id) AS orders
    FROM {GOLD}.fct_orders f
    JOIN {GOLD}.dim_customer c ON f.customer_id = c.customer_id
    GROUP BY 1
    ORDER BY 2 DESC
""")

fig_state = px.bar(
    state,
    x="state",
    y="orders",
    labels={"state": "주(州)", "orders": "주문 수"},
    color="orders",
    color_continuous_scale="Blues",
)
st.plotly_chart(fig_state, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────
st.divider()
st.caption("Data: Olist Brazilian E-Commerce · Pipeline: dlt → dbt → DuckDB · Orchestration: Dagster")
