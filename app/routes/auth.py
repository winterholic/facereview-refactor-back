from flask import request, g, make_response
from flask_smorest import Blueprint

from app.schemas.auth import (
    UserResponseSchema, LoginRequestSchema, SignupRequestSchema,
    EmailCheckRequestSchema, EmailCheckResponseSchema,
    TestTokenResponseSchema, AccessTokenResponseSchema
)
from app.schemas.common_schema import SuccessResponseSchema
from app.services.auth_service import AuthService
from common.decorator.auth_decorators import login_required, public_route

REFRESH_TOKEN_COOKIE_NAME = 'refresh_token'
REFRESH_TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7일

auth_blueprint = Blueprint(
    'auth',
    __name__,
    url_prefix='/api/v2/auth',
    description='인증 관련 API'
)


@auth_blueprint.route('/check-email', methods=['POST'])
@public_route
@auth_blueprint.arguments(EmailCheckRequestSchema)
@auth_blueprint.response(200, EmailCheckResponseSchema)
def check_duplicate_email(data):
    is_dup = AuthService.check_duplicate_email(data['email'])

    if is_dup:
        message_text = "이미 가입된 이메일입니다."
    else:
        message_text = "사용 가능한 이메일입니다."

    return {
        "is_duplicate": is_dup,
        "message": message_text
    }


@auth_blueprint.route('/signup', methods=['POST'])
@public_route
@auth_blueprint.arguments(SignupRequestSchema)
@auth_blueprint.response(201, AccessTokenResponseSchema)
def signup(data):
    tokens = AuthService.signup(data['email'], data['password'], data['name'], data['favorite_genres'])

    response = make_response({'access_token': tokens.access_token}, 201)
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        tokens.refresh_token,
        max_age=REFRESH_TOKEN_MAX_AGE,
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    return response


@auth_blueprint.route('/login', methods=['POST'])
@public_route
@auth_blueprint.arguments(LoginRequestSchema)
@auth_blueprint.response(200, AccessTokenResponseSchema)
def login(data):
    tokens = AuthService.login(data['email'], data['password'])

    response = make_response({'access_token': tokens.access_token})
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        tokens.refresh_token,
        max_age=REFRESH_TOKEN_MAX_AGE,
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    return response


@auth_blueprint.route('/me', methods=['GET'])
@login_required
@auth_blueprint.response(200, UserResponseSchema)
@auth_blueprint.doc(security=[{"BearerAuth": []}])
def get_my_info():
    return AuthService.get_my_info(g.user_id)


@auth_blueprint.route('/tutorial', methods=['PATCH'])
@login_required
@auth_blueprint.response(200, SuccessResponseSchema)
@auth_blueprint.doc(security=[{"BearerAuth": []}])
def complete_tutorial():
    AuthService.complete_tutorial(g.user_id)
    return {
        "result": "success",
        "message": "튜토리얼이 완료되었습니다."
    }


@auth_blueprint.route('/logout', methods=['POST'])
@login_required
@auth_blueprint.response(200, SuccessResponseSchema)
@auth_blueprint.doc(security=[{"BearerAuth": []}])
def logout():
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if refresh_token:
        AuthService.logout(refresh_token)

    response = make_response({
        "result": "success",
        "message": "로그아웃되었습니다."
    })
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME)
    return response


@auth_blueprint.route('/reissue', methods=['POST'])
@public_route
@auth_blueprint.response(200, AccessTokenResponseSchema)
def reissue_token():
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        from common.enum.error_code import APIError
        from common.exception.exceptions import BusinessError
        raise BusinessError(APIError.AUTH_INVALID_TOKEN)

    tokens = AuthService.reissue(refresh_token)

    response = make_response({'access_token': tokens.access_token})
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        tokens.refresh_token,
        max_age=REFRESH_TOKEN_MAX_AGE,
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    return response


@auth_blueprint.route('/test-token', methods=['POST'])
@public_route
@auth_blueprint.response(200, TestTokenResponseSchema)
def test_token():
    return AuthService.test_token()