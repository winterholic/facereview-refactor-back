import uuid
import random
import psutil
from typing import Dict, Optional
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import desc, func, or_, text

from common.extensions import db, mongo_client, mongo_db, redis_client
from common.decorator.db_decorators import transactional, transactional_readonly
from common.exception.exceptions import BusinessError
from common.enum.error_code import APIError
from common.enum.youtube_genre import GenreEnum

from app.models.user import User
from app.models.video import Video
from app.models.video_request import VideoRequest
from app.models.comment import Comment
from app.models.video_like import VideoLike
from app.models.video_view_log import VideoViewLog
from app.models.mongodb.video_distribution import VideoDistributionRepository, VideoDistribution, EmotionAverages, RecommendationScores
from app.models.mongodb.youtube_watching_data import YoutubeWatchingData, YoutubeWatchingDataRepository, EmotionPercentages

from app.dto.admin import (
    MessageResponseDto, ApproveVideoResponseDto,
    AdminUserDto, AdminUserListDto,
    VideoRequestDto, VideoRequestListDto,
    AdminVideoDto, AdminVideoListDto,
    AdminCommentDto, AdminCommentListDto,
    SignupTrendPointDto, VideoRequestPipelineDto,
    CategoryPopularityDto, EmotionDistributionDto,
    DominantEmotionCountDto, ContentHealthDto, BusinessStatsDto,
)

# NOTE: WAU는 video_view_log 전체 스캔(created_at 단독 인덱스 없음)이라 매 요청 재계산하지 않고 캐시
_WAU_CACHE_KEY = 'facereview:admin:wau'
_WAU_CACHE_TTL_SECONDS = 900


class AdminService:

    @staticmethod
    @transactional_readonly
    def get_users(keyword: Optional[str] = None, page: int = 1, size: int = 20,
                  is_deleted: Optional[bool] = None) -> Dict:
        query = db.session.query(
            User,
            func.count(func.distinct(VideoViewLog.video_view_log_id)).label('total_watch_count'),
            func.count(func.distinct(Comment.comment_id)).label('total_comment_count')
        ).outerjoin(
            VideoViewLog, User.user_id == VideoViewLog.user_id
        ).outerjoin(
            Comment, User.user_id == Comment.user_id
        ).group_by(User.user_id)

        if keyword:
            query = query.filter(
                or_(
                    User.name.like(f'%{keyword}%'),
                    User.email.like(f'%{keyword}%')
                )
            )

        if is_deleted is True:
            query = query.filter(User.is_deleted == 1)
        elif is_deleted is False:
            query = query.filter(User.is_deleted == 0)

        total = query.count()
        offset = (page - 1) * size
        results = query.order_by(desc(User.created_at)).offset(offset).limit(size).all()

        user_dtos = []
        for user, watch_count, comment_count in results:
            user_dtos.append(AdminUserDto(
                user_id=user.user_id,
                email=user.email,
                name=user.name,
                role=user.role,
                profile_image_id=user.profile_image_id,
                is_tutorial_done=bool(user.is_tutorial_done),
                is_verify_email_done=bool(user.is_verify_email_done),
                is_deleted=bool(user.is_deleted),
                created_at=user.created_at.isoformat(),
                total_watch_count=watch_count or 0,
                total_comment_count=comment_count or 0
            ))

        result_dto = AdminUserListDto(
            users=user_dtos,
            total=total,
            page=page,
            size=size,
            has_next=(offset + size < total)
        )

        return result_dto.to_dict()

    @staticmethod
    @transactional
    def deactivate_user(actor_user_id: str, user_id: str) -> Dict:
        actor = db.session.query(User).filter_by(user_id=actor_user_id).first()
        if not actor:
            raise BusinessError(APIError.USER_NOT_FOUND)

        user = db.session.query(User).filter_by(user_id=user_id).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        # NOTE: SUPER_ADMIN은 전체 대상 비활성화 가능, ADMIN은 일반(GENERAL) 유저만 가능
        if actor.role != 'SUPER_ADMIN' and user.role != 'GENERAL':
            raise BusinessError(APIError.USER_FORBIDDEN, "일반 회원만 비활성화할 수 있습니다.")

        user.is_deleted = 1
        db.session.query(Comment).filter_by(user_id=user_id).update({'is_deleted': 1})
        db.session.flush()

        return MessageResponseDto(message='사용자가 비활성화되었습니다.').to_dict()

    @staticmethod
    @transactional
    def change_user_role(user_id: str, role: str) -> Dict:
        user = db.session.query(User).filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        user.role = role
        db.session.flush()

        return MessageResponseDto(message=f'사용자 권한이 {role}으로 변경되었습니다.').to_dict()

    @staticmethod
    @transactional_readonly
    def get_video_requests(status: Optional[str] = None, page: int = 1, size: int = 20) -> Dict:
        query = db.session.query(VideoRequest, User).join(
            User, VideoRequest.user_id == User.user_id
        )

        if status:
            query = query.filter(VideoRequest.status == status)

        total = query.count()
        offset = (page - 1) * size
        results = query.order_by(desc(VideoRequest.created_at)).offset(offset).limit(size).all()

        request_dtos = []
        for video_request, user in results:
            request_dtos.append(VideoRequestDto(
                video_request_id=video_request.video_request_id,
                user_id=user.user_id,
                user_name=user.name,
                youtube_url=video_request.youtube_url,
                youtube_full_url=video_request.youtube_full_url,
                status=video_request.status,
                admin_comment=video_request.admin_comment,
                created_at=video_request.created_at.isoformat(),
                updated_at=video_request.updated_at.isoformat()
            ))

        result_dto = VideoRequestListDto(
            requests=request_dtos,
            total=total,
            page=page,
            size=size,
            has_next=(offset + size < total)
        )

        return result_dto.to_dict()

    @staticmethod
    @transactional
    def approve_video_request(request_id: str, youtube_title: str, channel_name: str, duration: int, category: str) -> Dict:
        video_request = db.session.query(VideoRequest).filter_by(
            video_request_id=request_id
        ).first()

        if not video_request:
            raise BusinessError(APIError.VIDEO_NOT_FOUND, "영상 요청을 찾을 수 없습니다.")

        if video_request.status != 'PENDING':
            raise BusinessError(APIError.INVALID_INPUT_VALUE, "이미 처리된 요청입니다.")

        existing_video = db.session.query(Video).filter_by(
            youtube_url=video_request.youtube_url
        ).first()

        if existing_video:
            raise BusinessError(APIError.VIDEO_DUPLICATE_URL)

        # NOTE: video_request는 카테고리를 안 가짐(실제 DB에 컬럼 없음, 요청 생성 시점에도 안 받음)
        #       — 승인하는 관리자가 이 시점에 고르는 값을 그대로 사용.
        new_video = Video(
            youtube_url=video_request.youtube_url,
            title=youtube_title,
            channel_name=channel_name,
            category=GenreEnum(category),
            duration=duration,
            view_count=0,
            is_deleted=0
        )
        db.session.add(new_video)
        db.session.flush()

        _mongo_db = mongo_client[current_app.config['MONGO_DB_NAME']]
        distribution_repo = VideoDistributionRepository(_mongo_db)

        initial_distribution = VideoDistribution(
            video_id=new_video.video_id,
            average_completion_rate=0.0,
            emotion_averages=EmotionAverages(),
            recommendation_scores=RecommendationScores(),
            dominant_emotion='neutral',
            updated_at=datetime.utcnow()
        )
        distribution_repo.upsert(initial_distribution)

        video_request.status = 'ACCEPTED'
        db.session.flush()

        return ApproveVideoResponseDto(
            video_id=new_video.video_id,
            message='영상 요청이 승인되었습니다.'
        ).to_dict()

    @staticmethod
    @transactional
    def reject_video_request(request_id: str, admin_comment: str) -> Dict:
        video_request = db.session.query(VideoRequest).filter_by(
            video_request_id=request_id
        ).first()

        if not video_request:
            raise BusinessError(APIError.VIDEO_NOT_FOUND, "영상 요청을 찾을 수 없습니다.")

        if video_request.status != 'PENDING':
            raise BusinessError(APIError.INVALID_INPUT_VALUE, "이미 처리된 요청입니다.")

        video_request.status = 'REJECTED'
        video_request.admin_comment = admin_comment
        db.session.flush()

        return MessageResponseDto(message='영상 요청이 거절되었습니다.').to_dict()

    @staticmethod
    @transactional_readonly
    def get_videos(keyword: Optional[str] = None, category: Optional[str] = None,
                   page: int = 1, size: int = 20) -> Dict:
        query = db.session.query(Video).filter_by(is_deleted=0)

        if keyword:
            query = query.filter(
                or_(
                    Video.title.like(f'%{keyword}%'),
                    Video.channel_name.like(f'%{keyword}%')
                )
            )

        if category:
            category_enum = GenreEnum(category)
            query = query.filter(Video.category == category_enum)

        total = query.count()
        offset = (page - 1) * size
        videos = query.order_by(desc(Video.created_at)).offset(offset).limit(size).all()

        video_dtos = []
        for video in videos:
            like_count = db.session.query(VideoLike).filter_by(video_id=video.video_id).count()
            comment_count = db.session.query(Comment).filter_by(
                video_id=video.video_id, is_deleted=0
            ).count()

            video_dtos.append(AdminVideoDto(
                video_id=video.video_id,
                youtube_url=video.youtube_url,
                title=video.title,
                channel_name=video.channel_name or '',
                category=video.category.value if hasattr(video.category, 'value') else video.category,
                duration=video.duration,
                view_count=video.view_count,
                like_count=like_count,
                comment_count=comment_count,
                created_at=video.created_at.isoformat(),
                is_deleted=bool(video.is_deleted)
            ))

        result_dto = AdminVideoListDto(
            videos=video_dtos,
            total=total,
            page=page,
            size=size,
            has_next=(offset + size < total)
        )

        return result_dto.to_dict()

    @staticmethod
    @transactional
    def delete_video(video_id: str) -> Dict:
        video = db.session.query(Video).filter_by(video_id=video_id).first()
        if not video:
            raise BusinessError(APIError.VIDEO_NOT_FOUND)

        video.is_deleted = 1
        db.session.flush()

        return MessageResponseDto(message='영상이 삭제되었습니다.').to_dict()

    @staticmethod
    @transactional_readonly
    def get_comments(video_id: Optional[str] = None, keyword: Optional[str] = None,
                     is_deleted: Optional[bool] = None, page: int = 1, size: int = 20) -> Dict:
        query = db.session.query(Comment, Video, User).join(
            Video, Comment.video_id == Video.video_id
        ).join(
            User, Comment.user_id == User.user_id
        )

        if video_id:
            query = query.filter(Comment.video_id == video_id)

        if keyword:
            query = query.filter(Comment.content.like(f'%{keyword}%'))

        if is_deleted is True:
            query = query.filter(Comment.is_deleted == 1)
        elif is_deleted is False:
            query = query.filter(Comment.is_deleted == 0)

        total = query.count()
        offset = (page - 1) * size
        results = query.order_by(desc(Comment.created_at)).offset(offset).limit(size).all()

        comment_dtos = []
        for comment, video, user in results:
            comment_dtos.append(AdminCommentDto(
                comment_id=comment.comment_id,
                video_id=video.video_id,
                video_title=video.title,
                user_id=user.user_id,
                user_name=user.name,
                content=comment.content,
                is_modified=bool(comment.is_modified),
                is_deleted=bool(comment.is_deleted),
                created_at=comment.created_at.isoformat()
            ))

        result_dto = AdminCommentListDto(
            comments=comment_dtos,
            total=total,
            page=page,
            size=size,
            has_next=(offset + size < total)
        )

        return result_dto.to_dict()

    @staticmethod
    @transactional
    def delete_comment(comment_id: str) -> Dict:
        comment = db.session.query(Comment).filter_by(comment_id=comment_id).first()
        if not comment:
            raise BusinessError(APIError.COMMENT_NOT_FOUND)

        comment.is_deleted = 1
        db.session.flush()

        return MessageResponseDto(message='댓글이 삭제되었습니다.').to_dict()

    @staticmethod
    @transactional_readonly
    def get_business_stats() -> Dict:
        return BusinessStatsDto(
            signup_trend=AdminService._get_signup_trend(days=7),
            weekly_active_users=AdminService._get_weekly_active_users(),
            video_request_pipeline=AdminService._get_video_request_pipeline(),
            content_health=AdminService._get_content_health(),
            computed_at=datetime.utcnow().isoformat()
        ).to_dict()

    SIGNUP_TREND_PERIODS = {
        '7d': (7, 'day'),
        '30d': (30, 'day'),
        '3m': (90, 'week'),
        '1y': (365, 'month'),
        '3y': (1095, 'month'),
    }

    @staticmethod
    @transactional_readonly
    def get_signup_trend(period: str) -> Dict:
        days, granularity = AdminService.SIGNUP_TREND_PERIODS.get(period, (7, 'day'))
        start_date = (datetime.utcnow() - timedelta(days=days - 1)).date()
        today = datetime.utcnow().date()

        # NOTE: 일 단위로 한 번만 집계(가입일 수는 기간과 무관하게 적음)하고, 주/월 버킷은
        #       파이썬에서 묶는다 — YEARWEEK/DATE_FORMAT 등 SQL 날짜연산 없이 동일 결과.
        day_expr = func.date(User.created_at)
        rows = db.session.query(
            day_expr.label('day'),
            func.count(User.user_id).label('cnt')
        ).filter(
            day_expr >= start_date
        ).group_by(day_expr).all()
        daily_counts = {row.day: row.cnt for row in rows}

        if granularity == 'day':
            points = []
            for i in range(days):
                d = start_date + timedelta(days=i)
                points.append((d, daily_counts.get(d, 0)))
        elif granularity == 'week':
            bucket_totals = {}
            cursor = start_date - timedelta(days=start_date.weekday())
            while cursor <= today:
                bucket_totals[cursor] = 0
                cursor += timedelta(days=7)
            for d, cnt in daily_counts.items():
                monday = d - timedelta(days=d.weekday())
                bucket_totals[monday] = bucket_totals.get(monday, 0) + cnt
            points = sorted(bucket_totals.items())
        else:  # month
            bucket_totals = {}
            cursor = start_date.replace(day=1)
            while cursor <= today:
                bucket_totals[cursor] = 0
                cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            for d, cnt in daily_counts.items():
                month_start = d.replace(day=1)
                bucket_totals[month_start] = bucket_totals.get(month_start, 0) + cnt
            points = sorted(bucket_totals.items())

        return {
            'points': [SignupTrendPointDto(date=str(d), count=c).to_dict() for d, c in points],
            'granularity': granularity,
        }

    @staticmethod
    def _get_signup_trend(days: int = 7) -> list:
        start_date = (datetime.utcnow() - timedelta(days=days - 1)).date()

        # NOTE: group_by('day')처럼 문자열 라벨을 그대로 넘기면 SQLAlchemy 2.0에서
        #       ArgumentError("Textual SQL ... should be explicitly declared as text(...)")로
        #       500 남 — 실제 컬럼 표현식 객체를 select/group_by 양쪽에 재사용해야 함.
        day_expr = func.date(User.created_at)
        rows = db.session.query(
            day_expr.label('day'),
            func.count(User.user_id).label('cnt')
        ).filter(
            day_expr >= start_date
        ).group_by(day_expr).all()

        counts_by_day = {str(day): cnt for day, cnt in rows}

        trend = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            trend.append(SignupTrendPointDto(date=str(day), count=counts_by_day.get(str(day), 0)))

        return trend

    @staticmethod
    def _get_weekly_active_users() -> int:
        if redis_client:
            try:
                cached = redis_client.get(_WAU_CACHE_KEY)
                if cached is not None:
                    return int(cached)
            except Exception:
                pass

        week_ago = datetime.utcnow() - timedelta(days=7)
        wau = db.session.query(
            func.count(func.distinct(VideoViewLog.user_id))
        ).filter(
            VideoViewLog.created_at >= week_ago,
            VideoViewLog.user_id.isnot(None)
        ).scalar() or 0

        if redis_client:
            try:
                redis_client.setex(_WAU_CACHE_KEY, _WAU_CACHE_TTL_SECONDS, wau)
            except Exception:
                pass

        return wau

    @staticmethod
    def _get_video_request_pipeline() -> VideoRequestPipelineDto:
        pending_count = db.session.query(VideoRequest).filter_by(status='PENDING').count()

        avg_minutes = db.session.query(
            func.avg(func.timestampdiff(text('MINUTE'), VideoRequest.created_at, VideoRequest.updated_at))
        ).filter(
            VideoRequest.status.in_(['ACCEPTED', 'REJECTED']),
            VideoRequest.updated_at >= datetime.utcnow() - timedelta(days=30)
        ).scalar()

        return VideoRequestPipelineDto(
            pending_count=pending_count,
            # NOTE: 최근 30일 처리 이력이 없으면 avg_minutes가 None(SQL AVG의 정상 결과) —
            #       0.0으로 기본값 처리하면 "0분 만에 처리됨"으로 오해됨. null 그대로 노출해
            #       프론트가 "데이터 없음"으로 구분 표시하게 함.
            avg_processing_minutes=round(float(avg_minutes), 1) if avg_minutes is not None else None
        )

    @staticmethod
    def _get_content_health() -> ContentHealthDto:
        # NOTE: youtube_watching_data(세션 원본, 매우 큼)를 매번 스캔하지 않고, watch_frame마다
        #       이미 실시간 갱신되는 video_distribution(영상당 1문서, 작음)에서 바로 평균낸다.
        # NOTE: 영상 승인 시점(approve_video_request)에 시청 이전부터 emotion_averages가 전부
        #       0인 문서가 미리 생성됨(total_frames 필드 자체가 없음). 이걸 걸러내지 않고 평균내면
        #       실제 시청된 영상들의 감정 벡터(항상 합=1)가 0벡터와 섞여 평균 감정분포 합이 100%
        #       밑으로 처짐 — $match로 실제 시청 프레임이 쌓인 문서만 집계 대상으로 한정.
        try:
            pipeline = [
                {'$match': {'total_frames': {'$gt': 0}}},
                {'$facet': {
                    'averages': [{'$group': {
                        '_id': None,
                        'avg_completion_rate': {'$avg': '$average_completion_rate'},
                        'avg_neutral': {'$avg': '$emotion_averages.neutral'},
                        'avg_happy': {'$avg': '$emotion_averages.happy'},
                        'avg_surprise': {'$avg': '$emotion_averages.surprise'},
                        'avg_sad': {'$avg': '$emotion_averages.sad'},
                        'avg_angry': {'$avg': '$emotion_averages.angry'},
                    }}],
                    'dominant_counts': [
                        {'$group': {'_id': '$dominant_emotion', 'count': {'$sum': 1}}},
                        {'$sort': {'count': -1}},
                    ],
                }},
            ]
            facets = list(mongo_db.video_distribution.aggregate(pipeline))
            facet = facets[0] if facets else {}
        except Exception:
            facet = {}

        averages = facet.get('averages') or []
        doc = averages[0] if averages else {}
        avg_completion_rate = round(doc.get('avg_completion_rate') or 0.0, 4)
        emotion_distribution = EmotionDistributionDto(
            neutral=round(doc.get('avg_neutral') or 0.0, 4),
            happy=round(doc.get('avg_happy') or 0.0, 4),
            surprise=round(doc.get('avg_surprise') or 0.0, 4),
            sad=round(doc.get('avg_sad') or 0.0, 4),
            angry=round(doc.get('avg_angry') or 0.0, 4),
        )

        dominant_emotion_video_counts = [
            DominantEmotionCountDto(emotion=row['_id'], video_count=row['count'])
            for row in (facet.get('dominant_counts') or [])
            if row.get('_id')
        ]

        # NOTE: GenreEnum 자체가 16종으로 자연히 상한이 있어 limit 없이 전체를 반환(더 이상
        #       "Top 5"가 아니라 카테고리별 전체 조회수 — 필드명은 하위 호환을 위해 유지).
        category_rows = db.session.query(
            Video.category, func.sum(Video.view_count)
        ).filter(Video.is_deleted == 0).group_by(Video.category).order_by(
            func.sum(Video.view_count).desc()
        ).all()

        category_top5 = [
            CategoryPopularityDto(
                category=category.value if hasattr(category, 'value') else category,
                view_count=int(total_views or 0)
            )
            for category, total_views in category_rows
        ]

        return ContentHealthDto(
            avg_completion_rate=avg_completion_rate,
            emotion_distribution=emotion_distribution,
            category_top5=category_top5,
            dominant_emotion_video_counts=dominant_emotion_video_counts
        )

    @staticmethod
    def get_system_status() -> Dict:
        # 서버 리소스
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        server = {
            'cpu_usage': round(cpu, 1),
            'memory_usage': round(mem.percent, 1),
            'memory_total_mb': round(mem.total / (1024 * 1024), 1),
            'disk_usage': round(disk.percent, 1),
        }

        # API 요청 통계 (Redis 카운터)
        total_requests_1h = 0
        avg_response_time_ms = 0.0
        error_rate_1h = 0.0

        if redis_client:
            try:
                req_count = redis_client.get('facereview:metrics:requests:1h')
                total_requests_1h = int(req_count) if req_count else 0

                err_count = redis_client.get('facereview:metrics:errors:1h')
                errors = int(err_count) if err_count else 0
                error_rate_1h = round(errors / total_requests_1h * 100, 2) if total_requests_1h > 0 else 0.0

                times = redis_client.lrange('facereview:metrics:response_times', 0, -1)
                if times:
                    avg_response_time_ms = round(sum(float(t) for t in times) / len(times), 2)
            except Exception:
                pass

        api_stats = {
            'total_requests_1h': total_requests_1h,
            'avg_response_time_ms': avg_response_time_ms,
            'error_rate_1h': error_rate_1h,
        }

        # DB/인프라 연결 상태
        mysql_status = 'ok'
        redis_status = 'ok'
        mongodb_status = 'ok'

        try:
            db.session.execute(text('SELECT 1'))
        except Exception:
            mysql_status = 'error'

        if redis_client:
            try:
                redis_client.ping()
            except Exception:
                redis_status = 'error'
        else:
            redis_status = 'error'

        try:
            mongo_db.command('ping')
        except Exception:
            mongodb_status = 'error'

        connections = {
            'mysql': mysql_status,
            'redis': redis_status,
            'mongodb': mongodb_status,
        }

        return {
            'server': server,
            'api': api_stats,
            'connections': connections,
            'checked_at': datetime.utcnow().isoformat(),
        }

    @staticmethod
    def generate_dummy_data(user_id: str, count: int = 30) -> dict:
        all_videos = Video.query.filter(Video.is_deleted == 0, Video.duration > 0).all()
        if not all_videos:
            raise BusinessError(APIError.VIDEO_NOT_FOUND, "더미 데이터를 생성할 영상이 없습니다.")

        videos = random.sample(all_videos, min(count, len(all_videos)))

        watching_data_repo = YoutubeWatchingDataRepository(mongo_db)
        video_dist_repo = VideoDistributionRepository(mongo_db)

        created_video_ids = []

        for video in videos:
            try:
                category = video.category.value if hasattr(video.category, 'value') else str(video.category)
                frames = _generate_session_frames(category, video.duration)
                stats = _compute_session_stats(frames)

                most_emotion_timeline = {f['time_key']: f['dominant'] for f in frames}
                emotion_score_timeline = {
                    f['time_key']: [
                        f['scores']['neutral'],
                        f['scores']['happy'],
                        f['scores']['surprise'],
                        f['scores']['sad'],
                        f['scores']['angry'],
                    ]
                    for f in frames
                }

                created_at = datetime.utcnow() - timedelta(
                    days=random.randint(0, 90),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                video_view_log_id = str(uuid.uuid4())

                watching_data = YoutubeWatchingData(
                    user_id=user_id,
                    video_id=video.video_id,
                    video_view_log_id=video_view_log_id,
                    created_at=created_at,
                    completion_rate=1.0,
                    dominant_emotion=stats['dominant'],
                    emotion_percentages=EmotionPercentages(**stats['percentages']),
                    most_emotion_timeline=most_emotion_timeline,
                    emotion_score_timeline=emotion_score_timeline,
                )
                watching_data_repo.insert(watching_data)

                view_log = VideoViewLog(
                    video_view_log_id=video_view_log_id,
                    user_id=user_id,
                    video_id=video.video_id,
                    created_at=created_at,
                    updated_at=created_at,
                )
                db.session.add(view_log)
                db.session.commit()

                #NOTE: youtube_watching_data 삽입 후 video_distribution 재계산
                from app.services.watching_data_service import WatchingDataService
                WatchingDataService._update_video_distribution(video_dist_repo, watching_data_repo, video.video_id)

                created_video_ids.append(video.video_id)

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"[dummy] video_id={video.video_id} 생성 실패: {e}")
                continue

        return {
            'message': f'더미 데이터 생성 완료 ({len(created_video_ids)}개 영상)',
            'created_count': len(created_video_ids),
            'user_id': user_id,
            'video_ids': created_video_ids,
        }


# ── 더미 데이터 생성 헬퍼 ─────────────────────────────────────────────────────

_EMOTIONS = ['neutral', 'happy', 'surprise', 'sad', 'angry']

_CATEGORY_WEIGHTS = {
    'drama':       {'neutral': 0.5, 'happy': 2.5, 'surprise': 2.0, 'sad': 3.0, 'angry': 2.0},
    'eating':      {'neutral': 1.0, 'happy': 4.0, 'surprise': 2.5, 'sad': 0.2, 'angry': 0.5},
    'travel':      {'neutral': 0.8, 'happy': 3.5, 'surprise': 3.0, 'sad': 0.5, 'angry': 0.3},
    'cook':        {'neutral': 2.5, 'happy': 3.0, 'surprise': 1.5, 'sad': 0.3, 'angry': 0.5},
    'show':        {'neutral': 0.3, 'happy': 4.5, 'surprise': 2.5, 'sad': 1.0, 'angry': 0.8},
    'information': {'neutral': 3.0, 'happy': 1.5, 'surprise': 2.5, 'sad': 0.5, 'angry': 1.5},
    'horror':      {'neutral': 0.5, 'happy': 0.3, 'surprise': 5.0, 'sad': 1.5, 'angry': 2.0},
    'exercise':    {'neutral': 2.0, 'happy': 3.5, 'surprise': 1.5, 'sad': 0.5, 'angry': 1.5},
    'vlog':        {'neutral': 2.5, 'happy': 2.5, 'surprise': 1.5, 'sad': 1.5, 'angry': 1.0},
    'game':        {'neutral': 1.5, 'happy': 3.0, 'surprise': 2.5, 'sad': 1.5, 'angry': 2.5},
    'sports':      {'neutral': 1.0, 'happy': 3.5, 'surprise': 4.0, 'sad': 1.0, 'angry': 1.5},
    'music':       {'neutral': 1.5, 'happy': 4.0, 'surprise': 2.0, 'sad': 2.5, 'angry': 1.0},
    'animal':      {'neutral': 1.0, 'happy': 4.5, 'surprise': 3.0, 'sad': 0.8, 'angry': 0.2},
    'beauty':      {'neutral': 2.0, 'happy': 3.5, 'surprise': 2.5, 'sad': 0.5, 'angry': 0.5},
    'comedy':      {'neutral': 0.2, 'happy': 5.0, 'surprise': 2.0, 'sad': 0.3, 'angry': 0.5},
    'etc':         {'neutral': 2.5, 'happy': 2.0, 'surprise': 2.0, 'sad': 1.5, 'angry': 1.5},
}
_DEFAULT_WEIGHTS = {'neutral': 2.0, 'happy': 2.0, 'surprise': 2.0, 'sad': 2.0, 'angry': 2.0}


def _pick_dominant(category: str, prev: str = None) -> str:
    #NOTE: 78% 확률로 이전 프레임과 같은 감정 (시간적 연속성)
    if prev and random.random() < 0.78:
        return prev
    #NOTE: 12% 확률로 카테고리 무관 랜덤 감정 (mood shift)
    if random.random() < 0.12:
        return random.choice(_EMOTIONS)
    w = _CATEGORY_WEIGHTS.get(category, _DEFAULT_WEIGHTS)
    return random.choices(_EMOTIONS, weights=[w[e] for e in _EMOTIONS], k=1)[0]


def _make_frame_scores(dominant: str) -> dict:
    #NOTE: 실제 모델 특성 반영: dominant 감정은 72~95% 수준으로 치우침
    dominant_score = random.uniform(72.0, 95.0)
    remaining = 100.0 - dominant_score
    others = [e for e in _EMOTIONS if e != dominant]
    #NOTE: 제곱 랜덤으로 나머지 감정도 편중되게 분배
    raw = [random.random() ** 2 for _ in others]
    total = sum(raw) or 1.0
    scores = {dominant: dominant_score}
    for e, r in zip(others, raw):
        scores[e] = remaining * r / total
    s = sum(scores.values())
    return {e: round(scores[e] / s * 100, 2) for e in _EMOTIONS}


def _generate_session_frames(category: str, duration: int) -> list:
    frames = []
    prev = None
    for i in range(duration * 2):  # 0.5초 간격 = 초당 2프레임
        dominant = _pick_dominant(category, prev)
        scores = _make_frame_scores(dominant)
        frames.append({
            'time_key': str(i * 50),  # centisecond 단위: 0, 50, 100, ...
            'scores': scores,
            'dominant': dominant,
        })
        prev = dominant
    return frames


def _compute_session_stats(frames: list) -> dict:
    totals = {e: 0.0 for e in _EMOTIONS}
    for f in frames:
        for e in _EMOTIONS:
            totals[e] += f['scores'][e]
    n = len(frames)
    #NOTE: 0-100 스케일 프레임 → 0-1 비율 (WatchingDataService와 동일 로직)
    percentages = {e: round(totals[e] / n / 100.0, 3) for e in _EMOTIONS}
    dominant = max(percentages, key=percentages.get)
    return {'percentages': percentages, 'dominant': dominant}
