from werkzeug.security import generate_password_hash, check_password_hash
import datetime

from app.dto.auth import AuthTokenDto, UserBaseDataDto
from app.models import UserFavoriteGenre
from app.models.user import User
from app.schemas.auth import LoginResponseSchema
from common.decorator.db_decorators import transactional, transactional_readonly
from common.enum.error_code import APIError
from common.enum.youtube_genre import GenreEnum
from common.exception.exceptions import BusinessError
from common.extensions import db, redis_client
from common.utils import create_access_token, create_refresh_token, decode_token
from common.utils.jwt_utils import create_test_token
from common.utils.logging_utils import get_logger

logger = get_logger('auth_service')


class AuthService:

    @staticmethod
    @transactional_readonly
    def check_duplicate_email(email: str) -> bool:
        user = User.query.filter_by(email=email).first()
        return user is not None

    @staticmethod
    @transactional
    def signup(email: str, password: str, name: str, favorite_genres: list) -> AuthTokenDto:
        if User.query.filter_by(email=email).first():
            raise BusinessError(APIError.AUTH_DUPLICATE_EMAIL)

        hashed_password = generate_password_hash(password)

        new_user = User(
            email=email,
            password=hashed_password,
            name=name,
            is_tutorial_done=False,
            role='GENERAL'
        )
        db.session.add(new_user)
        db.session.flush()

        genre_objects = [
            UserFavoriteGenre(
                user_id=new_user.user_id,
                genre=GenreEnum(genre_str)
            )
            for genre_str in favorite_genres
        ]
        db.session.add_all(genre_objects)

        access_token = create_access_token(new_user.user_id)
        refresh_token = create_refresh_token(new_user.user_id)

        return AuthTokenDto(
            access_token=access_token,
            refresh_token=refresh_token
        )


    @staticmethod
    @transactional_readonly
    def login(email: str, password:str) -> AuthTokenDto:
        user = User.query.filter_by(email=email).first()
        if not user:
            raise BusinessError(APIError.AUTH_INVALID_EMAIL)
        if not check_password_hash(user.password, password):
            raise BusinessError(APIError.AUTH_INVALID_PASSWORD)

        access_token = create_access_token(user.user_id)
        refresh_token = create_refresh_token(user.user_id)

        return AuthTokenDto(
            access_token=access_token,
            refresh_token=refresh_token
        )

    @staticmethod
    @transactional_readonly
    def get_my_info(user_id: str) -> UserBaseDataDto:
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        genre_list = [fg.genre.value for fg in user.favorite_genres.all()]

        return UserBaseDataDto(
            user_id=user.user_id,
            email=user.email,
            name=user.name,
            profile_image_id=user.profile_image_id,
            is_tutorial_done=bool(user.is_tutorial_done),
            is_verify_email_done=bool(user.is_verify_email_done),
            role=user.role,
            created_at=user.created_at,
            favorite_genres=genre_list
        )

    @staticmethod
    @transactional
    def complete_tutorial(user_id: str):
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)
        user.complete_tutorial()

    @staticmethod
    def logout(token: str):
        if not redis_client:
            return

        payload = decode_token(token)
        exp_timestamp = payload.get('exp')

        if exp_timestamp:
            current_timestamp = datetime.datetime.utcnow().timestamp()
            ttl_seconds = int(exp_timestamp - current_timestamp)

            #NOTE: 만료 시간이 남아있으면 블랙리스트에 추가
            if ttl_seconds > 0:
                if redis_client is not None:
                    redis_client.setex(
                        f"facereview:blacklist:{token}",
                        ttl_seconds,
                        "1"
                    )
                else:
                    logger.warning("Redis 사용 불가, 토큰 블랙리스트 기능 비활성화")

    @staticmethod
    @transactional_readonly
    def reissue(refresh_token: str) -> AuthTokenDto:
        payload = decode_token(refresh_token)

        if payload.get('type') != 'refresh':
            raise BusinessError(APIError.AUTH_INVALID_TOKEN)

        user_id = payload.get('sub')

        user = User.query.get(user_id)
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        new_access_token = create_access_token(user.user_id)
        new_refresh_token = create_refresh_token(user.user_id)

        return AuthTokenDto(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )

    @staticmethod
    def test_token() -> AuthTokenDto:
        new_test_token = create_test_token("7156c110-7097-4df3-8787-5d9c1eefcc9f")

        return AuthTokenDto(
            access_token=new_test_token,
            refresh_token=new_test_token
        )