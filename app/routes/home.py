from flask import g
from flask_smorest import Blueprint

from app.schemas.common_schema import SuccessResponseSchema
from common.decorator.auth_decorators import login_required, login_optional, public_route
from app.schemas.home import (
    VideoResponseSchema,
    EmotionVideoQuerySchema,
    CategoryGroupedResponseSchema,
    VideoRecommendRequestSchema,
    AllVideoResponseSchema,
    SearchVideoResponseSchema,
    SearchVideoRequestSchema,
    BookmarkToggleRequestSchema,
    BookmarkToggleResponseSchema
)
from app.services.home_service import HomeService

home_blueprint = Blueprint(
    'home',
    __name__,
    url_prefix='/api/v2/home',
    description='홈 화면 및 영상 추천 API'
)

#TODO: 논리삭제된 데이터 삭제처리 스케줄러 추가
#TODO: 스케줄러 test용 api 추가

@home_blueprint.route('/search', methods=['GET'])
@public_route
@home_blueprint.arguments(SearchVideoRequestSchema, location='query')
@home_blueprint.response(200, SearchVideoResponseSchema)
@home_blueprint.doc(summary="영상 검색")
def get_search_videos(query_args):
    page = query_args['page']
    size = query_args['size']
    keyword_type = query_args['keyword_type']
    keyword = query_args['keyword']
    emotions = query_args.get('emotions', [])

    return HomeService.get_search_videos(page, size, keyword_type, keyword, emotions)

@home_blueprint.route('/personalized', methods=['GET'])
@login_required
@home_blueprint.response(200, VideoResponseSchema(many=True))
@home_blueprint.doc(summary="감정 기반 개인화 추천 영상 목록", security=[{"BearerAuth": []}])
def get_personalized_videos():
    user_id = g.user_id
    result_dtos = HomeService.get_personalized_videos(user_id, limit=20)

    return result_dtos


@home_blueprint.route('/category', methods=['GET'])
@public_route
@home_blueprint.response(200, CategoryGroupedResponseSchema(many=True))
@home_blueprint.doc(summary="카테고리별 감정 대표 영상 목록")
def get_videos_by_category_emotions():
    result_dto = HomeService.get_videos_by_category_emotions()

    return result_dto.video_data


@home_blueprint.route('/video/all', methods=['GET'])
@public_route
@home_blueprint.arguments(EmotionVideoQuerySchema, location='query')
@home_blueprint.response(200, AllVideoResponseSchema)
@home_blueprint.doc(summary="전체 영상 목록 조회 (감정 필터 가능)")
def get_all_videos(query_args):
    page = query_args['page']
    size = query_args['size']
    emotion = query_args['emotion']

    return HomeService.get_all_videos(page, size, emotion)


@home_blueprint.route('/bookmark', methods=['POST'])
@login_required
@home_blueprint.arguments(BookmarkToggleRequestSchema)
@home_blueprint.response(200, BookmarkToggleResponseSchema)
@home_blueprint.doc(summary="북마크 추가/해제 토글", security=[{"BearerAuth": []}])
def toggle_bookmark(data):
    return HomeService.toggle_bookmark(g.user_id, data['video_id'])


@home_blueprint.route('/bookmark', methods=['GET'])
@login_required
@home_blueprint.arguments(EmotionVideoQuerySchema, location='query')
@home_blueprint.response(200, AllVideoResponseSchema)
@home_blueprint.doc(summary="북마크한 영상 목록 조회", security=[{"BearerAuth": []}])
def get_bookmark_videos(query_args):
    page = query_args['page']
    size = query_args['size']
    emotion = query_args['emotion']

    return HomeService.get_bookmark_videos(g.user_id, page, size, emotion)


@home_blueprint.route('/video/recommend', methods=['POST'])
@login_required
@home_blueprint.arguments(VideoRecommendRequestSchema)
@home_blueprint.response(200, SuccessResponseSchema)
@home_blueprint.doc(summary="영상 등록 추천 요청", security=[{"BearerAuth": []}])
def create_user_video_recommend(data):
    user_id = g.user_id
    youtube_url_list = data['youtube_url_list']

    HomeService.create_user_video_recommend(user_id, youtube_url_list)

    return {
        "result": "success",
        'message': '영상 추천 요청이 등록되었습니다.'
    }