import os
from functools import lru_cache
from typing import Optional

import psycopg
from langchain_openai import OpenAIEmbeddings
from pgvector.psycopg import register_vector

from app.models import Product


DEFAULT_DATABASE_URL = (
    "postgresql://myuser:mysecretpassword@localhost:5439/mydatabase"
)
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 1536


def _database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _embedding_dimensions() -> int:
    dimensions = int(
        os.getenv("OPENAI_EMBEDDING_DIMENSIONS", DEFAULT_EMBEDDING_DIMENSIONS)
    )
    if dimensions <= 0:
        raise ValueError("OPENAI_EMBEDDING_DIMENSIONS must be greater than zero")
    return dimensions


@lru_cache(maxsize=1)
def _embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        dimensions=_embedding_dimensions(),
    )


def add_product(product: Product) -> None:
    """Embed and persist a product in the pgvector-backed catalog."""

    embedding = _embeddings().embed_query(product.embedding_text())
    dimensions = _embedding_dimensions()
    if len(embedding) != dimensions:
        raise ValueError(
            f"Expected an embedding with {dimensions} dimensions, got {len(embedding)}"
        )

    create_table = f"""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            unit_price_usd DOUBLE PRECISION NOT NULL,
            minimum_quantity INTEGER NOT NULL,
            lead_time_weeks INTEGER NOT NULL,
            supported_application TEXT NOT NULL,
            max_discount TEXT NOT NULL,
            embedding vector({dimensions}) NOT NULL
        )
    """

    with psycopg.connect(_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            register_vector(connection)
            cursor.execute(create_table)
            cursor.execute(
                """
                INSERT INTO products (
                    sku,
                    product_name,
                    unit_price_usd,
                    minimum_quantity,
                    lead_time_weeks,
                    supported_application,
                    max_discount,
                    embedding
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    product.sku,
                    product.product_name,
                    product.unit_price_usd,
                    product.minimum_quantity,
                    product.lead_time_weeks,
                    product.supported_application,
                    product.max_discount,
                    embedding,
                ),
            )


def list_products() -> list[Product]:
    """Return catalog products without exposing their embedding vectors."""

    dimensions = _embedding_dimensions()
    create_table = f"""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            unit_price_usd DOUBLE PRECISION NOT NULL,
            minimum_quantity INTEGER NOT NULL,
            lead_time_weeks INTEGER NOT NULL,
            supported_application TEXT NOT NULL,
            max_discount TEXT NOT NULL,
            embedding vector({dimensions}) NOT NULL
        )
    """

    with psycopg.connect(_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(create_table)
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
    """Return the closest products that also satisfy hard order constraints."""

    embedding = _embeddings().embed_query(query)
    dimensions = _embedding_dimensions()
    if len(embedding) != dimensions:
        raise ValueError(
            f"Expected an embedding with {dimensions} dimensions, got {len(embedding)}"
        )
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    create_table = f"""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            unit_price_usd DOUBLE PRECISION NOT NULL,
            minimum_quantity INTEGER NOT NULL,
            lead_time_weeks INTEGER NOT NULL,
            supported_application TEXT NOT NULL,
            max_discount TEXT NOT NULL,
            embedding vector({dimensions}) NOT NULL
        )
    """

    with psycopg.connect(_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            register_vector(connection)
            cursor.execute(create_table)
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
                    1 - (embedding <=> %s) AS similarity
                FROM products
                WHERE (%s::integer IS NULL OR minimum_quantity <= %s)
                  AND (%s::integer IS NULL OR lead_time_weeks <= %s)
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (
                    embedding,
                    quantity,
                    quantity,
                    delivery_weeks,
                    delivery_weeks,
                    embedding,
                    limit,
                ),
            )
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
