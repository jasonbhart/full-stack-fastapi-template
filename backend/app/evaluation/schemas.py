"""Schemas for evaluation."""

from pydantic import BaseModel, Field


class ScoreSchema(BaseModel):
    """Evaluation score schema."""

    score: float = Field(description="Score between 0 and 1")
    reasoning: str = Field(description="One sentence reasoning for the score")
