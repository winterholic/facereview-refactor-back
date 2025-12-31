from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from common.utils.logging_utils import get_logger

logger = get_logger('youtube_watching_data')


@dataclass
class EmotionPercentages:
    neutral: float = 0.0
    happy: float = 0.0
    surprise: float = 0.0
    sad: float = 0.0
    angry: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            'neutral': self.neutral,
            'happy': self.happy,
            'surprise': self.surprise,
            'sad': self.sad,
            'angry': self.angry
        }


@dataclass
class ClientInfo:
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_os: Optional[str] = None
    device_browser: Optional[str] = None
    is_mobile: bool = False

    def to_dict(self) -> Dict:
        return {
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'device': {
                'os': self.device_os,
                'browser': self.device_browser,
                'is_mobile': self.is_mobile
            }
        }


@dataclass
class YoutubeWatchingData:
    user_id: str
    video_id: str
    video_view_log_id: str

    created_at: datetime
    completion_rate: float = 0.0
    dominant_emotion: str = 'neutral'

    emotion_percentages: EmotionPercentages = field(default_factory=EmotionPercentages)

    most_emotion_timeline: Dict[str, str] = field(default_factory=dict)

    emotion_score_timeline: Dict[str, list] = field(default_factory=dict)

    client_info: ClientInfo = field(default_factory=ClientInfo)

    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'video_id': self.video_id,
            'video_view_log_id': self.video_view_log_id,
            'created_at': self.created_at,
            'completion_rate': self.completion_rate,
            'dominant_emotion': self.dominant_emotion,
            'emotion_percentages': self.emotion_percentages.to_dict(),
            'most_emotion_timeline': self.most_emotion_timeline,
            'emotion_score_timeline': self.emotion_score_timeline,
            'client_info': self.client_info.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'YoutubeWatchingData':
        emotion_pct = data.get('emotion_percentages', {})
        client_data = data.get('client_info', {})
        device_data = client_data.get('device', {})

        return cls(
            user_id=data['user_id'],
            video_id=data['video_id'],
            video_view_log_id=data['video_view_log_id'],
            created_at=data['created_at'],
            completion_rate=data.get('completion_rate', 0.0),
            dominant_emotion=data.get('dominant_emotion', 'neutral'),
            emotion_percentages=EmotionPercentages(**emotion_pct) if emotion_pct else EmotionPercentages(),
            most_emotion_timeline=data.get('most_emotion_timeline', {}),
            emotion_score_timeline=data.get('emotion_score_timeline', {}),
            client_info=ClientInfo(
                ip_address=client_data.get('ip_address'),
                user_agent=client_data.get('user_agent'),
                device_os=device_data.get('os'),
                device_browser=device_data.get('browser'),
                is_mobile=device_data.get('is_mobile', False)
            )
        )

    def add_emotion_at_time(self, millisecond: int, emotion: str, scores: list):
        ms_key = str(millisecond)
        self.most_emotion_timeline[ms_key] = emotion
        self.emotion_score_timeline[ms_key] = scores


class YoutubeWatchingDataRepository:

    COLLECTION_NAME = 'youtube_watching_data'

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]
        # 인덱스 생성
        self.collection.create_index([('user_id', 1), ('created_at', -1)])
        self.collection.create_index([('video_id', 1), ('created_at', -1)])
        self.collection.create_index('video_view_log_id', unique=True)

    def insert(self, watching_data: YoutubeWatchingData) -> Dict[str, any]:
        from flask import g

        self.collection.insert_one(watching_data.to_dict())

        compensation_data = {
            'video_view_log_id': watching_data.video_view_log_id
        }

        if hasattr(g, 'saga_context'):
            g.saga_context.save_result(f'insert_watching_data_{watching_data.video_view_log_id}', compensation_data)

        return compensation_data

    def find_by_video_view_log_id(self, video_view_log_id: str) -> Optional[YoutubeWatchingData]:
        doc = self.collection.find_one({'video_view_log_id': video_view_log_id})
        return YoutubeWatchingData.from_dict(doc) if doc else None

    def find_by_user_id(self, user_id: str, limit: int = 20):
        docs = self.collection.find(
            {'user_id': user_id}
        ).sort('created_at', -1).limit(limit)

        return [YoutubeWatchingData.from_dict(doc) for doc in docs]

    def find_by_video_id(self, video_id: str, limit: int = 100):
        docs = self.collection.find(
            {'video_id': video_id}
        ).sort('created_at', -1).limit(limit)

        return [YoutubeWatchingData.from_dict(doc) for doc in docs]

    def delete_by_video_view_log_id(self, video_view_log_id: str) -> Dict[str, any]:
        from flask import g

        deleted_data = self.find_by_video_view_log_id(video_view_log_id)

        self.collection.delete_one({'video_view_log_id': video_view_log_id})

        compensation_data = {
            'video_view_log_id': video_view_log_id,
            'deleted_data': deleted_data.to_dict() if deleted_data else None
        }

        if hasattr(g, 'saga_context'):
            g.saga_context.save_result(f'delete_watching_data_{video_view_log_id}', compensation_data)

        return compensation_data

    def count_by_video_id(self, video_id: str) -> int:
        return self.collection.count_documents({'video_id': video_id})

    def compensate_insert(self, compensation_data: Dict[str, any]):
        video_view_log_id = compensation_data['video_view_log_id']

        # #NOTE: 삽입된 데이터 삭제 (Saga Compensation)
        self.collection.delete_one({'video_view_log_id': video_view_log_id})
        logger.info(f"Deleted youtube_watching_data: {video_view_log_id}")

    def compensate_delete(self, compensation_data: Dict[str, any]):
        deleted_data = compensation_data['deleted_data']

        if deleted_data:
            # #NOTE: 삭제된 데이터 복원 (Saga Compensation)
            self.collection.insert_one(deleted_data)
            logger.info(f"Restored deleted youtube_watching_data: {deleted_data['video_view_log_id']}")
