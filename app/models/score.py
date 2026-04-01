from pydantic import BaseModel, Field, field_validator, ConfigDict

class ScoreIn(BaseModel):
    score: int = Field(..., ge=0, le=999999)

    model_config = ConfigDict(extra='ignore')

class ScoreOut(BaseModel):
    rank: int
    username: str
    score: int

class LeaderboardResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[ScoreOut]