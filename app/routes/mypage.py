from datetime import datetime
from flask import g, request, make_response
from flask_smorest import Blueprint

from app.schemas.common_schema import SuccessResponseSchema
from app.schemas.mypage import (
    UpdateProfileRequestSchema,
    VerifyEmailCodeRequestSchema, VerifyEmailCodeResponseSchema,
    VerifyCodeForPasswordResetRequestSchema, VerifyCodeForPasswordResetResponseSchema,
    ChangePasswordRequestSchema, ChangePasswordResponseSchema,
    GetRecentVideosRequestSchema, RecentVideoListResponseSchema,
    EmotionSummaryResponseSchema,
    HighlightResponseSchema,
    GetEmotionCalendarRequestSchema, EmotionCalendarResponseSchema,
    GetMomentsRequestSchema, MomentListResponseSchema,
    EmotionDnaResponseSchema,
)
from app.services.mypage_service import MypageService
from common.decorator.auth_decorators import login_required


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
    MypageService.update_profile(
        g.user_id,
        data.get('name'),
        data.get('profile_image_id'),
        data.get('favorite_genres'),
    )
    return {"result": "success", 'message': '유저 프로필이 수정되었습니다.'}


@mypage_blueprint.route('/email/verification', methods=['POST'])
@login_required
@mypage_blueprint.response(200, SuccessResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def send_verification_email():
    MypageService.send_verification_email_service(g.user_id)
    return {"result": "success", 'message': '인증번호가 발송되었습니다.'}


@mypage_blueprint.route('/email/verify', methods=['POST'])
@login_required
@mypage_blueprint.arguments(VerifyEmailCodeRequestSchema)
@mypage_blueprint.response(200, SuccessResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def verify_email_code(data):
    MypageService.verify_email_code_service(g.user_id, data['code'])
    return {"result": "success", 'message': '이메일 인증이 완료되었습니다.'}


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
    return {"result": "success", 'message': '비밀번호가 변경되었습니다.'}


# ==================== 1.1 최근 시청 ====================

@mypage_blueprint.route('/videos/recent', methods=['GET'])
@login_required
@mypage_blueprint.arguments(GetRecentVideosRequestSchema, location='query')
@mypage_blueprint.response(200, RecentVideoListResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_recent_videos(args):
    return MypageService.get_recent_videos(
        g.user_id,
        args.get('emotion', 'all'),
        args.get('page', 1),
        args.get('size', 10),
    )


# ==================== 1.2 감정 요약 ====================

@mypage_blueprint.route('/emotion/summary', methods=['GET'])
@login_required
@mypage_blueprint.response(200, EmotionSummaryResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_emotion_summary():
    return MypageService.get_emotion_summary(g.user_id)


# ==================== 1.3 하이라이트 ====================

@mypage_blueprint.route('/highlight', methods=['GET'])
@login_required
@mypage_blueprint.response(200, HighlightResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_highlight():
    return MypageService.get_highlight(g.user_id)


# ==================== 2.1 감정 캘린더 ====================

@mypage_blueprint.route('/emotion/calendar', methods=['GET'])
@login_required
@mypage_blueprint.arguments(GetEmotionCalendarRequestSchema, location='query')
@mypage_blueprint.response(200, EmotionCalendarResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_emotion_calendar(args):
    year = args.get('year') or datetime.utcnow().year
    month = args.get('month')
    return MypageService.get_emotion_calendar(g.user_id, year, month)


# ==================== 2.2 베스트 모먼트 ====================

@mypage_blueprint.route('/moments', methods=['GET'])
@login_required
@mypage_blueprint.arguments(GetMomentsRequestSchema, location='query')
@mypage_blueprint.response(200, MomentListResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_moments(args):
    return MypageService.get_moments(
        g.user_id,
        args.get('emotion', 'all'),
        args.get('page', 1),
        args.get('size', 10),
    )


# ==================== 2.3 감정 DNA ====================

@mypage_blueprint.route('/emotion-dna', methods=['GET'])
@login_required
@mypage_blueprint.response(200, EmotionDnaResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def get_emotion_dna():
    return MypageService.get_emotion_dna(g.user_id)


# ==================== 회원 탈퇴 ====================

@mypage_blueprint.route('/withdraw', methods=['DELETE'])
@login_required
@mypage_blueprint.response(200, SuccessResponseSchema)
@mypage_blueprint.doc(security=[{"BearerAuth": []}])
def withdraw_user():
    refresh_token = request.cookies.get('refresh_token')
    MypageService.withdraw_user(g.user_id, refresh_token)

    response = make_response({
        "result": "success",
        "message": "회원 탈퇴가 완료되었습니다."
    })
    response.delete_cookie('refresh_token')
    return response
