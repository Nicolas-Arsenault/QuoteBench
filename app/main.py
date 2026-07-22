import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response, status
from openai import OpenAIError
from pydantic import BaseModel
from psycopg.errors import UniqueViolation

from app.comparison import run_model_comparison
from app.graph import FinalState, quote_graph
from app.models import Product
from app.retrieval import add_product


load_dotenv()


app = FastAPI(
    title="Semiconductor Order API",
    version="1.0.0",
)


class ClientMessage(BaseModel):
    message: str


@app.get("/health")
def read_root():
    return {"message": "Healthy!"}


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
    except (OpenAIError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The product embedding could not be generated",
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
    except (OpenAIError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The quote workflow could not be completed",
        ) from exc

    if result.status == "human_review_required":
        response.status_code = status.HTTP_202_ACCEPTED

    return result


@app.post("/compare")
def compare(data: ClientMessage):
    return run_model_comparison(data.message)
