from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from common.utils.logging_utils import get_logger

logger = get_logger('video_distribution')

EMOTION_LABELS = ["neutral", "happy", "surprise", "sad", "angry"]

# NOTE: 카테고리별 감정 가중치 (main_rec_alg.py에서 가져옴)
CATEGORY_WEIGHTS = {
    'drama': {'neutral': 0.5, 'happy': 2.5, 'surprise': 2.0, 'sad': 3.0, 'angry': 2.0},
    'eating': {'neutral': 1.0, 'happy': 4.0, 'surprise': 2.5, 'sad': 0.2, 'angry': 0.5},
    'travel': {'neutral': 0.8, 'happy': 3.5, 'surprise': 3.0, 'sad': 0.5, 'angry': 0.3},
    'cook': {'neutral': 2.5, 'happy': 3.0, 'surprise': 1.5, 'sad': 0.3, 'angry': 0.5},
    'show': {'neutral': 0.3, 'happy': 4.5, 'surprise': 2.5, 'sad': 1.0, 'angry': 0.8},
    'information': {'neutral': 3.0, 'happy': 1.5, 'surprise': 2.5, 'sad': 0.5, 'angry': 1.5},
    'horror': {'neutral': 0.5, 'happy': 0.3, 'surprise': 5.0, 'sad': 1.5, 'angry': 2.0},
    'exercise': {'neutral': 2.0, 'happy': 3.5, 'surprise': 1.5, 'sad': 0.5, 'angry': 1.5},
    'vlog': {'neutral': 2.5, 'happy': 2.5, 'surprise': 1.5, 'sad': 1.5, 'angry': 1.0},
    'game': {'neutral': 1.5, 'happy': 3.0, 'surprise': 2.5, 'sad': 1.5, 'angry': 2.5},
    'sports': {'neutral': 1.0, 'happy': 3.5, 'surprise': 4.0, 'sad': 1.0, 'angry': 1.5},
    'music': {'neutral': 1.5, 'happy': 4.0, 'surprise': 2.0, 'sad': 2.5, 'angry': 1.0},
    'animal': {'neutral': 1.0, 'happy': 4.5, 'surprise': 3.0, 'sad': 0.8, 'angry': 0.2},
    'beauty': {'neutral': 2.0, 'happy': 3.5, 'surprise': 2.5, 'sad': 0.5, 'angry': 0.5},
    'comedy': {'neutral': 0.2, 'happy': 5.0, 'surprise': 2.0, 'sad': 0.3, 'angry': 0.5},
    'etc': {'neutral': 2.5, 'happy': 2.0, 'surprise': 2.0, 'sad': 1.5, 'angry': 1.5}
}

# NOTE: 카테고리가 없을 때 기본 가중치
DEFAULT_WEIGHTS = {'neutral': 2.0, 'happy': 2.0, 'surprise': 2.0, 'sad': 2.0, 'angry': 2.0}


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

    dominant_emotion: Optional[str] = None

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

    def increment_emotion(self, video_id: str, emotion: str, category: str = None, duration: int = 0):
        """
        watch_frame 시 호출되어 감정 카운트를 증가시키고
        emotion_averages, recommendation_scores, average_completion_rate를 재계산함.
        """
        if emotion not in EMOTION_LABELS:
            raise ValueError(f"Invalid emotion: {emotion}")

        # NOTE: 1단계 - emotion_counts와 total_frames 증가
        self.collection.update_one(
            {'video_id': video_id},
            {
                '$inc': {
                    'total_frames': 1,
                    f'emotion_counts.{emotion}': 1
                },
                '$setOnInsert': {
                    'video_id': video_id,
                    'category': category,
                    'duration': duration,
                    'emotion_averages': {e: 0.0 for e in EMOTION_LABELS},
                    'recommendation_scores': {e: 0.0 for e in EMOTION_LABELS},
                    'dominant_emotion': None,
                    'average_completion_rate': 0.0,
                    'created_at': datetime.utcnow()
                },
                '$set': {
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )

        # NOTE: 2단계 - emotion_averages, recommendation_scores, average_completion_rate 재계산
        self._recalculate_scores(video_id, category, duration)

        logger.debug(f"Distribution emotion incremented: video_id={video_id}, emotion={emotion}, category={category}, duration={duration}")

    def _recalculate_scores(self, video_id: str, category: str = None, duration: int = 0):
        """
        emotion_counts와 total_frames를 기반으로
        emotion_averages, recommendation_scores, average_completion_rate를 재계산함.
        """
        doc = self.collection.find_one({'video_id': video_id})
        if not doc:
            return

        total_frames = doc.get('total_frames', 0)
        emotion_counts = doc.get('emotion_counts', {})

        if total_frames == 0:
            return

        # NOTE: 카테고리가 파라미터로 안 왔으면 문서에서 가져옴
        if not category:
            category = doc.get('category', 'etc')

        # NOTE: duration이 파라미터로 안 왔으면 문서에서 가져옴
        if not duration:
            duration = doc.get('duration', 0)

        # NOTE: emotion_averages 계산 (각 감정 비율)
        emotion_averages = {}
        for e in EMOTION_LABELS:
            count = emotion_counts.get(e, 0)
            emotion_averages[e] = round(count / total_frames, 4)

        # NOTE: recommendation_scores 계산 (카테고리 가중치 적용)
        weights = CATEGORY_WEIGHTS.get(category, DEFAULT_WEIGHTS)
        recommendation_scores = {}
        for e in EMOTION_LABELS:
            recommendation_scores[e] = round(emotion_averages[e] * weights[e], 4)

        # NOTE: dominant_emotion 결정 (recommendation_scores 기준)
        dominant_emotion = max(recommendation_scores, key=recommendation_scores.get)

        # NOTE: average_completion_rate 계산 (0.5초 간격이므로 duration * 2가 완주 프레임 수)
        average_completion_rate = 0.0
        if duration > 0:
            expected_frames = duration * 2
            average_completion_rate = round(min(total_frames / expected_frames, 1.0), 4)

        # NOTE: 계산된 값들 업데이트
        self.collection.update_one(
            {'video_id': video_id},
            {
                '$set': {
                    'emotion_averages': emotion_averages,
                    'recommendation_scores': recommendation_scores,
                    'dominant_emotion': dominant_emotion,
                    'average_completion_rate': average_completion_rate,
                    'category': category,
                    'duration': duration
                }
            }
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
