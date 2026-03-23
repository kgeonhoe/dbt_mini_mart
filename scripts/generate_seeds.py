from __future__ import annotations

import csv
from pathlib import Path


RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

RAW_TABLES = [
    "olist_orders",
    "olist_order_items",
    "olist_order_payments",
    "olist_order_reviews",
    "olist_customers",
    "olist_products",
    "olist_sellers",
    "product_category_name_translation",
]


def write_csv(name: str, headers: list[str], rows: list[list[object]]) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (RAW_DATA_DIR / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def main() -> None:
    write_csv(
        "olist_customers",
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
        [
            ["c1", "u1", 1000, "sao paulo", "SP"],
            ["c2", "u2", 2000, "rio de janeiro", "RJ"],
            ["c3", "u3", 3000, "curitiba", "PR"],
            ["c4", "u4", 4000, "salvador", "BA"],
        ],
    )

    write_csv(
        "olist_sellers",
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        [
            ["s1", 1100, "sao paulo", "SP"],
            ["s2", 2200, "rio de janeiro", "RJ"],
            ["s3", 3300, "curitiba", "PR"],
        ],
    )

    write_csv(
        "product_category_name_translation",
        ["product_category_name", "product_category_name_english"],
        [
            ["beleza_saude", "health_beauty"],
            ["informatica_acessorios", "computers_accessories"],
            ["utilidades_domesticas", "housewares"],
        ],
    )

    write_csv(
        "olist_products",
        [
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ],
        [
            ["p1", "beleza_saude", 20, 100, 1, 500, 20, 10, 15],
            ["p2", "informatica_acessorios", 24, 130, 2, 700, 30, 8, 18],
            ["p3", "utilidades_domesticas", 16, 90, 1, 900, 25, 14, 20],
        ],
    )

    write_csv(
        "olist_orders",
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        [
            ["o1", "c1", "delivered", "2018-01-01 09:00:00", "2018-01-01 10:00:00", "2018-01-02 09:00:00", "2018-01-05 12:00:00", "2018-01-07 00:00:00"],
            ["o2", "c2", "delivered", "2018-01-03 11:00:00", "2018-01-03 11:15:00", "2018-01-04 08:00:00", "2018-01-08 15:00:00", "2018-01-09 00:00:00"],
            ["o3", "c3", "shipped", "2018-01-08 13:00:00", "2018-01-08 13:20:00", "2018-01-09 10:00:00", "", "2018-01-14 00:00:00"],
            ["o4", "c4", "canceled", "2018-01-10 17:00:00", "", "", "", "2018-01-15 00:00:00"],
        ],
    )

    write_csv(
        "olist_order_items",
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
        [
            ["o1", 1, "p1", "s1", "2018-01-03 00:00:00", 100.0, 15.0],
            ["o1", 2, "p2", "s2", "2018-01-03 00:00:00", 50.0, 8.0],
            ["o2", 1, "p3", "s3", "2018-01-05 00:00:00", 80.0, 10.0],
            ["o3", 1, "p2", "s1", "2018-01-10 00:00:00", 120.0, 12.0],
        ],
    )

    write_csv(
        "olist_order_payments",
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
        [
            ["o1", 1, "credit_card", 1, 165.0],
            ["o2", 1, "voucher", 1, 90.0],
            ["o3", 1, "credit_card", 2, 132.0],
            ["o4", 1, "boleto", 1, 0.0],
        ],
    )

    write_csv(
        "olist_order_reviews",
        ["review_id", "order_id", "review_score", "review_creation_date", "review_answer_timestamp"],
        [
            ["r1", "o1", 5, "2018-01-06", "2018-01-06 10:00:00"],
            ["r2", "o2", 4, "2018-01-10", "2018-01-10 11:00:00"],
            ["r3", "o3", 3, "2018-01-14", "2018-01-14 19:00:00"],
        ],
    )


if __name__ == "__main__":
    main()
