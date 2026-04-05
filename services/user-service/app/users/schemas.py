from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: str

    model_config = {"from_attributes": True}
