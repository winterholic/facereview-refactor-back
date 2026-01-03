from flask import current_app
from common.decorator.db_decorators import transactional_readonly, transactional
from app.models.user import User
from app.models.video import Video
from app.models import UserFavoriteGenre, VideoViewLog, VideoRequest
from app.models.mongodb.youtube_watching_data import YoutubeWatchingData, YoutubeWatchingDataRepository
from app.models.mongodb.video_distribution import VideoDistribution, VideoDistributionRepository
from common.enum.error_code import APIError
from common.enum.youtube_genre import GenreEnum
from common.exception.exceptions import BusinessError
from common.extensions import db, mongo_client, mongo_db
from common.utils.main_rec_alg import get_personalized_recommendations
from common.utils.category_rec_alg import get_top_videos_by_category_emotion
from app.dto.home import BaseVideoDataDto, CategoryVideoDataDto, CategoryVideoDataListDto, AllVideoDataDto
from bson.codec_options import CodecOptions
from bson.binary import UuidRepresentation


class HomeService:

    @staticmethod
    @transactional_readonly
    def get_search_videos(page: int, size: int, emotion: str, keyword_type: str, keyword: str):
        
        return


    @staticmethod
    @transactional_readonly
    def get_personalized_videos(user_id: str, limit: int = 20):
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        favorite_genres = [fg.genre.value for fg in user.favorite_genres.all()]

        all_videos = Video.query.filter_by(is_deleted=0).all()

        user_view_logs = VideoViewLog.query.filter_by(user_id=user_id).all()

        viewed_video_ids = {log.video_id for log in user_view_logs}

        recent_watching_data_objs = []
        video_stats_dict = {}
        watching_data_repo = YoutubeWatchingDataRepository(mongo_db)
        video_dist_repo = VideoDistributionRepository(mongo_db)

        recent_watching_data_objs = watching_data_repo.find_by_user_id(user_id, limit=20)

        video_ids = [video.video_id for video in all_videos]

        video_stats_dict = video_dist_repo.find_by_video_ids(video_ids)

        all_videos_dict = []
        for video in all_videos:
            video_distribution_document = video_stats_dict.get(video.video_id)

            emotion_dist = {}
            if video_distribution_document:
                emotion_dist = {
                    'neutral': video_distribution_document.emotion_averages.neutral,
                    'happy': video_distribution_document.emotion_averages.happy,
                    'surprise': video_distribution_document.emotion_averages.surprise,
                    'sad': video_distribution_document.emotion_averages.sad,
                    'angry': video_distribution_document.emotion_averages.angry
                }

            if ((video_distribution_document.dominant_emotion is None)
                    or (not emotion_dist)
                    or (sum(emotion_dist.values()) == 0)):
                continue

            video_dict = {
                'video_id': video.video_id,
                'youtube_url': video.youtube_url,
                'title': video.title,
                'channel_name': video.channel_name,
                'category': video.category.value if hasattr(video.category, 'value') else video.category,
                'duration': video.duration,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'created_at': video.created_at,
                'is_deleted': video.is_deleted,
                'emotion_distribution': emotion_dist,
                'dominant_emotion': video_distribution_document.dominant_emotion,
                'average_completion_rate': video_distribution_document.average_completion_rate,
                'watching_data_count': 0
            }
            all_videos_dict.append(video_dict)

        user_logs_dict = [
            {
                'video_id': log.video_id,
                'created_at': log.created_at
            }
            for log in user_view_logs
        ]

        recent_watching_data = []
        for wd in recent_watching_data_objs:
            if wd.dominant_emotion is None:
                continue

            emotion_pct = wd.emotion_percentages.to_dict()

            recent_watching_data.append({
                'video_id': wd.video_id,
                'completion_rate': wd.completion_rate,
                'dominant_emotion': wd.dominant_emotion,
                'emotion_percentages': emotion_pct,
                'created_at': wd.created_at
            })

        user_data_dict = {
            'user_id': user_id,
            'favorite_genres': favorite_genres
        }

        recommended_videos = get_personalized_recommendations(
            all_videos=all_videos_dict,
            user_data=user_data_dict,
            recent_watching=recent_watching_data,
            user_logs=user_logs_dict,
            viewed_ids=viewed_video_ids,
            limit=limit
        )

        result_dtos = []
        for video in recommended_videos:
            emotion_dist = video.get('emotion_distribution', {})
            dominant_emotion = video.get('dominant_emotion', 'none')

            if emotion_dist and dominant_emotion in emotion_dist:
                dominant_emotion_per = round(emotion_dist[dominant_emotion] * 100.0, 2)
            else:
                dominant_emotion_per = 0.0

            video_dto = BaseVideoDataDto(
                video_id=video['video_id'],
                youtube_url=video['youtube_url'],
                title=video['title'],
                dominant_emotion=dominant_emotion,
                dominant_emotion_per=dominant_emotion_per
            )
            result_dtos.append(video_dto)

        return result_dtos

    @staticmethod
    @transactional_readonly
    def get_videos_by_category_emotions():
        all_videos = Video.query.filter_by(is_deleted=0).all()

        video_dist_repo = VideoDistributionRepository(mongo_db)
        video_ids = [video.video_id for video in all_videos]

        video_stats_dict = {}
        video_stats_dict = video_dist_repo.find_by_video_ids(video_ids)

        videos_by_category = {}
        for genre in GenreEnum:
            videos_by_category[genre.value] = []

        for video in all_videos:
            video_distribution_document = video_stats_dict.get(video.video_id)

            emotion_dist = {}
            if video_distribution_document:
                emotion_dist = {
                    'neutral': video_distribution_document.emotion_averages.neutral,
                    'happy': video_distribution_document.emotion_averages.happy,
                    'surprise': video_distribution_document.emotion_averages.surprise,
                    'sad': video_distribution_document.emotion_averages.sad,
                    'angry': video_distribution_document.emotion_averages.angry
                }

            if ((video_distribution_document.dominant_emotion is None)
                    or (not emotion_dist)
                    or (sum(emotion_dist.values()) == 0)):
                continue

            video_dict = {
                'video_id': video.video_id,
                'youtube_url': video.youtube_url,
                'title': video.title,
                'channel_name': video.channel_name,
                'category': video.category,
                'duration': video.duration,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'created_at': video.created_at,
                'emotion_distribution': emotion_dist,
                'dominant_emotion': video_distribution_document.dominant_emotion,
                'average_completion_rate': video_distribution_document.average_completion_rate
            }

            category_value = video.category.value if hasattr(video.category, 'value') else video.category
            if category_value in videos_by_category:
                videos_by_category[category_value].append(video_dict)

        top_videos_by_category = get_top_videos_by_category_emotion(
            videos_by_category=videos_by_category,
            limit=20
        )

        category_dtos = []
        for category_name, videos in top_videos_by_category.items():
            video_dtos = []
            for video in videos:
                emotion_dist = video.get('emotion_distribution', {})
                dominant_emotion = video.get('dominant_emotion', 'none')

                if emotion_dist and dominant_emotion in emotion_dist:
                    dominant_emotion_per = round(emotion_dist[dominant_emotion] * 100.0, 2)
                else:
                    dominant_emotion_per = 0.0

                video_dto = BaseVideoDataDto(
                    video_id=video['video_id'],
                    youtube_url=video['youtube_url'],
                    title=video['title'],
                    dominant_emotion=dominant_emotion,
                    dominant_emotion_per=dominant_emotion_per
                )
                video_dtos.append(video_dto)

            category_dto = CategoryVideoDataDto(
                    category_name=category_name,
                    videos=video_dtos
                )
            category_dtos.append(category_dto)

        result = CategoryVideoDataListDto(video_data=category_dtos)
        return result



    @staticmethod
    @transactional_readonly
    def get_all_videos(page: int, size: int, emotion: str) -> AllVideoDataDto:
        video_dist_repo = VideoDistributionRepository(mongo_db)

        query = {}
        if emotion != 'all':
            query['dominant_emotion'] = emotion

        total = video_dist_repo.collection.count_documents(query)

        video_distributions = list(
            video_dist_repo.collection.find(query)
            .sort([
                ('created_at', -1),
                ('_id', -1)
            ])
            .skip((page - 1) * size)
            .limit(size)
        )

        video_distributions_dict = {}
        for vd in video_distributions:
            video_distributions_dict[vd['video_id']] = vd

        video_ids = [vd['video_id'] for vd in video_distributions]

        if not video_ids:
            return AllVideoDataDto(
                videos=[],
                total=total,
                page=page,
                size=size,
                has_next=False
            )

        videos = Video.query.filter(Video.video_id.in_(video_ids)).all()

        video_dto_list = []
        for vd in videos:
            vd_dict = video_distributions_dict.get(vd.video_id, {})
            dominant_emotion = vd_dict.get('dominant_emotion', 'neutral')

            emotion_averages = vd_dict.get('emotion_averages', {})
            dominant_emotion_per = round(
                emotion_averages.get(dominant_emotion, 0.0) * 100.0,
                2
            )

            video_dto_list.append(
                BaseVideoDataDto(
                    video_id=vd.video_id,
                    youtube_url=vd.youtube_url,
                    title=vd.title,
                    dominant_emotion=dominant_emotion,
                    dominant_emotion_per=dominant_emotion_per
                )
            )

        has_next = (page * size) < total

        return AllVideoDataDto(
            videos=video_dto_list,
            total=total,
            page=page,
            size=size,
            has_next=has_next
        )

    #TODO : bulk_save 확인해보기
    @staticmethod
    @transactional
    def create_user_video_recommend(user_id: str, youtube_url_list: list):
        existing_urls = {
            row.youtube_url
            for row in VideoRequest.query.filter(VideoRequest.youtube_url.in_(youtube_url_list)).all()
        }

        if existing_urls.intersection(youtube_url_list):
            raise BusinessError(APIError.VIDEO_REQUEST_DUPLICATE_URL)

        new_video_requests = [
            VideoRequest(
                user_id=user_id,
                youtube_url=url,
                youtube_full_url=f"https://www.youtube.com/watch?v={url}"
            )
            for url in youtube_url_list
        ]

        db.session.bulk_save_objects(new_video_requests)
        db.session.flush()