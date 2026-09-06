from pydantic import BaseModel


class RecommendationOut(BaseModel):
    priority: int
    action: str
    resource_type: str
    quantity: int
    reason: str
