from flask import g
from flask_smorest import Blueprint

from app.schemas.admin import (
    GetUsersRequestSchema, GetUsersResponseSchema,
    GetUserDetailResponseSchema,
    DeactivateUserResponseSchema,
    ChangeUserRoleRequestSchema, ChangeUserRoleResponseSchema,
    GetVideoRequestsRequestSchema, GetVideoRequestsResponseSchema,
    GetVideoRequestDetailResponseSchema,
    ApproveVideoRequestRequestSchema, ApproveVideoRequestResponseSchema,
    RejectVideoRequestRequestSchema, RejectVideoRequestResponseSchema,
    GetVideosRequestSchema, GetVideosResponseSchema,
    GetVideoStatisticsResponseSchema,
    DeleteVideoResponseSchema,
    GetCommentsRequestSchema, GetCommentsResponseSchema,
    DeleteCommentResponseSchema,
    DashboardOverviewResponseSchema,
    PopularVideosResponseSchema,
    RecentActivitiesResponseSchema
)
from app.services.admin_service import AdminService
from common.decorator.auth_decorators import login_required
from common.exception.exceptions import BusinessError
from common.enum.error_code import APIError

admin_blueprint = Blueprint(
    'admin',
    __name__,
    url_prefix='/api/v2/admin',
    description='관리자 페이지 API'
)


def admin_required(func):
    def wrapper(*args, **kwargs):
        from app.models.user import User
        from common.extensions import db

        user = db.session.query(User).filter_by(user_id=g.user_id).first()
        if not user or user.role != 'ADMIN':
            raise BusinessError(APIError.USER_NOT_FOUND, "관리자 권한이 필요합니다.")

        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


@admin_blueprint.route('/users', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.arguments(GetUsersRequestSchema, location='query')
@admin_blueprint.response(200, GetUsersResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_users(args):
    search = args.get('search')
    page = args.get('page', 1)
    size = args.get('size', 20)
    return AdminService.get_users(search, page, size)


@admin_blueprint.route('/users/<user_id>', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.response(200, GetUserDetailResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_user_detail(user_id):
    return AdminService.get_user_detail(user_id)


@admin_blueprint.route('/users/<user_id>/deactivate', methods=['PATCH'])
@login_required
@admin_required
@admin_blueprint.response(200, DeactivateUserResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def deactivate_user(user_id):
    return AdminService.deactivate_user(user_id)


@admin_blueprint.route('/users/<user_id>/role', methods=['PATCH'])
@login_required
@admin_required
@admin_blueprint.arguments(ChangeUserRoleRequestSchema)
@admin_blueprint.response(200, ChangeUserRoleResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def change_user_role(data, user_id):
    role = data['role']
    return AdminService.change_user_role(user_id, role)


@admin_blueprint.route('/video-requests', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.arguments(GetVideoRequestsRequestSchema, location='query')
@admin_blueprint.response(200, GetVideoRequestsResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_video_requests(args):
    status = args.get('status')
    page = args.get('page', 1)
    size = args.get('size', 20)
    return AdminService.get_video_requests(status, page, size)


@admin_blueprint.route('/video-requests/<request_id>', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.response(200, GetVideoRequestDetailResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_video_request_detail(request_id):
    return AdminService.get_video_request_detail(request_id)


@admin_blueprint.route('/video-requests/<request_id>/approve', methods=['POST'])
@login_required
@admin_required
@admin_blueprint.arguments(ApproveVideoRequestRequestSchema)
@admin_blueprint.response(200, ApproveVideoRequestResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def approve_video_request(data, request_id):
    youtube_title = data['youtube_title']
    channel_name = data['channel_name']
    duration = data['duration']
    return AdminService.approve_video_request(request_id, youtube_title, channel_name, duration)


@admin_blueprint.route('/video-requests/<request_id>/reject', methods=['POST'])
@login_required
@admin_required
@admin_blueprint.arguments(RejectVideoRequestRequestSchema)
@admin_blueprint.response(200, RejectVideoRequestResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def reject_video_request(data, request_id):
    admin_comment = data['admin_comment']
    return AdminService.reject_video_request(request_id, admin_comment)


@admin_blueprint.route('/videos', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.arguments(GetVideosRequestSchema, location='query')
@admin_blueprint.response(200, GetVideosResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_videos(args):
    search = args.get('search')
    category = args.get('category')
    page = args.get('page', 1)
    size = args.get('size', 20)
    return AdminService.get_videos(search, category, page, size)


@admin_blueprint.route('/videos/<video_id>/statistics', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.response(200, GetVideoStatisticsResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_video_statistics(video_id):
    return AdminService.get_video_statistics(video_id)


@admin_blueprint.route('/videos/<video_id>', methods=['DELETE'])
@login_required
@admin_required
@admin_blueprint.response(200, DeleteVideoResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def delete_video(video_id):
    return AdminService.delete_video(video_id)


@admin_blueprint.route('/comments', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.arguments(GetCommentsRequestSchema, location='query')
@admin_blueprint.response(200, GetCommentsResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_comments(args):
    video_id = args.get('video_id')
    user_id = args.get('user_id')
    page = args.get('page', 1)
    size = args.get('size', 20)
    return AdminService.get_comments(video_id, user_id, page, size)


@admin_blueprint.route('/comments/<comment_id>', methods=['DELETE'])
@login_required
@admin_required
@admin_blueprint.response(200, DeleteCommentResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def delete_comment(comment_id):
    return AdminService.delete_comment(comment_id)


@admin_blueprint.route('/dashboard/overview', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.response(200, DashboardOverviewResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_dashboard_overview():
    return AdminService.get_dashboard_overview()


@admin_blueprint.route('/dashboard/popular-videos', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.response(200, PopularVideosResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_popular_videos():
    return AdminService.get_popular_videos()


@admin_blueprint.route('/dashboard/recent-activities', methods=['GET'])
@login_required
@admin_required
@admin_blueprint.response(200, RecentActivitiesResponseSchema)
@admin_blueprint.doc(security=[{"BearerAuth": []}])
def get_recent_activities():
    return AdminService.get_recent_activities()
