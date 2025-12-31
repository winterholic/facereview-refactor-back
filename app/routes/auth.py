from flask import request, jsonify, g
from flask_smorest import Blueprint, abort

from app.schemas.auth import UserResponseSchema, LoginResponseSchema, LoginRequestSchema, SignupRequestSchema, \
    EmailCheckRequestSchema, CheckResponseSchema, EmailCheckResponseSchema, ReissueRequestSchema, LogoutRequestSchema
from app.schemas.common_schema import SuccessResponseSchema
from app.services.auth_service import AuthService
from common.decorator.auth_decorators import login_required, public_route

#TODO: tz timestamp 자료형 찾아보고 확인해보기

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
@auth_blueprint.response(201, LoginResponseSchema)
def signup(data):
    return AuthService.signup(data['email'], data['password'], data['name'], data['favorite_genres'])


@auth_blueprint.route('/login', methods=['POST'])
@public_route
@auth_blueprint.arguments(LoginRequestSchema)
@auth_blueprint.response(200, LoginResponseSchema)
def login(data):
    return AuthService.login(data['email'], data['password'])


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
@auth_blueprint.arguments(LogoutRequestSchema)
@auth_blueprint.response(200, SuccessResponseSchema)
@auth_blueprint.doc(security=[{"BearerAuth": []}])
def logout(data):
    AuthService.logout(data['token'])

    return {
        "result": "success",
        "message": "로그아웃되었습니다."
    }


@auth_blueprint.route('/reissue', methods=['POST'])
@public_route
@auth_blueprint.arguments(ReissueRequestSchema)
@auth_blueprint.response(200, LoginResponseSchema)
def reissue_token(data):
    return AuthService.reissue(data['refresh_token'])


@auth_blueprint.route('/test-token', methods=['POST'])
@public_route
@auth_blueprint.response(200, LoginResponseSchema)
def reissue_token():
    return AuthService.test_token()