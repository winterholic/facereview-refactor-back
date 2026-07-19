from functools import wraps
from flask import request, g

import common.extensions as extensions
from app.models.user import User
from common.enum.error_code import APIError
from common.exception.exceptions import BusinessError
from common.utils import decode_token


def _get_bearer_token():
    parts = (request.headers.get('Authorization') or '').split()
    if len(parts) != 2 or parts[0] != 'Bearer' or not parts[1]:
        raise BusinessError(APIError.AUTH_INVALID_TOKEN)
    return parts[1]


def _authenticate_access_token():
    token = _get_bearer_token()
    redis_client = extensions.redis_client
    if redis_client and redis_client.exists(f"facereview:blacklist:{token}"):
        raise BusinessError(APIError.AUTH_INVALID_TOKEN)

    payload = decode_token(token)
    if payload.get('type') != 'access' or not payload.get('sub'):
        raise BusinessError(APIError.AUTH_INVALID_TOKEN)

    user = extensions.db.session.query(User).filter_by(
        user_id=payload['sub'],
        is_deleted=False,
    ).first()
    if not user:
        raise BusinessError(APIError.AUTH_INVALID_TOKEN)

    g.current_user = user
    return user.user_id


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.user_id = _authenticate_access_token()
        g.is_guest = False

        return f(*args, **kwargs)
    return decorated_function


def login_optional(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            g.user_id = None
            g.is_guest = True
            return f(*args, **kwargs)

        g.user_id = _authenticate_access_token()
        g.is_guest = False

        return f(*args, **kwargs)
    return decorated_function


def public_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = getattr(g, 'current_user', None)
        if not user or user.role not in ('ADMIN', 'SUPER_ADMIN'):
            raise BusinessError(APIError.USER_FORBIDDEN, "관리자 권한이 필요합니다.")
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = getattr(g, 'current_user', None)
        if not user or user.role != 'SUPER_ADMIN':
            raise BusinessError(APIError.USER_FORBIDDEN, "최고 관리자 권한이 필요합니다.")
        return f(*args, **kwargs)
    return decorated_function
