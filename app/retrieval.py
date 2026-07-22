import os
from typing import Optional

import psycopg

from app.models import Product


DEFAULT_DATABASE_URL = (
    "postgresql://myuser:mysecretpassword@localhost:5439/mydatabase"
)


def _database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _ensure_products_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            unit_price_usd DOUBLE PRECISION NOT NULL,
            minimum_quantity INTEGER NOT NULL,
            lead_time_weeks INTEGER NOT NULL,
            supported_application TEXT NOT NULL,
            max_discount TEXT NOT NULL
        )
        """
    )
    # Remove the legacy OpenAI embedding column when upgrading an existing DB.
    cursor.execute("ALTER TABLE products DROP COLUMN IF EXISTS embedding")


def add_product(product: Product) -> None:
    """Persist a product in the local PostgreSQL catalog."""

    with psycopg.connect(_database_url()) as connection:
        with connection.cursor() as cursor:
            _ensure_products_table(cursor)
            cursor.execute(
                """
                INSERT INTO products (
                    sku,
                    product_name,
                    unit_price_usd,
                    minimum_quantity,
                    lead_time_weeks,
                    supported_application,
                    max_discount
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    product.sku,
                    product.product_name,
                    product.unit_price_usd,
                    product.minimum_quantity,
                    product.lead_time_weeks,
                    product.supported_application,
                    product.max_discount,
                ),
            )


def list_products() -> list[Product]:
    """Return all catalog products."""

    with psycopg.connect(_database_url()) as connection:
        with connection.cursor() as cursor:
            _ensure_products_table(cursor)
            cursor.execute(
                """
                SELECT
                    sku,
                    product_name,
                    unit_price_usd,
                    minimum_quantity,
                    lead_time_weeks,
                    supported_application,
                    max_discount
                FROM products
                ORDER BY sku
                """
            )
            columns = [column.name for column in cursor.description]
            return [
                Product.model_validate(dict(zip(columns, row)))
                for row in cursor.fetchall()
            ]


def search_products(
    query: str,
    quantity: Optional[int] = None,
    delivery_weeks: Optional[int] = None,
    limit: int = 5,
) -> list:
    """Return text-ranked products that satisfy hard order constraints."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    search_text = query.strip()

    with psycopg.connect(_database_url()) as connection:
        with connection.cursor() as cursor:
            _ensure_products_table(cursor)
            cursor.execute(
                """
                SELECT
                    sku,
                    product_name,
                    unit_price_usd,
                    minimum_quantity,
                    lead_time_weeks,
                    supported_application,
                    max_discount,
                    CASE
                        WHEN %s = '' THEN 0.0
                        ELSE ts_rank(
                            to_tsvector(
                                'english',
                                product_name || ' ' || supported_application
                            ),
                            plainto_tsquery('english', %s)
                        )
                    END AS similarity
                FROM products
                WHERE (%s::integer IS NULL OR minimum_quantity <= %s)
                  AND (%s::integer IS NULL OR lead_time_weeks <= %s)
                ORDER BY similarity DESC, sku
                LIMIT %s
                """,
                (
                    search_text,
                    search_text,
                    quantity,
                    quantity,
                    delivery_weeks,
                    delivery_weeks,
                    limit,
                ),
            )
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
