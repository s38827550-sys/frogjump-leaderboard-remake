from pydantic import BaseModel, Field, field_validator, ConfigDict

class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=16)
    nickname: str = Field(..., min_length=2, max_length=16)
    password: str = Field(..., min_length=6)

    @field_validator('username', 'nickname')
    @classmethod
    def clean_field(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('Field cannot be empty')
        return cleaned

    model_config = ConfigDict(str_strip_whitespace=True, extra='ignore')

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"