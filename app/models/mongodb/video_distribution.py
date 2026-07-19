from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field
from common.utils.logging_utils import get_logger

logger = get_logger('video_distribution')

EMOTION_LABELS = ["neutral", "happy", "surprise", "sad", "angry"]

#NOTE: 0.5초 간격 샘플링 기준 30프레임(실시청 15초) 미만이면 dominant_emotion 비율이
#       한두 프레임의 우연으로 100%까지 튈 수 있어(통계적으로 무의미) 신뢰하지 않음.
MIN_RELIABLE_FRAMES = 30

#NOTE: 카테고리별 감정 가중치 (recommendation_scores·dominant_emotion 계산용)
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

#NOTE: 카테고리가 없을 때 기본 가중치
DEFAULT_WEIGHTS = {'neutral': 2.0, 'happy': 2.0, 'surprise': 2.0, 'sad': 2.0, 'angry': 2.0}


@dataclass
class EmotionCounts:
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
        if emotion not in EMOTION_LABELS:
            raise ValueError(f"Invalid emotion: {emotion}")

        #NOTE: 1단계 - emotion_counts와 total_frames 증가
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

        result = self._recalculate_scores(video_id, category, duration)
        logger.debug(
            f"영상 감정 분포 갱신: video_id={video_id}, emotion={emotion}, "
            f"category={category}, duration={duration}"
        )
        return result

    def _recalculate_scores(self, video_id: str, category: str = None, duration: int = 0) -> Optional['VideoDistribution']:
        doc = self.collection.find_one({'video_id': video_id})
        if not doc:
            return None

        total_frames = doc.get('total_frames', 0)
        emotion_counts = doc.get('emotion_counts', {})

        if total_frames == 0:
            return None

        #NOTE: 카테고리가 파라미터로 안 왔으면 문서에서 가져옴
        if not category:
            category = doc.get('category', 'etc')

        #NOTE: duration이 파라미터로 안 왔으면 문서에서 가져옴
        if not duration:
            duration = doc.get('duration', 0)

        #NOTE: emotion_averages 계산 (각 감정 비율)
        emotion_averages = {}
        for e in EMOTION_LABELS:
            count = emotion_counts.get(e, 0)
            emotion_averages[e] = round(count / total_frames, 4)

        #NOTE: recommendation_scores 계산 (카테고리 가중치 적용)
        weights = CATEGORY_WEIGHTS.get(category, DEFAULT_WEIGHTS)
        recommendation_scores = {}
        for e in EMOTION_LABELS:
            recommendation_scores[e] = round(emotion_averages[e] * weights[e], 4)

        #NOTE: dominant_emotion은 raw emotion_averages 기준 최댓값 (화면에 노출되는 그래프/퍼센트와 항상 일치해야 함)
        #       recommendation_scores(카테고리 가중치)는 watch_service의 동일감정 내 랭킹 정렬 용도로만 사용
        #       단, total_frames가 MIN_RELIABLE_FRAMES 미만이면 표본이 통계적으로 무의미하므로
        #       dominant_emotion을 확정하지 않음(None) — 프론트가 기존 "시청기록 없음" 상태로 자연스럽게 처리
        dominant_emotion = (
            max(emotion_averages, key=emotion_averages.get)
            if total_frames >= MIN_RELIABLE_FRAMES else None
        )

        #NOTE: average_completion_rate 계산 (0.5초 간격이므로 duration * 2가 완주 프레임 수)
        average_completion_rate = 0.0
        if duration > 0:
            expected_frames = duration * 2
            average_completion_rate = round(min(total_frames / expected_frames, 1.0), 4)

        #NOTE: 계산된 값들 업데이트
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

        return VideoDistribution(
            video_id=video_id,
            average_completion_rate=average_completion_rate,
            emotion_averages=EmotionAverages(**emotion_averages),
            recommendation_scores=RecommendationScores(**recommendation_scores),
            dominant_emotion=dominant_emotion
        )

    def find_by_video_id(self, video_id: str) -> Optional[VideoDistribution]:
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
            step_name = f'upsert_video_distribution_{distribution.video_id}'
            g.saga_context.save_result(step_name, compensation_data)
            g.saga_context.add_compensation(
                step_name,
                self.compensate_upsert,
                compensation_data,
            )

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
            step_name = f'delete_video_distribution_{video_id}'
            g.saga_context.save_result(step_name, compensation_data)
            g.saga_context.add_compensation(
                step_name,
                self.compensate_delete,
                compensation_data,
            )

        return compensation_data

    def compensate_upsert(self, compensation_data: Dict[str, any]):

        video_id = compensation_data['video_id']
        was_insert = compensation_data['was_insert']
        previous_data = compensation_data['previous_data']

        if was_insert:
            #NOTE: Saga에서 새로 삽입한 문서는 보상 시 제거한다.
            self.collection.delete_one({'video_id': video_id})
            logger.info(f"영상 감정 분포 삭제: {video_id}")
        else:
            #NOTE: 기존 문서를 갱신했다면 보상 시 이전 값으로 복원한다.
            if previous_data:
                self.collection.replace_one(
                    {'video_id': video_id},
                    previous_data
                )
                logger.info(f"영상 감정 분포 복원: {video_id}")

    def compensate_delete(self, compensation_data: Dict[str, any]):
        deleted_data = compensation_data['deleted_data']

        if deleted_data:
            #NOTE: Saga 보상 과정에서 삭제 전 문서를 복원한다.
            self.collection.insert_one(deleted_data)
            logger.info(f"삭제된 영상 감정 분포 복원: {deleted_data['video_id']}")
