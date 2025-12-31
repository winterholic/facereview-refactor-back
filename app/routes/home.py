from flask import g
from flask_smorest import Blueprint

from app.schemas.common_schema import SuccessResponseSchema
from common.decorator.auth_decorators import login_required, login_optional, public_route
from app.schemas.home import (
    VideoResponseSchema,
    EmotionVideoQuerySchema,
    CategoryGroupedResponseSchema,
    VideoRecommendRequestSchema,
    AllVideoResponseSchema
)
from app.services.home_service import HomeService

home_blueprint = Blueprint(
    'home',
    __name__,
    url_prefix='/api/v2/home',
    description='홈 화면 및 영상 추천 API'
)

#TODO: 검색 API 추가 전체, 제목, 채널명

@home_blueprint.route('/personalized', methods=['GET'])
@login_required
@home_blueprint.response(200, VideoResponseSchema(many=True))
@home_blueprint.doc(security=[{"BearerAuth": []}])
def get_personalized_videos():
    user_id = g.user_id
    result_dtos = HomeService.get_personalized_videos(user_id, limit=20)

    return result_dtos


@home_blueprint.route('/category', methods=['GET'])
@public_route
@home_blueprint.response(200, CategoryGroupedResponseSchema(many=True))
def get_videos_by_category_emotions():
    result_dto = HomeService.get_videos_by_category_emotions()

    return result_dto.video_data


@home_blueprint.route('/video/all', methods=['GET'])
@public_route
@home_blueprint.arguments(EmotionVideoQuerySchema, location='query')
@home_blueprint.response(200, AllVideoResponseSchema)
def get_all_videos(query_args):
    page = query_args['page']
    size = query_args['size']
    emotion = query_args['emotion']

    return HomeService.get_all_videos(page, size, emotion)


@home_blueprint.route('/video/recommend', methods=['POST'])
@login_required
@home_blueprint.arguments(VideoRecommendRequestSchema)
@home_blueprint.response(200, SuccessResponseSchema)
@home_blueprint.doc(security=[{"BearerAuth": []}])
def create_user_video_recommend(data):
    user_id = g.user_id
    youtube_url = data['youtube_url']

    HomeService.create_user_video_recommend(user_id, youtube_url)

    #TODO: list화

    return {
        "result": "success",
        'message': '영상 추천 요청이 등록되었습니다.'
    }