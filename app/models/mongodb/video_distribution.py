from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from common.utils.logging_utils import get_logger

logger = get_logger('video_distribution')

EMOTION_LABELS = ["neutral", "happy", "surprise", "sad", "angry"]
RECOMMENDATION_WEIGHTS = {"neutral": 2, "happy": 3, "surprise": 4, "sad": 3, "angry": 3}


@dataclass
class EmotionCounts:
    """실시간 집계를 위한 감정 카운트"""
    neutral: int = 0
    happy: int = 0
    surprise: int = 0
    sad: int = 0
    angry: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            'neutral': self.neutral,
            'happy': self.happy,
            'surprise': self.surprise,
            'sad': self.sad,
            'angry': self.angry
        }

    def total(self) -> int:
        return self.neutral + self.happy + self.surprise + self.sad + self.angry


@dataclass
class EmotionAverages:
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
class RecommendationScores:
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
class VideoDistribution:

    video_id: str

    average_completion_rate: float = 0.0

    emotion_averages: EmotionAverages = field(default_factory=EmotionAverages)

    recommendation_scores: RecommendationScores = field(default_factory=RecommendationScores)

    dominant_emotion: str = 'neutral'

    created_at: datetime = field(default_factory=datetime.utcnow)

    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """MongoDB 도큐먼트로 변환"""
        return {
            'video_id': self.video_id,
            'average_completion_rate': self.average_completion_rate,
            'emotion_averages': self.emotion_averages.to_dict(),
            'recommendation_scores': self.recommendation_scores.to_dict(),
            'dominant_emotion': self.dominant_emotion,
            'created_at': self.created_at,
            'updated_at': self.updated_at or datetime.utcnow()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'VideoDistribution':
        """MongoDB 도큐먼트에서 객체 생성"""
        emotion_avg = data.get('emotion_averages', {})
        rec_scores = data.get('recommendation_scores', {})

        return cls(
            video_id=data['video_id'],
            average_completion_rate=data.get('average_completion_rate', 0.0),
            emotion_averages=EmotionAverages(**emotion_avg) if emotion_avg else EmotionAverages(),
            recommendation_scores=RecommendationScores(**rec_scores) if rec_scores else RecommendationScores(),
            dominant_emotion=data.get('dominant_emotion', 'neutral'),
            created_at=data.get('created_at', datetime.utcnow()),
            updated_at=data.get('updated_at')
        )


class VideoDistributionRepository:

    COLLECTION_NAME = 'video_distribution'

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]
        self.collection.create_index('video_id', unique=True)

    def increment_emotion(self, video_id: str, emotion: str):
        """
        watch_frame 시 호출되어 감정 카운트를 증가시킴.
        $inc 연산으로 원자적 업데이트 수행.
        """
        if emotion not in EMOTION_LABELS:
            raise ValueError(f"Invalid emotion: {emotion}")

        self.collection.update_one(
            {'video_id': video_id},
            {
                '$inc': {
                    'total_frames': 1,
                    f'emotion_counts.{emotion}': 1
                },
                '$setOnInsert': {
                    'video_id': video_id,
                    'emotion_counts': {e: 0 for e in EMOTION_LABELS},
                    'emotion_averages': {e: 0.0 for e in EMOTION_LABELS},
                    'recommendation_scores': {e: 0.0 for e in EMOTION_LABELS},
                    'dominant_emotion': 'neutral',
                    'average_completion_rate': 0.0,
                    'created_at': datetime.utcnow()
                },
                '$set': {
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )

    def find_by_video_id(self, video_id: str) -> Optional[VideoDistribution]:
        """video_id로 조회"""
        doc = self.collection.find_one({'video_id': video_id})
        return VideoDistribution.from_dict(doc) if doc else None

    def find_by_video_ids(self, video_ids: list) -> Dict[str, VideoDistribution]:
        if not video_ids:
            return {}

        docs = self.collection.find({'video_id': {'$in': video_ids}})

        result = {}
        for doc in docs:
            distribution = VideoDistribution.from_dict(doc)
            result[distribution.video_id] = distribution

        return result

    def upsert(self, distribution: VideoDistribution) -> Dict[str, any]:
        from flask import g

        previous = self.find_by_video_id(distribution.video_id)
        was_insert = previous is None

        self.collection.update_one(
            {'video_id': distribution.video_id},
            {
                '$set': {
                    'average_completion_rate': distribution.average_completion_rate,
                    'emotion_averages': distribution.emotion_averages.to_dict(),
                    'recommendation_scores': distribution.recommendation_scores.to_dict(),
                    'dominant_emotion': distribution.dominant_emotion,
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'video_id': distribution.video_id,
                    'created_at': distribution.updated_at or datetime.utcnow()
                }
            },
            upsert=True
        )

        compensation_data = {
            'video_id': distribution.video_id,
            'previous_data': previous.to_dict() if previous else None,
            'was_insert': was_insert
        }

        if hasattr(g, 'saga_context'):
            g.saga_context.save_result(f'upsert_video_distribution_{distribution.video_id}', compensation_data)

        return compensation_data

    def delete_by_video_id(self, video_id: str) -> Dict[str, any]:
        from flask import g

        deleted_data = self.find_by_video_id(video_id)

        self.collection.delete_one({'video_id': video_id})

        compensation_data = {
            'video_id': video_id,
            'deleted_data': deleted_data.to_dict() if deleted_data else None
        }

        if hasattr(g, 'saga_context'):
            g.saga_context.save_result(f'delete_video_distribution_{video_id}', compensation_data)

        return compensation_data

    def compensate_upsert(self, compensation_data: Dict[str, any]):

        video_id = compensation_data['video_id']
        was_insert = compensation_data['was_insert']
        previous_data = compensation_data['previous_data']

        if was_insert:
            # #NOTE: 새로 삽입된 경우 → 삭제
            self.collection.delete_one({'video_id': video_id})
            logger.info(f"Deleted video_distribution: {video_id}")
        else:
            # #NOTE: 업데이트된 경우 → 이전 값으로 복원
            if previous_data:
                self.collection.replace_one(
                    {'video_id': video_id},
                    previous_data
                )
                logger.info(f"Restored video_distribution: {video_id}")

    def compensate_delete(self, compensation_data: Dict[str, any]):
        deleted_data = compensation_data['deleted_data']

        if deleted_data:
            # #NOTE: 삭제된 데이터 복원 (Saga Compensation)
            self.collection.insert_one(deleted_data)
            logger.info(f"Restored deleted video_distribution: {deleted_data['video_id']}")
