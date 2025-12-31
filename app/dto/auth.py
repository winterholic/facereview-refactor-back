from dataclasses import dataclass

from app.models import User


@dataclass
class AuthTokenDto:
    access_token: str
    refresh_token: str

@dataclass
class UserBaseDataDto:
    user_id: str
    email: str
    name: str
    profile_image_id: int
    is_verify_email_done: bool
    is_tutorial_done: bool
    role: str
    created_at: object  # datetime 객체 (Schema가 직렬화)
    favorite_genres: list