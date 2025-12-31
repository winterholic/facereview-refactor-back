from flask import g
from flask_smorest import Blueprint

from app.schemas.common_schema import SuccessResponseSchema
from app.schemas.mypage import (
    UpdateProfileRequestSchema,
    VerifyEmailCodeRequestSchema, VerifyEmailCodeResponseSchema,
    VerifyCodeForPasswordResetRequestSchema, VerifyCodeForPasswordResetResponseSchema,
    ChangePasswordRequestSchema, ChangePasswordResponseSchema,
    GetRecentVideosRequestSchema, RecentVideoListResponseSchema,
    EmotionSummaryResponseSchema,
    CategoryEmotionListResponseSchema,
    GetEmotionTrendRequestSchema, EmotionTrendResponseSchema,
    HighlightResponseSchema
)
from app.services.mypage_service import MypageService
from common.decorator.auth_decorators import login_required

# TODO : 프로필 이미지 변경 추후 실제이미지로도 고려
# TODO : 탈퇴하기 추가

mypage_blueprint = Blueprint(
    'mypage',
    __name__,
    url_prefix='/api/v2/mypage',
    description='마이페이지 API'
)


@mypage_blueprint.route('/profile', methods=['PATCH'])
@login_required
@mypage_blueprint.arguments(UpdateProfileRequestSchema)
@mypage_blueprint.response(200, SuccessResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def update_profile(data):
    user_id = g.user_id
    name = data.get('name')
    profile_image_id = data.get('profile_image_id')
    favorite_genres = data.get('favorite_genres')

    MypageService.update_profile(user_id, name, profile_image_id, favorite_genres)

    return {
        "result": "success",
        'message': '유저 프로필이 수정되었습니다.'
    }


@mypage_blueprint.route('/email/verification', methods=['POST'])
@login_required
@mypage_blueprint.response(200, SuccessResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def send_verification_email():
    MypageService.send_verification_email_service(g.user_id)

    return {
        "result": "success",
        'message': '인증번호가 발송되었습니다.'
    }


@mypage_blueprint.route('/email/verify', methods=['POST'])
@login_required
@mypage_blueprint.arguments(VerifyEmailCodeRequestSchema)
@mypage_blueprint.response(200, SuccessResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def verify_email_code(data):
    MypageService.verify_email_code_service(g.user_id, data['code'])

    return {
        "result": "success",
        'message': '이메일 인증이 완료되었습니다.'
    }


@mypage_blueprint.route('/password/verification', methods=['POST'])
@login_required
@mypage_blueprint.arguments(VerifyCodeForPasswordResetRequestSchema)
@mypage_blueprint.response(200, VerifyCodeForPasswordResetResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def verify_code_for_password_reset(data):
    return MypageService.verify_code_for_password_reset(g.user_id, data['code'])


@mypage_blueprint.route('/password', methods=['PATCH'])
@login_required
@mypage_blueprint.arguments(ChangePasswordRequestSchema)
@mypage_blueprint.response(200, SuccessResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def change_password(data):
    MypageService.change_password(data['reset_token'], data['new_password'])

    return {
        "result": "success",
        'message': '비밀번호가 변경되었습니다.'
    }


@mypage_blueprint.route('/videos/recent', methods=['GET'])
@login_required
@mypage_blueprint.arguments(GetRecentVideosRequestSchema, location='query')
@mypage_blueprint.response(200, RecentVideoListResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_recent_videos(args):
    user_id = g.user_id
    emotion = args.get('emotion', 'all')
    page = args.get('page', 1)
    size = args.get('size', 10)

    return MypageService.get_recent_videos(user_id, emotion, page, size)


@mypage_blueprint.route('/emotion/summary', methods=['GET'])
@login_required
@mypage_blueprint.response(200, EmotionSummaryResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_emotion_summary():
    user_id = g.user_id

    return MypageService.get_emotion_summary(user_id)


@mypage_blueprint.route('/emotion/category', methods=['GET'])
@login_required
@mypage_blueprint.response(200, CategoryEmotionListResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_category_emotions():
    user_id = g.user_id

    return MypageService.get_category_emotions(user_id)


@mypage_blueprint.route('/emotion/trend', methods=['GET'])
@login_required
@mypage_blueprint.arguments(GetEmotionTrendRequestSchema, location='query')
@mypage_blueprint.response(200, EmotionTrendResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_emotion_trend(args):
    user_id = g.user_id
    period = args['period']

    return MypageService.get_emotion_trend(user_id, period)


@mypage_blueprint.route('/highlight', methods=['GET'])
@login_required
@mypage_blueprint.response(200, HighlightResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_highlight():
    user_id = g.user_id

    return MypageService.get_highlight(user_id)
