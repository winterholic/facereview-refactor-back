import json
import random
from flask import current_app
from common.decorator.db_decorators import transactional_readonly, transactional
from app.models.user import User
from app.models.video import Video
from app.models import UserFavoriteGenre, VideoViewLog, VideoRequest, VideoBookmark
from app.models.mongodb.youtube_watching_data import YoutubeWatchingData, YoutubeWatchingDataRepository
from app.models.mongodb.video_distribution import VideoDistribution, VideoDistributionRepository
from common.enum.error_code import APIError
from common.enum.youtube_genre import GenreEnum
from common.exception.exceptions import BusinessError
from common.extensions import db, mongo_client, mongo_db
from common.utils.main_rec_alg import get_personalized_recommendations
from common.utils.category_rec_alg import get_top_videos_by_category_emotion, CATEGORY_PREFERRED_EMOTION
from app.dto.home import BaseVideoDataDto, CategoryVideoDataDto, CategoryVideoDataListDto, AllVideoDataDto
from sqlalchemy import or_
from bson.codec_options import CodecOptions
from bson.binary import UuidRepresentation
from common.utils.logging_utils import get_logger

logger = get_logger('home_service')

#NOTE: Redis 캐시 키 및 TTL 설정
VIDEO_POOL_CACHE_KEY = 'facereview:video_pool_cache'
CATEGORY_VIDEOS_CACHE_KEY = 'facereview:category_videos'
VIDEO_POOL_CACHE_TTL = 1800     # 30분
CATEGORY_VIDEOS_CACHE_TTL = 3600  # 1시간


class HomeService:

    @staticmethod
    @transactional_readonly
    def get_search_videos(page: int, size: int, keyword_type: str, keyword: str, emotions: list = None):
        #NOTE: Video 테이블에서 LIKE 검색
        query = Video.query.filter_by(is_deleted=0)

        if keyword_type == 'title':
            query = query.filter(Video.title.like(f'%{keyword}%'))
        elif keyword_type == 'channel_name':
            query = query.filter(Video.channel_name.like(f'%{keyword}%'))
        elif keyword_type == 'all':
            query = query.filter(
                or_(
                    Video.title.like(f'%{keyword}%'),
                    Video.channel_name.like(f'%{keyword}%')
                )
            )

        if not emotions:
            total = query.count()
            videos = query.order_by(Video.created_at.desc()).offset((page - 1) * size).limit(size).all()

            if not videos:
                return {'videos': [], 'total': total, 'page': page, 'size': size, 'has_next': False}

            video_dist_repo = VideoDistributionRepository(mongo_db)
            video_ids = [video.video_id for video in videos]
            video_stats_dict = video_dist_repo.find_by_video_ids(video_ids)

            video_dto_list = []
            for video in videos:
                video_distribution = video_stats_dict.get(video.video_id)
                if not video_distribution:
                    continue

                dominant_emotion = video_distribution.dominant_emotion or 'neutral'
                emotion_averages_dict = {
                    'neutral': video_distribution.emotion_averages.neutral,
                    'happy': video_distribution.emotion_averages.happy,
                    'surprise': video_distribution.emotion_averages.surprise,
                    'sad': video_distribution.emotion_averages.sad,
                    'angry': video_distribution.emotion_averages.angry
                }
                dominant_emotion_per = round(emotion_averages_dict.get(dominant_emotion, 0.0) * 100.0, 2)

                video_dto_list.append(BaseVideoDataDto(
                    video_id=video.video_id,
                    youtube_url=video.youtube_url,
                    title=video.title,
                    dominant_emotion=dominant_emotion,
                    dominant_emotion_per=dominant_emotion_per
                ))

            has_next = (page * size) < total
            return {'videos': video_dto_list, 'total': total, 'page': page, 'size': size, 'has_next': has_next}

        #NOTE: 감정 필터가 있으면 SQL에서 후보 video_id 전체를 뽑고 MongoDB에서 페이지네이션
        all_video_ids = [v.video_id for v in query.all()]

        if not all_video_ids:
            return {'videos': [], 'total': 0, 'page': page, 'size': size, 'has_next': False}

        video_dist_repo = VideoDistributionRepository(mongo_db)
        mongo_query = {
            'video_id': {'$in': all_video_ids},
            'dominant_emotion': {'$in': emotions}
        }

        total = video_dist_repo.collection.count_documents(mongo_query)

        video_distributions = list(
            video_dist_repo.collection.find(mongo_query)
            .sort([('created_at', -1), ('_id', -1)])
            .skip((page - 1) * size)
            .limit(size)
        )

        if not video_distributions:
            return {'videos': [], 'total': total, 'page': page, 'size': size, 'has_next': False}

        video_distributions_dict = {vd['video_id']: vd for vd in video_distributions}
        page_video_ids = list(video_distributions_dict.keys())

        videos = Video.query.filter(Video.video_id.in_(page_video_ids)).all()

        video_dto_list = []
        for video in videos:
            vd = video_distributions_dict.get(video.video_id, {})
            dominant_emotion = vd.get('dominant_emotion', 'neutral')
            emotion_averages = vd.get('emotion_averages', {})
            dominant_emotion_per = round(emotion_averages.get(dominant_emotion, 0.0) * 100.0, 2)

            video_dto_list.append(BaseVideoDataDto(
                video_id=video.video_id,
                youtube_url=video.youtube_url,
                title=video.title,
                dominant_emotion=dominant_emotion,
                dominant_emotion_per=dominant_emotion_per
            ))

        has_next = (page * size) < total
        return {'videos': video_dto_list, 'total': total, 'page': page, 'size': size, 'has_next': has_next}


    @staticmethod
    def _build_and_cache_video_pool() -> dict:
        """전체 영상 풀을 DB에서 로드하여 Redis Hash에 캐싱. 반환: {video_id: video_data_dict}"""
        from common.extensions import redis_client
        all_videos = Video.query.filter_by(is_deleted=0).all()
        video_ids = [v.video_id for v in all_videos]
        video_dist_repo = VideoDistributionRepository(mongo_db)
        video_stats_dict = video_dist_repo.find_by_video_ids(video_ids)

        pool = {}
        pipe = redis_client.pipeline() if redis_client else None

        for video in all_videos:
            dist = video_stats_dict.get(video.video_id)
            if not dist or not dist.dominant_emotion:
                continue
            emotion_dist = dist.emotion_averages.to_dict()
            if sum(emotion_dist.values()) == 0:
                continue

            entry = {
                'video_id': video.video_id,
                'youtube_url': video.youtube_url,
                'title': video.title,
                'channel_name': video.channel_name,
                'category': video.category.value if hasattr(video.category, 'value') else video.category,
                'duration': video.duration,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'created_at': video.created_at.isoformat() if video.created_at else None,
                'is_deleted': video.is_deleted,
                'emotion_distribution': emotion_dist,
                'dominant_emotion': dist.dominant_emotion,
                'average_completion_rate': dist.average_completion_rate,
                'watching_data_count': 0
            }
            pool[video.video_id] = entry
            if pipe:
                pipe.hset(VIDEO_POOL_CACHE_KEY, video.video_id, json.dumps(entry))

        if pipe and pool:
            pipe.expire(VIDEO_POOL_CACHE_KEY, VIDEO_POOL_CACHE_TTL)
            pipe.execute()
            logger.info(f"video_pool_cache 빌드 완료: {len(pool)}개 영상 캐싱")

        return pool

    @staticmethod
    def _get_video_pool_from_cache() -> dict | None:
        """Redis Hash에서 전체 영상 풀 조회. 캐시 없으면 None 반환"""
        from common.extensions import redis_client
        if not redis_client:
            return None
        raw = redis_client.hgetall(VIDEO_POOL_CACHE_KEY)
        if not raw:
            return None
        return {vid: json.loads(data) for vid, data in raw.items()}

    @staticmethod
    def _build_and_cache_category_videos() -> list:
        """카테고리별 영상 계산 후 Redis Hash에 캐싱. 반환: List[CategoryVideoDataDto]"""
        from common.extensions import redis_client
        all_videos = Video.query.filter_by(is_deleted=0).all()
        video_ids = [v.video_id for v in all_videos]
        video_dist_repo = VideoDistributionRepository(mongo_db)
        video_stats_dict = video_dist_repo.find_by_video_ids(video_ids)

        #NOTE: 카테고리별 전체 영상 풀 (감정 데이터 없을 때 랜덤 폴백용)
        raw_videos_by_category = {genre.value: [] for genre in GenreEnum}
        for video in all_videos:
            cat = video.category.value if hasattr(video.category, 'value') else video.category
            if cat in raw_videos_by_category:
                raw_videos_by_category[cat].append(video)

        #NOTE: 감정 데이터가 있는 영상만 분류 (알고리즘 입력용)
        emotion_videos_by_category = {genre.value: [] for genre in GenreEnum}
        for video in all_videos:
            dist = video_stats_dict.get(video.video_id)
            if not dist or not dist.dominant_emotion:
                continue
            emotion_dist = dist.emotion_averages.to_dict()
            if sum(emotion_dist.values()) == 0:
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
                'dominant_emotion': dist.dominant_emotion,
                'average_completion_rate': dist.average_completion_rate
            }
            cat = video.category.value if hasattr(video.category, 'value') else video.category
            if cat in emotion_videos_by_category:
                emotion_videos_by_category[cat].append(video_dict)

        top_videos_by_category = get_top_videos_by_category_emotion(
            videos_by_category=emotion_videos_by_category,
            limit=20
        )

        category_dtos = []
        pipe = redis_client.pipeline() if redis_client else None

        for category_name, videos in top_videos_by_category.items():
            if videos:
                cache_entries = []
                video_dtos = []
                for video in videos:
                    emotion_dist = video.get('emotion_distribution', {})
                    dominant_emotion = video.get('dominant_emotion', 'none')
                    dominant_emotion_per = round(emotion_dist[dominant_emotion] * 100.0, 2) if (emotion_dist and dominant_emotion in emotion_dist) else 0.0

                    #NOTE: 카테고리 선호 감정 비율 저장 (write-through 재정렬용)
                    cat_val = video.get('category')
                    cat_str = cat_val.value if hasattr(cat_val, 'value') else cat_val
                    try:
                        genre_enum = GenreEnum(cat_str)
                        preferred_emotion_str = CATEGORY_PREFERRED_EMOTION.get(genre_enum, 'neutral')
                    except (ValueError, KeyError):
                        preferred_emotion_str = 'neutral'
                    preferred_emotion_ratio = emotion_dist.get(preferred_emotion_str, 0.0)

                    cache_entries.append({
                        'video_id': video['video_id'],
                        'youtube_url': video['youtube_url'],
                        'title': video['title'],
                        'dominant_emotion': dominant_emotion,
                        'dominant_emotion_per': dominant_emotion_per,
                        'emotion_distribution': emotion_dist,
                        'preferred_emotion_ratio': preferred_emotion_ratio
                    })
                    video_dtos.append(BaseVideoDataDto(
                        video_id=video['video_id'],
                        youtube_url=video['youtube_url'],
                        title=video['title'],
                        dominant_emotion=dominant_emotion,
                        dominant_emotion_per=dominant_emotion_per
                    ))
            else:
                #NOTE: 감정 데이터 없는 카테고리 → 해당 카테고리 랜덤 영상으로 폴백
                raw_candidates = raw_videos_by_category.get(category_name, [])
                if not raw_candidates:
                    continue
                sampled = random.sample(raw_candidates, min(20, len(raw_candidates)))
                cache_entries = [
                    {
                        'video_id': v.video_id,
                        'youtube_url': v.youtube_url,
                        'title': v.title,
                        'dominant_emotion': None,
                        'dominant_emotion_per': 0.0,
                        'emotion_distribution': {},
                        'preferred_emotion_ratio': 0.0
                    }
                    for v in sampled
                ]
                video_dtos = [
                    BaseVideoDataDto(
                        video_id=v.video_id,
                        youtube_url=v.youtube_url,
                        title=v.title,
                        dominant_emotion=None,
                        dominant_emotion_per=0.0
                    )
                    for v in sampled
                ]

            category_dtos.append(CategoryVideoDataDto(category_name=category_name, videos=video_dtos))
            if pipe:
                pipe.hset(CATEGORY_VIDEOS_CACHE_KEY, category_name, json.dumps(cache_entries))

        if pipe and category_dtos:
            pipe.expire(CATEGORY_VIDEOS_CACHE_KEY, CATEGORY_VIDEOS_CACHE_TTL)
            pipe.execute()
            logger.info(f"category_videos_cache 빌드 완료: {len(category_dtos)}개 카테고리 캐싱")

        return category_dtos

    @staticmethod
    def _get_category_videos_from_cache() -> list | None:
        """Redis Hash에서 카테고리별 영상 조회. 캐시 없으면 None 반환"""
        from common.extensions import redis_client
        if not redis_client:
            return None
        raw = redis_client.hgetall(CATEGORY_VIDEOS_CACHE_KEY)
        if not raw:
            return None
        category_dtos = []
        for cat_name, videos_json in raw.items():
            videos = json.loads(videos_json)
            video_dtos = [
                BaseVideoDataDto(
                    video_id=v['video_id'],
                    youtube_url=v['youtube_url'],
                    title=v['title'],
                    dominant_emotion=v.get('dominant_emotion'),
                    dominant_emotion_per=v.get('dominant_emotion_per', 0.0)
                )
                for v in videos
            ]
            category_dtos.append(CategoryVideoDataDto(category_name=cat_name, videos=video_dtos))
        return category_dtos

    @staticmethod
    @transactional_readonly
    def get_personalized_videos(user_id: str, limit: int = 20):
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        favorite_genres = [fg.genre.value for fg in user.favorite_genres.all()]

        #NOTE: 유저별 데이터 (빠름 - 개인 데이터만 조회)
        user_view_logs = VideoViewLog.query.filter_by(user_id=user_id).all()
        viewed_video_ids = {log.video_id for log in user_view_logs}
        watching_data_repo = YoutubeWatchingDataRepository(mongo_db)
        recent_watching_data_objs = watching_data_repo.find_by_user_id(user_id, limit=20)

        #NOTE: 영상 풀 캐시에서 조회 (없으면 DB에서 빌드 후 캐싱)
        video_pool = HomeService._get_video_pool_from_cache()
        if video_pool is None:
            logger.info("video_pool_cache miss → DB에서 빌드")
            video_pool = HomeService._build_and_cache_video_pool()

        all_videos_dict = list(video_pool.values())
        video_category_map = {vid: data['category'] for vid, data in video_pool.items()}

        user_logs_dict = [
            {'video_id': log.video_id, 'created_at': log.created_at}
            for log in user_view_logs
        ]

        recent_watching_data = []
        for wd in recent_watching_data_objs:
            if wd.dominant_emotion is None:
                continue
            emotion_pct = wd.emotion_percentages.to_dict()
            recent_watching_data.append({
                'video_id': wd.video_id,
                'category': video_category_map.get(wd.video_id),
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

        #NOTE: 감정 데이터 부족으로 추천 결과 없음 → 선호 장르 랜덤 폴백, 없으면 전체 풀 폴백
        if not recommended_videos:
            genre_videos = [v for v in all_videos_dict if v.get('category') in favorite_genres]
            candidates = genre_videos if genre_videos else all_videos_dict
            sampled = random.sample(candidates, min(limit, len(candidates)))
            return [
                BaseVideoDataDto(
                    video_id=v['video_id'],
                    youtube_url=v['youtube_url'],
                    title=v['title'],
                    dominant_emotion=None,
                    dominant_emotion_per=0.0
                )
                for v in sampled
            ]

        result_dtos = []
        for video in recommended_videos:
            emotion_dist = video.get('emotion_distribution', {})
            dominant_emotion = video.get('dominant_emotion', 'none')
            dominant_emotion_per = round(emotion_dist[dominant_emotion] * 100.0, 2) if (emotion_dist and dominant_emotion in emotion_dist) else 0.0
            result_dtos.append(BaseVideoDataDto(
                video_id=video['video_id'],
                youtube_url=video['youtube_url'],
                title=video['title'],
                dominant_emotion=dominant_emotion,
                dominant_emotion_per=dominant_emotion_per
            ))

        return result_dtos

    @staticmethod
    @transactional_readonly
    def get_videos_by_category_emotions():
        #NOTE: 카테고리 영상 캐시에서 조회 (없으면 DB에서 빌드 후 캐싱)
        category_dtos = HomeService._get_category_videos_from_cache()
        if category_dtos is None:
            logger.info("category_videos_cache miss → DB에서 빌드")
            category_dtos = HomeService._build_and_cache_category_videos()

        return CategoryVideoDataListDto(video_data=category_dtos)



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

    @staticmethod
    @transactional
    def toggle_bookmark(user_id: str, video_id: str):
        video = Video.query.filter_by(video_id=video_id, is_deleted=0).first()
        if not video:
            raise BusinessError(APIError.VIDEO_NOT_FOUND)

        existing = VideoBookmark.query.filter_by(user_id=user_id, video_id=video_id).first()
        if existing:
            db.session.delete(existing)
            return {'is_bookmarked': False, 'message': '북마크가 해제되었습니다.'}

        db.session.add(VideoBookmark(user_id=user_id, video_id=video_id))
        return {'is_bookmarked': True, 'message': '북마크에 추가되었습니다.'}

    @staticmethod
    @transactional_readonly
    def get_bookmark_videos(user_id: str, page: int, size: int, emotion: str) -> AllVideoDataDto:
        bookmarked_video_ids = [
            b.video_id for b in VideoBookmark.query.filter_by(user_id=user_id).all()
        ]

        if not bookmarked_video_ids:
            return AllVideoDataDto(videos=[], total=0, page=page, size=size, has_next=False)

        video_dist_repo = VideoDistributionRepository(mongo_db)

        query = {'video_id': {'$in': bookmarked_video_ids}}
        if emotion != 'all':
            query['dominant_emotion'] = emotion

        total = video_dist_repo.collection.count_documents(query)

        video_distributions = list(
            video_dist_repo.collection.find(query)
            .sort([('created_at', -1), ('_id', -1)])
            .skip((page - 1) * size)
            .limit(size)
        )

        if not video_distributions:
            return AllVideoDataDto(videos=[], total=total, page=page, size=size, has_next=False)

        video_distributions_dict = {vd['video_id']: vd for vd in video_distributions}
        page_video_ids = list(video_distributions_dict.keys())

        videos = Video.query.filter(Video.video_id.in_(page_video_ids)).all()

        video_dto_list = []
        for video in videos:
            vd = video_distributions_dict.get(video.video_id, {})
            dominant_emotion = vd.get('dominant_emotion', 'neutral')
            emotion_averages = vd.get('emotion_averages', {})
            dominant_emotion_per = round(emotion_averages.get(dominant_emotion, 0.0) * 100.0, 2)

            video_dto_list.append(BaseVideoDataDto(
                video_id=video.video_id,
                youtube_url=video.youtube_url,
                title=video.title,
                dominant_emotion=dominant_emotion,
                dominant_emotion_per=dominant_emotion_per
            ))

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