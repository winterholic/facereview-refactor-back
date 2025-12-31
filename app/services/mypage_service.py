import bcrypt
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from flask import current_app

from common.extensions import db, mongo_client, redis_client, mongo_db
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
from app.models.video import Video
from app.models.mongodb.youtube_watching_data import YoutubeWatchingDataRepository

from app.dto.mypage import (
    RecentVideoDto,
    RecentVideoListDto,
    EmotionSummaryDto,
    CategoryEmotionDto,
    CategoryEmotionItemDto,
    CategoryEmotionListDto,
    EmotionTrendDto,
    EmotionTrendPointDto,
    HighlightDto,
    EmotionVideoDto,
    CategoryEmotionHighlightDto,
    VideoTimelineDto,
    TimelineEmotionPointDto, PasswordResetDto
)


class MypageService:
    @staticmethod
    @transactional
    def update_profile(user_id: str, name: Optional[str] = None,
                       profile_image_id: Optional[int] = None,
                       favorite_genres: Optional[List[str]] = None):
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        user.name = name

        user.profile_image_id = profile_image_id

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

        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        user.password = hashed_password.decode('utf-8')

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

        sorted_keys = sorted(emotion_score_timeline.keys(), key=lambda x: int(x))

        for idx, ms_key in enumerate(sorted_keys):
            scores = emotion_score_timeline[ms_key]
            emotion_lists['neutral'].append({'x': idx, 'y': scores[0]})
            emotion_lists['happy'].append({'x': idx, 'y': scores[1]})
            emotion_lists['surprise'].append({'x': idx, 'y': scores[2]})
            emotion_lists['sad'].append({'x': idx, 'y': scores[3]})
            emotion_lists['angry'].append({'x': idx, 'y': scores[4]})

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

        db_mongo = mongo_client.get_database()
        repo = YoutubeWatchingDataRepository(db_mongo)
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
                total_seconds['neutral'] += scores[0] * 0.1
                total_seconds['happy'] += scores[1] * 0.1
                total_seconds['surprise'] += scores[2] * 0.1
                total_seconds['sad'] += scores[3] * 0.1
                total_seconds['angry'] += scores[4] * 0.1

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
    def get_category_emotions(user_id: str) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        db_mongo = mongo_client.get_database()
        repo = YoutubeWatchingDataRepository(db_mongo)
        collection = repo.collection

        watching_data_docs = collection.find({'user_id': user_id})

        category_emotions = {}

        for doc in watching_data_docs:
            video_id = doc['video_id']

            video = Video.query.filter_by(video_id=video_id, is_deleted=0).first()
            if not video:
                continue

            category = video.category.value
            if category not in category_emotions:
                category_emotions[category] = {
                    'neutral': 0,
                    'happy': 0,
                    'surprise': 0,
                    'sad': 0,
                    'angry': 0
                }

            emotion_score_timeline = doc.get('emotion_score_timeline', {})
            for ms_key, scores in emotion_score_timeline.items():
                category_emotions[category]['neutral'] += scores[0]
                category_emotions[category]['happy'] += scores[1]
                category_emotions[category]['surprise'] += scores[2]
                category_emotions[category]['sad'] += scores[3]
                category_emotions[category]['angry'] += scores[4]

        categories = []
        for category, emotions in category_emotions.items():
            total = sum(emotions.values())

            emotion_percentages = []
            for emotion, score in emotions.items():
                if total > 0:
                    percentage = round((score / total) * 100, 1)
                else:
                    percentage = 0.0
                emotion_percentages.append((emotion, percentage))

            emotion_percentages.sort(key=lambda x: x[1], reverse=True)
            top_2 = emotion_percentages[:2]

            top_emotions = [
                CategoryEmotionItemDto(emotion=emotion, percentage=percentage)
                for emotion, percentage in top_2
            ]

            category_dto = CategoryEmotionDto(
                category=category,
                top_emotions=top_emotions
            )
            categories.append(category_dto)

        result = CategoryEmotionListDto(categories=categories)
        return result.to_dict()

    @staticmethod
    @transactional_readonly
    def get_emotion_trend(user_id: str, period: str) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        db_mongo = mongo_client.get_database()
        repo = YoutubeWatchingDataRepository(db_mongo)
        collection = repo.collection

        watching_data_docs = collection.find({'user_id': user_id})

        period_emotions = {}

        for doc in watching_data_docs:
            created_at = doc['created_at']

            if period == 'weekly':
                label = f"{created_at.year}-W{created_at.isocalendar()[1]:02d}"
            elif period == 'monthly':
                label = f"{created_at.year}-{created_at.month:02d}"
            elif period == 'yearly':
                label = str(created_at.year)
            else:
                raise BusinessError(APIError.INVALID_INPUT_VALUE, "period는 'weekly', 'monthly', 'yearly' 중 하나여야 합니다.")

            if label not in period_emotions:
                period_emotions[label] = {
                    'neutral': 0,
                    'happy': 0,
                    'surprise': 0,
                    'sad': 0,
                    'angry': 0
                }

            emotion_score_timeline = doc.get('emotion_score_timeline', {})
            for ms_key, scores in emotion_score_timeline.items():
                period_emotions[label]['neutral'] += scores[0]
                period_emotions[label]['happy'] += scores[1]
                period_emotions[label]['surprise'] += scores[2]
                period_emotions[label]['sad'] += scores[3]
                period_emotions[label]['angry'] += scores[4]

        data_points = []
        for label in sorted(period_emotions.keys()):
            emotions = period_emotions[label]
            total = sum(emotions.values())

            if total > 0:
                point = EmotionTrendPointDto(
                    label=label,
                    neutral=round((emotions['neutral'] / total) * 100, 1),
                    happy=round((emotions['happy'] / total) * 100, 1),
                    surprise=round((emotions['surprise'] / total) * 100, 1),
                    sad=round((emotions['sad'] / total) * 100, 1),
                    angry=round((emotions['angry'] / total) * 100, 1)
                )
            else:
                point = EmotionTrendPointDto(
                    label=label,
                    neutral=0.0,
                    happy=0.0,
                    surprise=0.0,
                    sad=0.0,
                    angry=0.0
                )

            data_points.append(point)

        result = EmotionTrendDto(period=period, data=data_points)
        return result.to_dict()

    @staticmethod
    @transactional_readonly
    def get_highlight(user_id: str) -> Dict:
        user = User.query.filter_by(user_id=user_id, is_deleted=0).first()
        if not user:
            raise BusinessError(APIError.USER_NOT_FOUND)

        db_mongo = mongo_client.get_database()
        repo = YoutubeWatchingDataRepository(db_mongo)
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

            category = video.category.value
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
                category_emotions_map[category]['neutral'] += scores[0]
                category_emotions_map[category]['happy'] += scores[1]
                category_emotions_map[category]['surprise'] += scores[2]
                category_emotions_map[category]['sad'] += scores[3]
                category_emotions_map[category]['angry'] += scores[4]

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
                category = video.category.value
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
                total_emotions['neutral'] += scores[0]
                total_emotions['happy'] += scores[1]
                total_emotions['surprise'] += scores[2]
                total_emotions['sad'] += scores[3]
                total_emotions['angry'] += scores[4]

        most_felt_emotion = max(total_emotions, key=total_emotions.get) if any(total_emotions.values()) else 'neutral'

        result = HighlightDto(
            emotion_videos=emotion_videos,
            category_emotions=category_emotions,
            most_watched_category=most_watched_category,
            most_felt_emotion=most_felt_emotion
        )

        return result.to_dict()
