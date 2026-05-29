from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    """User profile fields returned by the /users/me endpoint."""

    id: str
    username: str
    email: str
    created_at: str

    model_config = {"from_attributes": True}
