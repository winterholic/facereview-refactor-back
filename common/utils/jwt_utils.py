import jwt
import datetime
from flask import current_app
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError

from common.exception.exceptions import BusinessError
from common.enum.error_code import APIError

def get_jwt_config():
    try:
        secret_key = current_app.config.get('JWT_SECRET_KEY')
        algorithm = current_app.config.get('JWT_ALGORITHM', 'HS256')

        if not secret_key:
            raise BusinessError(APIError.INTERNAL_SERVER_ERROR, "JWT KEY가 설정되지 않았습니다.")

        return secret_key, algorithm
    except RuntimeError:
        raise BusinessError(APIError.INTERNAL_SERVER_ERROR, "Application Context Error")

def encode_token(user_id, expires_delta, token_type):
    secret_key, algorithm = get_jwt_config()

    current_time = datetime.datetime.utcnow()

    payload = {
        "sub": user_id,                  # Subject (유저 ID)
        "iat": current_time,             # Issued At (발급 시간)
        "exp": current_time + expires_delta, # Expiration (만료 시간)
        "type": token_type               # 커스텀: 토큰 타입 (access/refresh)
    }

    encoded_token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return encoded_token

def decode_token(encoded_token):
    secret_key, algorithm = get_jwt_config()

    try:
        payload = jwt.decode(encoded_token, secret_key, algorithms=[algorithm])
        return payload

    except ExpiredSignatureError:
        raise BusinessError(APIError.AUTH_TOKEN_EXPIRED)

    except (DecodeError, InvalidTokenError):
        raise BusinessError(APIError.AUTH_INVALID_TOKEN)

    except Exception as e:
        raise BusinessError(APIError.AUTH_INVALID_TOKEN)

def create_access_token(user_id):
    expires = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', datetime.timedelta(hours=1))
    return encode_token(user_id, expires, 'access')

def create_refresh_token(user_id):
    expires = current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', datetime.timedelta(days=30))
    return encode_token(user_id, expires, 'refresh')

def create_test_token(user_id):
    expires = datetime.timedelta(hours=168)
    return encode_token(user_id, expires, 'access')