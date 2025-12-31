from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class EmotionAveragesHistory:
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
class RecommendationScoresHistory:
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
class VideoDistributionHistory:

    video_id: str

    recorded_at: datetime

    average_completion_rate: float = 0.0

    emotion_averages: EmotionAveragesHistory = field(default_factory=EmotionAveragesHistory)

    recommendation_scores: RecommendationScoresHistory = field(default_factory=RecommendationScoresHistory)

    dominant_emotion: str = 'neutral'

    def to_dict(self) -> Dict:
        return {
            'video_id': self.video_id,
            'recorded_at': self.recorded_at,
            'average_completion_rate': self.average_completion_rate,
            'emotion_averages': self.emotion_averages.to_dict(),
            'recommendation_scores': self.recommendation_scores.to_dict(),
            'dominant_emotion': self.dominant_emotion
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'VideoDistributionHistory':
        emotion_avg = data.get('emotion_averages', {})
        rec_scores = data.get('recommendation_scores', {})

        return cls(
            video_id=data['video_id'],
            recorded_at=data['recorded_at'],
            average_completion_rate=data.get('average_completion_rate', 0.0),
            emotion_averages=EmotionAveragesHistory(**emotion_avg) if emotion_avg else EmotionAveragesHistory(),
            recommendation_scores=RecommendationScoresHistory(**rec_scores) if rec_scores else RecommendationScoresHistory(),
            dominant_emotion=data.get('dominant_emotion', 'neutral')
        )


class VideoDistributionHistoryRepository:
    COLLECTION_NAME = 'video_distribution_history'

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]
        self.collection.create_index([('video_id', 1), ('recorded_at', -1)])

    def insert(self, history: VideoDistributionHistory):
        self.collection.insert_one(history.to_dict())

    def find_by_video_id(self, video_id: str, limit: int = 30) -> List[VideoDistributionHistory]:
        docs = self.collection.find(
            {'video_id': video_id}
        ).sort('recorded_at', -1).limit(limit)

        return [VideoDistributionHistory.from_dict(doc) for doc in docs]

    def find_by_date_range(
        self,
        video_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[VideoDistributionHistory]:
        docs = self.collection.find({
            'video_id': video_id,
            'recorded_at': {
                '$gte': start_date,
                '$lte': end_date
            }
        }).sort('recorded_at', 1)

        return [VideoDistributionHistory.from_dict(doc) for doc in docs]

    def delete_old_records(self, days: int = 90):
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        self.collection.delete_many({
            'recorded_at': {'$lt': cutoff_date}
        })
