from pydantic import BaseModel, ConfigDict, Field


class Product(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    unit_price_usd: float = Field(gt=0)
    minimum_quantity: int = Field(gt=0)
    lead_time_weeks: int = Field(gt=0)
    supported_application: str = Field(min_length=1)
    max_discount: str = Field(min_length=1)

    def embedding_text(self) -> str:
        return (
            f"SKU: {self.sku}\n"
            f"Product: {self.product_name}\n"
            f"Supported applications: {self.supported_application}"
        )
