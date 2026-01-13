from functools import wraps
from flask import request, jsonify, g

from common.enum.error_code import APIError
from common.exception.exceptions import BusinessError
from common.utils import decode_token
from common.extensions import redis_client

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith("Bearer "):
            raise BusinessError(APIError.AUTH_INVALID_TOKEN)

        token = auth_header.split(" ")[1]

        if redis_client and redis_client.exists(f"facereview:blacklist:{token}"):
            raise BusinessError(APIError.AUTH_INVALID_TOKEN)

        payload = decode_token(token)

        if payload.get('type') != 'access':
            raise BusinessError(APIError.AUTH_INVALID_TOKEN)

        g.user_id = payload['sub']
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

        if not auth_header.startswith("Bearer "):
            raise BusinessError(APIError.AUTH_INVALID_TOKEN)

        token = auth_header.split(" ")[1]

        if redis_client and redis_client.exists(f"facereview:blacklist:{token}"):
            raise BusinessError(APIError.AUTH_INVALID_TOKEN)

        payload = decode_token(token)

        if payload.get('type') != 'access':
            raise BusinessError(APIError.AUTH_INVALID_TOKEN)

        g.user_id = payload['sub']
        g.is_guest = False

        return f(*args, **kwargs)
    return decorated_function

def public_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function