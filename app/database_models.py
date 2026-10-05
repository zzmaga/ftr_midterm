"""Transport schema, without importing database startup side effects."""
from pydantic import BaseModel, Field


class PaymentInput(BaseModel):
    student_id: str = Field(min_length=1, max_length=30)
    amount: int = Field(gt=0, le=100000, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=100)
