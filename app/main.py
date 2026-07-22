from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from psycopg.errors import UniqueViolation

from app.graph import FinalState, quote_graph
from app.models import Product
from app.retrieval import add_product, list_products


load_dotenv()


UI_PATH = Path(__file__).parent / "static" / "index.html"


app = FastAPI(
    title="Semiconductor Order API",
    version="1.0.0",
)


class ClientMessage(BaseModel):
    message: str


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/health")
def read_root():
    return {"message": "Healthy!"}


@app.get("/products", response_model=list[Product])
def read_products() -> list[Product]:
    try:
        return list_products()
    except psycopg.OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The product database is unavailable",
        ) from exc
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The product catalog could not be read",
        ) from exc


@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(product: Product) -> Product:
    try:
        add_product(product)
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A product with SKU '{product.sku}' already exists",
        ) from exc
    except psycopg.OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The product database is unavailable",
        ) from exc
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The product could not be stored",
        ) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The product could not be processed",
        ) from exc

    return product


@app.post("/quote", response_model=FinalState)
def quotes(data: ClientMessage, response: Response) -> FinalState:
    try:
        result = FinalState.model_validate(
            quote_graph.invoke(FinalState(message=data.message))
        )
    except psycopg.OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The product database is unavailable",
        ) from exc
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The product catalog could not be searched",
        ) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The quote workflow could not be completed",
        ) from exc

    if result.status == "human_review_required":
        response.status_code = status.HTTP_202_ACCEPTED

    return result
