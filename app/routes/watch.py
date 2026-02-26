from flask import g
from flask_smorest import Blueprint

from app.schemas.common_schema import SuccessResponseSchema
from app.schemas.watch import (
    GetVideoDetailRequestSchema, VideoDetailResponseSchema,
    GetRecommendedVideosRequestSchema, RecommendedVideoListResponseSchema,
    GetCommentListRequestSchema, CommentListResponseSchema,
    AddCommentRequestSchema, AddCommentResponseSchema,
    UpdateCommentRequestSchema,
    DeleteCommentRequestSchema,
    ToggleLikeRequestSchema, ToggleLikeResponseSchema
)
from app.services.watch_service import WatchService
from common.decorator.auth_decorators import login_required, login_optional

watch_blueprint = Blueprint(
    'watch',
    __name__,
    url_prefix='/api/v2/watch',
    description='영상 시청 및 감정 분석 API'
)


@watch_blueprint.route('/video', methods=['GET'])
@login_optional
@watch_blueprint.arguments(GetVideoDetailRequestSchema, location='query')
@watch_blueprint.response(200, VideoDetailResponseSchema)
@watch_blueprint.doc(summary="영상 상세 조회 (타임라인 감정 그래프 포함)", security=[{"BearerAuth": []}])
def get_video_detail(data):
    return WatchService.get_video_detail(data['video_id'], g.user_id)


@watch_blueprint.route('/recommended', methods=['GET'])
@login_optional
@watch_blueprint.arguments(GetRecommendedVideosRequestSchema, location='query')
@watch_blueprint.response(200, RecommendedVideoListResponseSchema)
@watch_blueprint.doc(summary="현재 영상 기반 연관 추천 영상 목록", security=[{"BearerAuth": []}])
def get_recommended_videos(data):
    video_id = data['video_id']
    page = data.get('page', 1)
    size = data.get('size', 10)

    return WatchService.get_recommended_videos(video_id, page, size)


@watch_blueprint.route('/comments', methods=['GET'])
@login_optional
@watch_blueprint.arguments(GetCommentListRequestSchema, location='query')
@watch_blueprint.response(200, CommentListResponseSchema)
@watch_blueprint.doc(summary="영상 댓글 목록 조회", security=[{"BearerAuth": []}])
def get_comment_list(data):
    return WatchService.get_comment_list(data['video_id'], g.user_id)


@watch_blueprint.route('/comments', methods=['POST'])
@login_required
@watch_blueprint.arguments(AddCommentRequestSchema)
@watch_blueprint.response(200, AddCommentResponseSchema)
@watch_blueprint.doc(summary="댓글 작성", security=[{"BearerAuth": []}])
def add_comment(data):
    video_id = data['video_id']
    content = data['content']
    user_id = g.user_id

    return WatchService.add_comment(video_id, user_id, content)


@watch_blueprint.route('/comments', methods=['PATCH'])
@login_required
@watch_blueprint.arguments(UpdateCommentRequestSchema)
@watch_blueprint.response(200, SuccessResponseSchema)
@watch_blueprint.doc(summary="댓글 수정", security=[{"BearerAuth": []}])
def update_comment(data):
    comment_id = data['comment_id']
    content = data['content']
    user_id = g.user_id

    WatchService.update_comment(comment_id, user_id, content)
    return {
        "result": "success",
        'message': '댓글이 수정되었습니다.'
    }


@watch_blueprint.route('/comments', methods=['DELETE'])
@login_required
@watch_blueprint.arguments(DeleteCommentRequestSchema, location='query')
@watch_blueprint.response(200, SuccessResponseSchema)
@watch_blueprint.doc(summary="댓글 삭제", security=[{"BearerAuth": []}])
def delete_comment(data):
    WatchService.delete_comment(data['comment_id'], g.user_id)

    return {
        "result": "success",
        'message': '댓글이 삭제되었습니다.'
    }


@watch_blueprint.route('/like', methods=['POST'])
@login_required
@watch_blueprint.arguments(ToggleLikeRequestSchema)
@watch_blueprint.response(200, ToggleLikeResponseSchema)
@watch_blueprint.doc(summary="좋아요 추가/취소 토글", security=[{"BearerAuth": []}])
def toggle_like(data):
    return WatchService.toggle_like(data['video_id'], g.user_id)
