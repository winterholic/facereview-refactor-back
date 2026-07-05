import dataclasses
import json
import random
import time
from flask import current_app
from common.decorator.db_decorators import transactional_readonly, transactional
from app.models.user import User
from app.models.video import Video
from app.models import UserFavoriteGenre, VideoViewLog, VideoRequest, VideoBookmark
from app.models.video_like import VideoLike
from app.models.mongodb.youtube_watching_data import YoutubeWatchingData, YoutubeWatchingDataRepository
from app.models.mongodb.video_distribution import VideoDistribution, VideoDistributionRepository
from common.enum.error_code import APIError
from common.enum.youtube_genre import GenreEnum
from common.exception.exceptions import BusinessError
from common.extensions import db, mongo_client, mongo_db
from common.utils.recommendation_alg import compute_base_score, rank_personalized
from app.dto.home import BaseVideoDataDto, CategoryVideoDataDto, CategoryVideoDataListDto, AllVideoDataDto
from sqlalchemy import or_, func
from bson.codec_options import CodecOptions
from bson.binary import UuidRepresentation
from common.utils.logging_utils import get_logger

logger = get_logger('home_service')

#NOTE: 경주마 2단 추천 - 오프라인(Celery)이 미리 계산한 base_score 랭킹 풀/카테고리 리스트를 Redis에 보관
RECO_POOL_CACHE_KEY = 'facereview:reco:pool'          # base_score 내림차순 상위 풀(JSON list)
RECO_CATEGORY_CACHE_KEY = 'facereview:reco:category'  # 카테고리별 상위 리스트(Redis Hash)
RECO_POOL_SIZE = 1000        # 미리 뽑아두는 상위 영상 수
RECO_CATEGORY_SIZE = 20      # 카테고리별 상위 수
RECO_PERSONAL_TOP_N = 150    # 요청 시 개인화 재정렬에 쓰는 상위 후보 수
RECO_PERSONAL_RANDOM_N = 50  # 탐색용 랜덤 후보 수
RECO_CACHE_TTL = 7200        # 2시간 (30분 주기 갱신 대비 여유)

#NOTE: Redis 불통 시 워커 프로세스 인메모리 폴백 캐시 (Redis 복구되면 자동으로 공유 캐시 우선)
_MEM_CACHE = {'pool': None, 'categories': None, 'ts': 0.0}


def _mem_cache_fresh() -> bool:
    return _MEM_CACHE['pool'] is not None and (time.time() - _MEM_CACHE['ts']) < RECO_CACHE_TTL


class HomeService:

    @staticmethod
    def _get_bookmarked_ids(user_id: str, video_ids) -> set:
        #NOTE: 영상 목록 API마다 개별 북마크 조회(N+1) 대신, 응답에 실릴 video_id들만 모아 단일 쿼리로 조회
        if not user_id or not video_ids:
            return set()
        rows = db.session.query(VideoBookmark.video_id).filter(
            VideoBookmark.user_id == user_id,
            VideoBookmark.video_id.in_(video_ids)
        ).all()
        return {row.video_id for row in rows}

    @staticmethod
    @transactional_readonly
    def get_search_videos(page: int, size: int, keyword_type: str, keyword: str, emotions: list = None, user_id: str = None):
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
            bookmarked_ids = HomeService._get_bookmarked_ids(user_id, video_ids)

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
                    dominant_emotion_per=dominant_emotion_per,
                    is_bookmarked=video.video_id in bookmarked_ids
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
        bookmarked_ids = HomeService._get_bookmarked_ids(user_id, page_video_ids)

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
                dominant_emotion_per=dominant_emotion_per,
                is_bookmarked=video.video_id in bookmarked_ids
            ))

        has_next = (page * size) < total
        return {'videos': video_dto_list, 'total': total, 'page': page, 'size': size, 'has_next': has_next}


    @staticmethod
    def _slim_pool_entry(v: dict) -> dict:
        #NOTE: 요청 시 개인화 재정렬에 필요한 최소 필드만 캐시에 저장 (base_score는 이미 계산됨)
        return {
            'video_id': v['video_id'],
            'youtube_url': v['youtube_url'],
            'title': v['title'],
            'category': v['category'],
            'dominant_emotion': v['dominant_emotion'],
            'dominant_emotion_per': v['dominant_emotion_per'],
            'emotion_distribution': v['emotion_distribution'],
            'base_score': v['base_score']
        }

    @staticmethod
    def _load_scored_videos() -> list:
        #NOTE: 활성 영상 + 감정 분포(raw doc)를 조인해 영상 본질 점수(base_score) 계산 후 내림차순 정렬
        all_videos = Video.query.filter_by(is_deleted=0).all()
        video_ids = [v.video_id for v in all_videos]
        video_dist_repo = VideoDistributionRepository(mongo_db)
        raw_docs = {
            doc['video_id']: doc
            for doc in video_dist_repo.collection.find({'video_id': {'$in': video_ids}})
        }

        #NOTE: 좋아요 수를 영상당 COUNT(N+1) 대신 GROUP BY 한 방으로 집계 (빌드 성능 핵심)
        like_map = dict(
            db.session.query(VideoLike.video_id, func.count(VideoLike.video_like_id))
            .group_by(VideoLike.video_id).all()
        )

        scored = []
        for video in all_videos:
            doc = raw_docs.get(video.video_id)
            if not doc or not doc.get('dominant_emotion'):
                continue
            emotion_dist = doc.get('emotion_averages') or {}
            if not emotion_dist or sum(emotion_dist.values()) == 0:
                continue

            cat = video.category.value if hasattr(video.category, 'value') else video.category
            dominant = doc.get('dominant_emotion')
            dominant_per = round(emotion_dist.get(dominant, 0.0) * 100.0, 2)
            frames = doc.get('total_frames') or sum((doc.get('emotion_counts') or {}).values())

            entry = {
                'video_id': video.video_id,
                'youtube_url': video.youtube_url,
                'title': video.title,
                'category': cat,
                'dominant_emotion': dominant,
                'dominant_emotion_per': dominant_per,
                'emotion_distribution': emotion_dist,
                'view_count': video.view_count,
                'like_count': like_map.get(video.video_id, 0),
                'created_at': video.created_at.isoformat() if video.created_at else None,
                'average_completion_rate': doc.get('average_completion_rate', 0.0),
                'sample_frames': frames
            }
            entry['base_score'] = compute_base_score(entry)
            scored.append(entry)

        scored.sort(key=lambda x: x['base_score'], reverse=True)
        return scored

    @staticmethod
    def _entries_to_category_dtos(by_category: dict) -> list:
        #NOTE: 슬림 엔트리 dict → CategoryVideoDataDto (캐시 재읽기 없이 in-memory 결과를 바로 응답에 쓰기 위함)
        dtos = []
        for cat_name, entries in by_category.items():
            if not entries:
                continue
            video_dtos = [
                BaseVideoDataDto(
                    video_id=e['video_id'],
                    youtube_url=e['youtube_url'],
                    title=e['title'],
                    dominant_emotion=e.get('dominant_emotion'),
                    dominant_emotion_per=e.get('dominant_emotion_per', 0.0)
                )
                for e in entries
            ]
            dtos.append(CategoryVideoDataDto(category_name=cat_name, videos=video_dtos))
        return dtos

    @staticmethod
    def _build_and_cache_ranked_pool() -> tuple:
        #NOTE: Tier1 - 영상 본질 점수 상위 풀 + 카테고리별 상위 리스트를 계산해 Redis에 저장. 반환: (슬림 풀 list, 카테고리 DTO list)
        from common.extensions import redis_client
        scored = HomeService._load_scored_videos()
        pool = [HomeService._slim_pool_entry(v) for v in scored[:RECO_POOL_SIZE]]

        #NOTE: 카테고리별 상위 리스트도 동일한 base_score 기준으로 구성 (감정 있는 영상 우선)
        by_category: dict = {}
        for v in scored:
            bucket = by_category.setdefault(v['category'], [])
            if len(bucket) < RECO_CATEGORY_SIZE:
                bucket.append(HomeService._slim_pool_entry(v))

        #NOTE: 감정 데이터가 없어 비어 있는 카테고리는 해당 카테고리 랜덤 영상으로 폴백 (모든 카테고리가 무언가 반환하도록)
        deficient = [g.value for g in GenreEnum if len(by_category.get(g.value, [])) < RECO_CATEGORY_SIZE]
        if deficient:
            fill_videos = Video.query.filter(
                Video.is_deleted == 0, Video.category.in_([GenreEnum(c) for c in deficient])
            ).all()
            raw_by_cat: dict = {}
            for video in fill_videos:
                cat = video.category.value if hasattr(video.category, 'value') else video.category
                raw_by_cat.setdefault(cat, []).append(video)
            for cat in deficient:
                bucket = by_category.setdefault(cat, [])
                existing = {e['video_id'] for e in bucket}
                pad_source = [v for v in raw_by_cat.get(cat, []) if v.video_id not in existing]
                random.shuffle(pad_source)
                for v in pad_source:
                    if len(bucket) >= RECO_CATEGORY_SIZE:
                        break
                    bucket.append({
                        'video_id': v.video_id, 'youtube_url': v.youtube_url, 'title': v.title,
                        'category': cat, 'dominant_emotion': None, 'dominant_emotion_per': 0.0,
                        'emotion_distribution': {}, 'base_score': 0.0
                    })

        if redis_client:
            pipe = redis_client.pipeline()
            pipe.set(RECO_POOL_CACHE_KEY, json.dumps(pool), ex=RECO_CACHE_TTL)
            pipe.delete(RECO_CATEGORY_CACHE_KEY)
            for cat, entries in by_category.items():
                if entries:
                    pipe.hset(RECO_CATEGORY_CACHE_KEY, cat, json.dumps(entries))
            pipe.expire(RECO_CATEGORY_CACHE_KEY, RECO_CACHE_TTL)
            pipe.execute()
            logger.info(f"추천 풀 빌드 완료: 상위 {len(pool)}개 영상, {len(by_category)}개 카테고리 캐싱")

        category_dtos = HomeService._entries_to_category_dtos(by_category)

        #NOTE: Redis 유무와 무관하게 인메모리 폴백 캐시도 항상 갱신 (Redis 불통 시 요청 warm 유지)
        _MEM_CACHE['pool'] = pool
        _MEM_CACHE['categories'] = category_dtos
        _MEM_CACHE['ts'] = time.time()
        if not redis_client:
            logger.info(f"추천 풀 빌드 완료(인메모리): 상위 {len(pool)}개 영상, {len(by_category)}개 카테고리")

        return pool, category_dtos

    @staticmethod
    def _get_ranked_pool() -> list:
        #NOTE: Redis(공유) → 인메모리(폴백) → 동기 빌드 순으로 랭킹 풀 확보
        from common.extensions import redis_client
        if redis_client:
            raw = redis_client.get(RECO_POOL_CACHE_KEY)
            if raw:
                return json.loads(raw)
        if _mem_cache_fresh():
            return _MEM_CACHE['pool']
        logger.info("추천 풀 캐시 miss → 동기 빌드")
        return HomeService._build_and_cache_ranked_pool()[0]

    @staticmethod
    def _get_category_videos_from_cache() -> list | None:
        #NOTE: Redis Hash에서 카테고리별 영상 조회. 캐시 없으면 None 반환
        from common.extensions import redis_client
        if not redis_client:
            return None
        raw = redis_client.hgetall(RECO_CATEGORY_CACHE_KEY)
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

        #NOTE: 유저별 데이터만 가볍게 조회 (시청 영상 제외 + 최근 감정 프로필용)
        viewed_video_ids = {log.video_id for log in VideoViewLog.query.filter_by(user_id=user_id).all()}
        watching_data_repo = YoutubeWatchingDataRepository(mongo_db)
        recent_watching_data_objs = watching_data_repo.find_recent_summaries_by_user_id(user_id, limit=20)

        #NOTE: Tier1에서 미리 뽑아둔 base_score 랭킹 풀 로드 (무거운 계산은 오프라인에서 끝남)
        pool = HomeService._get_ranked_pool()
        pool_category_map = {v['video_id']: v['category'] for v in pool}

        recent_watching_data = []
        for wd in recent_watching_data_objs:
            dominant_emotion = wd.get('dominant_emotion')
            if dominant_emotion is None:
                continue
            recent_watching_data.append({
                'category': pool_category_map.get(wd.get('video_id')),
                'dominant_emotion': dominant_emotion,
                'emotion_percentages': wd.get('emotion_percentages', {})
            })

        #NOTE: Tier2 - 상위 150 + 랜덤 50만 개인 감정 가산점으로 순간 재정렬
        recommended_videos = rank_personalized(
            pool=pool,
            recent_watching=recent_watching_data,
            favorite_genres=favorite_genres,
            viewed_ids=viewed_video_ids,
            limit=limit,
            top_n=RECO_PERSONAL_TOP_N,
            random_n=RECO_PERSONAL_RANDOM_N
        )

        #NOTE: 풀 자체가 비었거나(감정 데이터 전무) 전부 시청함 → 선호 장르/전체 랜덤 폴백
        if not recommended_videos:
            unwatched_pool = [v for v in pool if v.get('video_id') not in viewed_video_ids]
            genre_videos = [v for v in unwatched_pool if v.get('category') in favorite_genres]
            candidates = genre_videos if genre_videos else unwatched_pool
            if not candidates:
                return []
            recommended_videos = random.sample(candidates, min(limit, len(candidates)))

        bookmarked_ids = HomeService._get_bookmarked_ids(user_id, [v['video_id'] for v in recommended_videos])
        return [
            BaseVideoDataDto(
                video_id=v['video_id'],
                youtube_url=v['youtube_url'],
                title=v['title'],
                dominant_emotion=v.get('dominant_emotion'),
                dominant_emotion_per=v.get('dominant_emotion_per', 0.0),
                is_bookmarked=v['video_id'] in bookmarked_ids
            )
            for v in recommended_videos
        ]

    @staticmethod
    @transactional_readonly
    def get_videos_by_category_emotions(user_id: str = None):
        #NOTE: Redis(공유) → 인메모리(폴백) → 동기 빌드 순. 빌드 결과는 캐시 재읽기 없이 바로 사용 (Redis 이슈 시 빈 응답 방지)
        category_dtos = HomeService._get_category_videos_from_cache()
        if not category_dtos and _mem_cache_fresh():
            category_dtos = _MEM_CACHE['categories']
        if not category_dtos:
            logger.info("카테고리 캐시 miss → 추천 풀 동기 빌드")
            _, category_dtos = HomeService._build_and_cache_ranked_pool()

        #NOTE: category_dtos는 인메모리 폴백 캐시(_MEM_CACHE)가 프로세스 전역으로 공유하는 객체일 수 있으므로
        #      절대 원본을 mutate하지 않고, 북마크 여부만 반영한 새 DTO로 복제해서 반환 (아니면 유저 A의 북마크가 다른 요청에 새어나감)
        if user_id:
            all_video_ids = [v.video_id for cat in category_dtos for v in cat.videos]
            bookmarked_ids = HomeService._get_bookmarked_ids(user_id, all_video_ids)
            if bookmarked_ids:
                category_dtos = [
                    CategoryVideoDataDto(
                        category_name=cat.category_name,
                        videos=[
                            dataclasses.replace(v, is_bookmarked=v.video_id in bookmarked_ids)
                            for v in cat.videos
                        ]
                    )
                    for cat in category_dtos
                ]

        return CategoryVideoDataListDto(video_data=category_dtos)



    @staticmethod
    @transactional_readonly
    def get_all_videos(page: int, size: int, emotion: str, user_id: str = None) -> AllVideoDataDto:
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
        bookmarked_ids = HomeService._get_bookmarked_ids(user_id, video_ids)

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
                    dominant_emotion_per=dominant_emotion_per,
                    is_bookmarked=vd.video_id in bookmarked_ids
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
                dominant_emotion_per=dominant_emotion_per,
                is_bookmarked=True  #NOTE: 이 목록 자체가 유저의 북마크 목록이므로 항상 True (별도 쿼리 불필요)
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
