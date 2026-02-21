import uuid
import datetime as dt
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from flask import current_app
from werkzeug.security import generate_password_hash

from common.extensions import db, redis_client, mongo_db
from common.utils import decode_token
from common.decorator.db_decorators import transactional, transactional_readonly
from common.exception.exceptions import BusinessError
from common.enum.error_code import APIError
from common.utils.email_utils import (
    generate_verification_code,
    store_verification_code,
    verify_code,
    send_verification_email,
    generate_password_reset_token,
    store_password_reset_token,
    verify_password_reset_token
)

from app.models.user import User
from app.models.user_favorite_genre import UserFavoriteGenre
from app.models.user_point_history import UserPointHistory
from app.models.video import Video
from app.models.video_like import VideoLike
from app.models.video_view_log import VideoViewLog
from app.models.video_request import VideoRequest
from app.models.comment import Comment
from app.models.mongodb.youtube_watching_data import YoutubeWatchingDataRepository

from app.models.user_emotion_dna import UserEmotionDna

from app.dto.mypage import (
    RecentVideoDto,
    RecentVideoListDto,
    EmotionSummaryDto,
    HighlightDto,
    EmotionVideoDto,
    CategoryEmotionHighlightDto,
    VideoTimelineDto,
    TimelineEmotionPointDto,
    PasswordResetDto,
    CalendarDayDto,
    EmotionCalendarDto,
    MomentDto,
    DnaTraitDto,
)


def _extract_emotion_scores(scores) -> Dict[str, float]:
    """emotion_score_timeline 값을 list/dict 양쪽 형태 모두 파싱"""
    emotion_order = ['neutral', 'happy', 'surprise', 'sad', 'angry']
    result = {'neutral': 0.0, 'happy': 0.0, 'surprise': 0.0, 'sad': 0.0, 'angry': 0.0}

    if isinstance(scores, dict):
        for emotion in emotion_order:
            result[emotion] = float(scores.get(emotion, 0.0))
    elif isinstance(scores, (list, tuple)) and len(scores) >= 5:
        for i, emotion in enumerate(emotion_order):
            result[emotion] = float(scores[i])
    elif isinstance(scores, (list, tuple)):
        # 5개 미만인 경우 있는 만큼만 처리
        for i, emotion in enumerate(emotion_order[:len(scores)]):
            result[emotion] = float(scores[i])

    return result


class MypageService:
    @staticmethod
    @transactional
    def update_profile(user_id: str, name: Optional[str] = None,
                       profile_image_id: Optional[int] = None,
                       favorite_genres: Optional[List[str]] = None):
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        if name is not None:
            user.name = name

        if profile_image_id is not None:
            user.profile_image_id = profile_image_id

        if favorite_genres is not None:
            UserFavoriteGenre.query.filter_by(user_id=user_id).delete()

            for genre in favorite_genres:
                new_genre = UserFavoriteGenre(
                    user_id=user_id,
                    genre=genre
                )
                db.session.add(new_genre)

    @staticmethod
    @transactional_readonly
    def send_verification_email_service(user_id: str):
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        code = generate_verification_code(6)

        store_verification_code(user.email, code, expire_seconds=300)

        success = send_verification_email(user.email, code)

        if not success:
            raise BusinessError(APIError.INTERNAL_SERVER_ERROR, "이메일 발송에 실패했습니다.")

    @staticmethod
    @transactional
    def verify_email_code_service(user_id: str, code: str):
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        if not verify_code(user.email, code):
            raise BusinessError(APIError.AUTH_INVALID_VERIFICATION_CODE)

        user.is_verify_email_done = 1

    @staticmethod
    @transactional_readonly
    def verify_code_for_password_reset(user_id: str, code: str) -> PasswordResetDto:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        if not verify_code(user.email, code):
            raise BusinessError(APIError.AUTH_INVALID_VERIFICATION_CODE)

        token = generate_password_reset_token()

        store_password_reset_token(user.email, token, expire_seconds=600)

        return PasswordResetDto(
            reset_token=token,
            message='비밀번호 재설정 토큰이 생성되었습니다.'
        )

    @staticmethod
    @transactional
    def change_password(reset_token: str, new_password: str):
        email = verify_password_reset_token(reset_token)
        if not email:
            raise BusinessError(APIError.AUTH_INVALID_TOKEN, "유효하지 않거나 만료된 토큰입니다.")

        user = User.query.filter_by(email=email, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        hashed_password = generate_password_hash(new_password)
        user.password = hashed_password

        return {
            'message': '비밀번호가 변경되었습니다.'
        }

    @staticmethod
    @transactional_readonly
    def get_recent_videos(user_id: str, emotion: str = 'all', page: int = 1, size: int = 10) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        repo = YoutubeWatchingDataRepository(mongo_db)
        collection = repo.collection

        query = {'user_id': user_id}

        if emotion != 'all':
            query['dominant_emotion'] = emotion

        total = collection.count_documents(query)

        skip = (page - 1) * size
        has_next = (skip + size) < total

        watching_data_docs = collection.find(query).sort('created_at', -1).skip(skip).limit(size)

        videos = []
        for doc in watching_data_docs:
            video_id = doc['video_id']

            video = Video.query.filter_by(video_id=video_id, is_deleted=0).first()
            if not video:
                continue

            timeline_data = MypageService._compress_timeline(doc.get('emotion_score_timeline', {}))

            emotion_percentages = doc.get('emotion_percentages', {})
            dominant_emotion = doc.get('dominant_emotion', 'neutral')
            dominant_emotion_per = emotion_percentages.get(dominant_emotion, 0.0)

            video_dto = RecentVideoDto(
                video_id=video.video_id,
                youtube_url=f"https://www.youtube.com/watch?v={video.youtube_url}",
                title=video.title,
                dominant_emotion=dominant_emotion,
                dominant_emotion_per=dominant_emotion_per,
                watched_at=doc['created_at'].isoformat(),
                timeline_data=timeline_data
            )
            videos.append(video_dto)

        result = RecentVideoListDto(
            videos=videos,
            total=total,
            page=page,
            size=size,
            has_next=has_next
        )

        return result.to_dict()

    @staticmethod
    def _compress_timeline(emotion_score_timeline: Dict[str, list]) -> List[VideoTimelineDto]:
        if not emotion_score_timeline:
            return []

        emotion_lists = {
            'neutral': [],
            'happy': [],
            'surprise': [],
            'sad': [],
            'angry': []
        }

        # NOTE: 키가 정수로 변환 가능한 것만 필터링
        valid_keys = []
        for key in emotion_score_timeline.keys():
            try:
                int(key)
                valid_keys.append(key)
            except (ValueError, TypeError):
                continue

        sorted_keys = sorted(valid_keys, key=lambda x: int(x))

        for idx, ms_key in enumerate(sorted_keys):
            scores = _extract_emotion_scores(emotion_score_timeline[ms_key])
            emotion_lists['neutral'].append({'x': idx, 'y': scores['neutral']})
            emotion_lists['happy'].append({'x': idx, 'y': scores['happy']})
            emotion_lists['surprise'].append({'x': idx, 'y': scores['surprise']})
            emotion_lists['sad'].append({'x': idx, 'y': scores['sad']})
            emotion_lists['angry'].append({'x': idx, 'y': scores['angry']})

        data_num = len(sorted_keys)

        #NOTE: 압축 로직 (40개 이하로)
        if data_num > 40:
            parameter = round(data_num / 40, 0)

            compressed_lists = {}
            for emotion_name, emotion_list in emotion_lists.items():
                compressed = []
                temp_sum = 0
                temp_count = 0
                temp_index = 1

                for idx, point in enumerate(emotion_list):
                    temp_sum += point['y']
                    temp_count += 1

                    if temp_count == parameter or idx == len(emotion_list) - 1:
                        temp_data = round(temp_sum / temp_count, 1)
                        compressed.append({'x': temp_index, 'y': temp_data})
                        temp_sum = 0
                        temp_count = 0
                        temp_index += 1

                compressed_lists[emotion_name] = compressed
        else:
            compressed_lists = emotion_lists

        timeline_dtos = []
        for emotion_name, points in compressed_lists.items():
            emotion_points = [TimelineEmotionPointDto(x=p['x'], y=p['y']) for p in points]
            timeline_dto = VideoTimelineDto(id=emotion_name, data=emotion_points)
            timeline_dtos.append(timeline_dto)

        return timeline_dtos

    @staticmethod
    @transactional_readonly
    def get_emotion_summary(user_id: str) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        repo = YoutubeWatchingDataRepository(mongo_db)
        collection = repo.collection

        watching_data_docs = collection.find({'user_id': user_id})

        total_seconds = {
            'neutral': 0,
            'happy': 0,
            'surprise': 0,
            'sad': 0,
            'angry': 0
        }

        for doc in watching_data_docs:
            emotion_score_timeline = doc.get('emotion_score_timeline', {})

            for ms_key, scores in emotion_score_timeline.items():
                parsed_scores = _extract_emotion_scores(scores)
                total_seconds['neutral'] += parsed_scores['neutral'] * 0.1
                total_seconds['happy'] += parsed_scores['happy'] * 0.1
                total_seconds['surprise'] += parsed_scores['surprise'] * 0.1
                total_seconds['sad'] += parsed_scores['sad'] * 0.1
                total_seconds['angry'] += parsed_scores['angry'] * 0.1

        total_time = sum(total_seconds.values())

        emotion_percentages = {}
        emotion_seconds = {}

        for emotion, seconds in total_seconds.items():
            emotion_seconds[emotion] = int(seconds)
            if total_time > 0:
                emotion_percentages[emotion] = round((seconds / total_time) * 100, 1)
            else:
                emotion_percentages[emotion] = 0.0

        result = EmotionSummaryDto(
            emotion_percentages=emotion_percentages,
            emotion_seconds=emotion_seconds
        )

        return result.to_dict()

    @staticmethod
    @transactional_readonly
    def get_highlight(user_id: str) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        repo = YoutubeWatchingDataRepository(mongo_db)
        collection = repo.collection

        watching_data_docs = list(collection.find({'user_id': user_id}))

        emotion_videos_map = {}

        for doc in watching_data_docs:
            video_id = doc['video_id']
            emotion_percentages = doc.get('emotion_percentages', {})

            for emotion, percentage in emotion_percentages.items():
                if emotion not in emotion_videos_map or percentage > emotion_videos_map[emotion][1]:
                    emotion_videos_map[emotion] = (video_id, percentage)

        emotion_videos = []
        for emotion in ['neutral', 'happy', 'surprise', 'sad', 'angry']:
            if emotion in emotion_videos_map:
                video_id, percentage = emotion_videos_map[emotion]
                video = Video.query.filter_by(video_id=video_id, is_deleted=0).first()
                if video:
                    emotion_video_dto = EmotionVideoDto(
                        emotion=emotion,
                        video_id=video.video_id,
                        youtube_url=f"https://www.youtube.com/watch?v={video.youtube_url}",
                        title=video.title,
                        emotion_percentage=percentage
                    )
                    emotion_videos.append(emotion_video_dto)

        category_emotions_map = {}

        for doc in watching_data_docs:
            video_id = doc['video_id']
            video = Video.query.filter_by(video_id=video_id, is_deleted=0).first()
            if not video:
                continue

            category = video.category.value if hasattr(video.category, 'value') else video.category
            if category not in category_emotions_map:
                category_emotions_map[category] = {
                    'neutral': 0,
                    'happy': 0,
                    'surprise': 0,
                    'sad': 0,
                    'angry': 0
                }

            emotion_score_timeline = doc.get('emotion_score_timeline', {})
            for ms_key, scores in emotion_score_timeline.items():
                parsed_scores = _extract_emotion_scores(scores)
                category_emotions_map[category]['neutral'] += parsed_scores['neutral']
                category_emotions_map[category]['happy'] += parsed_scores['happy']
                category_emotions_map[category]['surprise'] += parsed_scores['surprise']
                category_emotions_map[category]['sad'] += parsed_scores['sad']
                category_emotions_map[category]['angry'] += parsed_scores['angry']

        category_emotions = []
        for category, emotions in category_emotions_map.items():
            total = sum(emotions.values())

            dominant_emotion = max(emotions, key=emotions.get)
            if total > 0:
                percentage = round((emotions[dominant_emotion] / total) * 100, 1)
            else:
                percentage = 0.0

            category_emotion_dto = CategoryEmotionHighlightDto(
                category=category,
                dominant_emotion=dominant_emotion,
                percentage=percentage
            )
            category_emotions.append(category_emotion_dto)

        category_counts = {}
        for doc in watching_data_docs:
            video_id = doc['video_id']
            video = Video.query.filter_by(video_id=video_id, is_deleted=0).first()
            if video:
                category = video.category.value if hasattr(video.category, 'value') else video.category
                category_counts[category] = category_counts.get(category, 0) + 1

        most_watched_category = max(category_counts, key=category_counts.get) if category_counts else 'none'

        total_emotions = {
            'neutral': 0,
            'happy': 0,
            'surprise': 0,
            'sad': 0,
            'angry': 0
        }

        for doc in watching_data_docs:
            emotion_score_timeline = doc.get('emotion_score_timeline', {})
            for ms_key, scores in emotion_score_timeline.items():
                parsed_scores = _extract_emotion_scores(scores)
                total_emotions['neutral'] += parsed_scores['neutral']
                total_emotions['happy'] += parsed_scores['happy']
                total_emotions['surprise'] += parsed_scores['surprise']
                total_emotions['sad'] += parsed_scores['sad']
                total_emotions['angry'] += parsed_scores['angry']

        most_felt_emotion = max(total_emotions, key=total_emotions.get) if any(total_emotions.values()) else 'neutral'

        result = HighlightDto(
            emotion_videos=emotion_videos,
            category_emotions=category_emotions,
            most_watched_category=most_watched_category,
            most_felt_emotion=most_felt_emotion
        )

        return result.to_dict()

    @staticmethod
    @transactional_readonly
    def get_emotion_calendar(user_id: str, year: int, month: Optional[int]) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        repo = YoutubeWatchingDataRepository(mongo_db)
        start_date = datetime(year, month or 1, 1)
        if month:
            end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        else:
            end_date = datetime(year + 1, 1, 1)

        docs = list(repo.collection.find({
            'user_id': user_id,
            'created_at': {'$gte': start_date, '$lt': end_date}
        }))

        daily_map: Dict[str, list] = {}
        for doc in docs:
            date_str = doc['created_at'].strftime('%Y-%m-%d')
            dominant = doc.get('dominant_emotion', 'neutral')
            ep = doc.get('emotion_percentages', {})
            intensity_val = float(ep.get(dominant, 0.0))
            timeline_len = len(doc.get('emotion_score_timeline', {}))
            watch_secs = timeline_len // 2  # 2 frames/sec → seconds

            if date_str not in daily_map:
                daily_map[date_str] = []
            daily_map[date_str].append({
                'dominant': dominant,
                'intensity': intensity_val,
                'watch_secs': watch_secs,
            })

        result_data = []
        for date_str in sorted(daily_map.keys()):
            sessions = daily_map[date_str]
            emotion_counts: Dict[str, int] = {}
            total_intensity = 0.0
            total_secs = 0

            for s in sessions:
                emotion_counts[s['dominant']] = emotion_counts.get(s['dominant'], 0) + 1
                total_intensity += s['intensity']
                total_secs += s['watch_secs']

            day_dominant = max(emotion_counts, key=emotion_counts.get)
            avg_intensity = round(min(total_intensity / len(sessions), 1.0), 3)

            result_data.append(CalendarDayDto(
                date=date_str,
                dominant_emotion=day_dominant,
                intensity=avg_intensity,
                watch_count=len(sessions),
                total_watch_time=total_secs,
            ))

        return EmotionCalendarDto(year=year, month=month, data=result_data).to_dict()

    @staticmethod
    @transactional_readonly
    def get_moments(user_id: str, emotion: str = 'all', page: int = 1, size: int = 10) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        repo = YoutubeWatchingDataRepository(mongo_db)
        docs = list(repo.collection.find({'user_id': user_id}).sort('created_at', -1).limit(200))

        #NOTE: 배치로 Video 정보 조회 (N+1 방지)
        video_ids = list({doc['video_id'] for doc in docs})
        video_map = {v.video_id: v for v in Video.query.filter(Video.video_id.in_(video_ids)).all()}

        all_moments = []
        PEAK_THRESHOLD = 80.0
        WINDOW_FRAMES = 60  # 30초 구간 (2 frames/sec * 30sec)

        for doc in docs:
            video = video_map.get(doc['video_id'])
            if not video:
                continue

            timeline = doc.get('emotion_score_timeline', {})
            watched_at = doc['created_at'].isoformat()

            try:
                sorted_keys = sorted(timeline.keys(), key=lambda k: int(k))
            except (ValueError, TypeError):
                continue

            #NOTE: 30초 구간별 피크 프레임 1개 추출
            window_best = None
            window_start = 0

            for i, key in enumerate(sorted_keys):
                scores = _extract_emotion_scores(timeline[key])
                peak_emotion = max(scores, key=scores.get)
                peak_score = scores[peak_emotion]

                if i - window_start >= WINDOW_FRAMES:
                    if window_best and window_best['score'] >= PEAK_THRESHOLD:
                        all_moments.append(window_best['moment'])
                    window_start = i
                    window_best = None

                if peak_score >= PEAK_THRESHOLD:
                    if window_best is None or peak_score > window_best['score']:
                        window_best = {
                            'score': peak_score,
                            'moment': MomentDto(
                                video_id=video.video_id,
                                video_title=video.title,
                                youtube_url=f"https://www.youtube.com/watch?v={video.youtube_url}",
                                timestamp_seconds=round(int(key) / 100.0, 1),
                                emotion=peak_emotion,
                                emotion_percentage=round(peak_score, 2),
                                thumbnail_url=f"https://img.youtube.com/vi/{video.youtube_url}/hqdefault.jpg",
                                watched_at=watched_at,
                            )
                        }

            #NOTE: 마지막 구간 처리
            if window_best and window_best['score'] >= PEAK_THRESHOLD:
                all_moments.append(window_best['moment'])

        if emotion != 'all':
            all_moments = [m for m in all_moments if m.emotion == emotion]

        all_moments.sort(key=lambda m: m.emotion_percentage, reverse=True)

        total = len(all_moments)
        start = (page - 1) * size
        paged = all_moments[start:start + size]

        return {
            'moments': [m.to_dict() for m in paged],
            'total': total,
            'has_next': (start + size) < total,
        }

    @staticmethod
    @transactional
    def get_emotion_dna(user_id: str) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        repo = YoutubeWatchingDataRepository(mongo_db)
        total_sessions = repo.collection.count_documents({'user_id': user_id})

        #NOTE: 캐시 확인 (만료 전 + 시청 증가 5 미만이면 캐시 반환)
        cached = UserEmotionDna.query.filter_by(user_id=user_id).first()
        if cached:
            if (cached.expires_at > datetime.utcnow()
                    and total_sessions - cached.based_on_videos < 5):
                return cached.dna_data

        docs = list(repo.collection.find({'user_id': user_id}))

        if not docs:
            return _build_default_dna(user_id)

        #NOTE: 감정 통계 집계
        ep_sums = {'neutral': 0.0, 'happy': 0.0, 'surprise': 0.0, 'sad': 0.0, 'angry': 0.0}
        total_completion = 0.0
        night_count = 0
        video_ids_set = set()

        for doc in docs:
            ep = doc.get('emotion_percentages', {})
            for e in ep_sums:
                ep_sums[e] += float(ep.get(e, 0.0))
            total_completion += float(doc.get('completion_rate', 0.0))
            hour = doc['created_at'].hour
            if hour >= 22 or hour <= 3:
                night_count += 1
            video_ids_set.add(doc['video_id'])

        n = len(docs)
        happy_pct = ep_sums['happy'] / n
        sad_pct = ep_sums['sad'] / n
        surprise_pct = ep_sums['surprise'] / n
        neutral_pct = ep_sums['neutral'] / n
        angry_pct = ep_sums['angry'] / n
        avg_completion = total_completion / n
        night_ratio = night_count / n

        videos = Video.query.filter(Video.video_id.in_(list(video_ids_set))).all()
        num_genres = len({(v.category.value if hasattr(v.category, 'value') else v.category) for v in videos})

        dna_type = _determine_dna_type(
            avg_completion, night_ratio, happy_pct, sad_pct,
            surprise_pct, neutral_pct, num_genres, n
        )
        dna_info = _DNA_TYPES[dna_type]
        traits = _compute_traits(dna_type, happy_pct, sad_pct, surprise_pct, neutral_pct,
                                 avg_completion, num_genres, night_ratio)
        fun_facts = _compute_fun_facts(happy_pct, avg_completion, n)

        generated_at = datetime.utcnow()
        result = {
            'dna_type': dna_type,
            'dna_title': dna_info['title'],
            'dna_description': dna_info['description'],
            'traits': traits,
            'emotion_radar': {
                'happy': int(happy_pct * 100),
                'surprise': int(surprise_pct * 100),
                'neutral': int(neutral_pct * 100),
                'sad': int(sad_pct * 100),
                'angry': int(angry_pct * 100),
            },
            'fun_facts': fun_facts,
            'generated_at': generated_at.isoformat(),
            'based_on_videos': n,
        }

        expires_at = generated_at + timedelta(days=7)
        if cached:
            cached.dna_type = dna_type
            cached.dna_data = result
            cached.based_on_videos = n
            cached.generated_at = generated_at
            cached.expires_at = expires_at
        else:
            db.session.add(UserEmotionDna(
                user_id=user_id,
                dna_type=dna_type,
                dna_data=result,
                based_on_videos=n,
                generated_at=generated_at,
                expires_at=expires_at,
            ))

        return result

    @staticmethod
    @transactional
    def withdraw_user(user_id: str, refresh_token: str = None):
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        if refresh_token and redis_client:
            payload = decode_token(refresh_token)
            exp_timestamp = payload.get('exp')
            if exp_timestamp:
                ttl_seconds = int(exp_timestamp - dt.datetime.utcnow().timestamp())
                if ttl_seconds > 0:
                    redis_client.setex(f"facereview:blacklist:{refresh_token}", ttl_seconds, "1")

        VideoLike.query.filter_by(user_id=user_id).delete()
        VideoViewLog.query.filter_by(user_id=user_id).delete()
        VideoRequest.query.filter_by(user_id=user_id).delete()
        UserFavoriteGenre.query.filter_by(user_id=user_id).delete()
        UserPointHistory.query.filter_by(user_id=user_id).delete()

        Comment.query.filter_by(user_id=user_id).update({'is_deleted': 1})

        user.is_deleted = 1


# ── 감정 DNA 헬퍼 ──────────────────────────────────────────────────────────────

_DNA_TYPES = {
    'JOYFUL_EXPLORER': {
        'title': '유쾌한 탐험가',
        'description': '새로운 장르를 두려워하지 않고, 어디서든 웃음을 찾아내는 당신!',
    },
    'EMOTIONAL_DIVER': {
        'title': '감성 다이버',
        'description': '기쁨과 슬픔을 깊게 느끼며 콘텐츠에 완전히 몰입하는 당신!',
    },
    'THRILL_SEEKER': {
        'title': '스릴 추구자',
        'description': '예상치 못한 순간에 짜릿함을 느끼는 당신!',
    },
    'CALM_OBSERVER': {
        'title': '차분한 관찰자',
        'description': '감정에 흔들리지 않고 냉철하게 콘텐츠를 분석하는 당신!',
    },
    'MOOD_SURFER': {
        'title': '무드 서퍼',
        'description': '감정의 파도를 자유롭게 타며 시청하는 당신!',
    },
    'COMFORT_LOVER': {
        'title': '안정 추구자',
        'description': '익숙한 장르에서 편안함을 찾는 당신!',
    },
    'NIGHT_OWL': {
        'title': '밤의 시청자',
        'description': '고요한 밤에 콘텐츠를 즐기는 당신!',
    },
    'BINGE_MASTER': {
        'title': '정주행 마스터',
        'description': '한번 시작하면 끝까지 보는 완주의 달인!',
    },
}

_TRAIT_POOL = {
    'happy_score':     '웃음 포인트',
    'explorer_score':  '장르 탐험가',
    'immersion_score': '몰입형 시청자',
    'thrill_score':    '짜릿함 추구자',
    'calm_score':      '차분한 관찰자',
    'night_score':     '야행성 시청자',
    'depth_score':     '감정 깊이',
}

_DNA_TRAIT_KEYS = {
    'JOYFUL_EXPLORER': ['happy_score', 'explorer_score', 'immersion_score'],
    'EMOTIONAL_DIVER': ['depth_score', 'immersion_score', 'happy_score'],
    'THRILL_SEEKER':   ['thrill_score', 'immersion_score', 'explorer_score'],
    'CALM_OBSERVER':   ['calm_score', 'immersion_score', 'explorer_score'],
    'MOOD_SURFER':     ['depth_score', 'explorer_score', 'happy_score'],
    'COMFORT_LOVER':   ['immersion_score', 'calm_score', 'happy_score'],
    'NIGHT_OWL':       ['night_score', 'immersion_score', 'happy_score'],
    'BINGE_MASTER':    ['immersion_score', 'happy_score', 'explorer_score'],
}


def _determine_dna_type(avg_completion, night_ratio, happy_pct, sad_pct,
                         surprise_pct, neutral_pct, num_genres, total_sessions) -> str:
    if avg_completion >= 0.85:
        return 'BINGE_MASTER'
    if night_ratio >= 0.40:
        return 'NIGHT_OWL'
    if surprise_pct >= 0.30:
        return 'THRILL_SEEKER'
    if neutral_pct >= 0.40:
        return 'CALM_OBSERVER'
    if (happy_pct + sad_pct) >= 0.50 and avg_completion >= 0.70:
        return 'EMOTIONAL_DIVER'
    if happy_pct >= 0.35:
        return 'JOYFUL_EXPLORER'
    if num_genres <= 2 and total_sessions >= 3:
        return 'COMFORT_LOVER'
    #NOTE: 어떤 감정도 30% 이상 지배적이지 않으면 MOOD_SURFER
    if max(happy_pct, sad_pct, surprise_pct, neutral_pct) < 0.30:
        return 'MOOD_SURFER'
    return 'JOYFUL_EXPLORER'


def _compute_traits(dna_type, happy_pct, sad_pct, surprise_pct, neutral_pct,
                    avg_completion, num_genres, night_ratio) -> list:
    scores = {
        'happy_score':     int(happy_pct * 100),
        'explorer_score':  int(min(num_genres / 16 * 100, 100)),
        'immersion_score': int(avg_completion * 100),
        'thrill_score':    int(surprise_pct * 100),
        'calm_score':      int(neutral_pct * 100),
        'night_score':     int(night_ratio * 100),
        'depth_score':     int((happy_pct + sad_pct) / 2 * 100),
    }
    keys = _DNA_TRAIT_KEYS.get(dna_type, ['happy_score', 'explorer_score', 'immersion_score'])
    return [{'trait': _TRAIT_POOL[k], 'score': scores[k]} for k in keys]


def _compute_fun_facts(happy_pct, avg_completion, total_sessions) -> list:
    AVG_HAPPY = 0.30
    AVG_COMPLETION = 0.60
    facts = []

    happy_diff = int(abs(happy_pct - AVG_HAPPY) / AVG_HAPPY * 100)
    if happy_pct >= AVG_HAPPY:
        facts.append(f"당신은 평균보다 {happy_diff}% 더 자주 웃어요")
    else:
        facts.append(f"당신은 평균보다 {happy_diff}% 덜 웃는 편이에요")

    completion_diff = int(abs(avg_completion - AVG_COMPLETION) / AVG_COMPLETION * 100)
    if avg_completion >= AVG_COMPLETION:
        facts.append(f"영상 완주율이 평균보다 {completion_diff}% 높아요")
    else:
        facts.append(f"총 {total_sessions}편의 영상을 시청했어요")

    return facts


def _build_default_dna(user_id: str) -> dict:
    #NOTE: 시청 데이터가 전혀 없는 유저의 기본 응답
    info = _DNA_TYPES['JOYFUL_EXPLORER']
    return {
        'dna_type': 'JOYFUL_EXPLORER',
        'dna_title': info['title'],
        'dna_description': info['description'],
        'traits': [
            {'trait': '웃음 포인트', 'score': 0},
            {'trait': '장르 탐험가', 'score': 0},
            {'trait': '몰입형 시청자', 'score': 0},
        ],
        'emotion_radar': {'happy': 0, 'surprise': 0, 'neutral': 0, 'sad': 0, 'angry': 0},
        'fun_facts': ['아직 시청 데이터가 없어요. 영상을 더 시청해보세요!'],
        'generated_at': datetime.utcnow().isoformat(),
        'based_on_videos': 0,
    }
