from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from common.utils.logging_utils import get_logger

logger = get_logger('video_timeline_emotion_count')


@dataclass
class VideoTimelineEmotionCount:
    video_id: str

    created_at: Optional[datetime] = None

    emotion_labels: List[str] = field(default_factory=lambda: ["neutral", "happy", "surprise", "sad", "angry"])

    counts: Dict[str, List[int]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'video_id': self.video_id,
            'created_at': self.created_at or datetime.utcnow(),
            'emotion_labels': self.emotion_labels,
            'counts': self.counts
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'VideoTimelineEmotionCount':
        return cls(
            video_id=data['video_id'],
            created_at=data.get('created_at'),
            emotion_labels=data.get('emotion_labels', ["neutral", "happy", "surprise", "sad", "angry"]),
            counts=data.get('counts', {})
        )

    def increment_emotion_at_time(self, youtube_running_time: int, emotion: str):
        time_key = str(youtube_running_time)

        if time_key not in self.counts:
            self.counts[time_key] = [0, 0, 0, 0, 0]

        try:
            emotion_index = self.emotion_labels.index(emotion)
            self.counts[time_key][emotion_index] += 1
        except ValueError:
            raise ValueError(f"Invalid emotion: {emotion}")

    def get_dominant_emotion_at_time(self, youtube_running_time: float) -> Optional[str]:
        # NOTE: centisecond 단위로 변환 (20.29초 → "2029")
        time_key = str(int(youtube_running_time * 100))

        if time_key not in self.counts:
            return None

        counts_data = self.counts[time_key]

        # NOTE: 객체 형태 {"neutral": 5, "happy": 3, ...} 또는 배열 형태 [5, 3, ...] 둘 다 지원
        if isinstance(counts_data, dict):
            if not counts_data:
                return None
            return max(counts_data, key=counts_data.get)
        else:
            # 기존 배열 형태 호환
            max_count = max(counts_data)
            if max_count == 0:
                return None
            max_index = counts_data.index(max_count)
            return self.emotion_labels[max_index]

    def get_emotion_percentages_at_time(self, youtube_running_time: float) -> Optional[Dict[str, float]]:
        # NOTE: centisecond 단위로 변환 (20.29초 → "2029")
        time_key = str(int(youtube_running_time * 100))

        if time_key not in self.counts:
            return None

        counts_data = self.counts[time_key]

        # NOTE: 객체 형태 {"neutral": 5, "happy": 3, ...} 또는 배열 형태 [5, 3, ...] 둘 다 지원
        if isinstance(counts_data, dict):
            total = sum(counts_data.values())
            if total == 0:
                return None
            return {
                label: round(counts_data.get(label, 0) / total, 3)
                for label in self.emotion_labels
            }
        else:
            # 기존 배열 형태 호환
            total = sum(counts_data)
            if total == 0:
                return None
            return {
                label: round(count / total, 3)
                for label, count in zip(self.emotion_labels, counts_data)
            }


class VideoTimelineEmotionCountRepository:

    COLLECTION_NAME = 'video_timeline_emotion_count'

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]
        # 인덱스 생성
        self.collection.create_index('video_id', unique=True)

    def find_by_video_id(self, video_id: str) -> Optional[VideoTimelineEmotionCount]:
        doc = self.collection.find_one({'video_id': video_id})
        return VideoTimelineEmotionCount.from_dict(doc) if doc else None

    def upsert(self, timeline: VideoTimelineEmotionCount) -> Dict[str, any]:
        from flask import g

        previous = self.find_by_video_id(timeline.video_id)
        was_insert = previous is None

        self.collection.update_one(
            {'video_id': timeline.video_id},
            {
                '$set': {
                    'emotion_labels': timeline.emotion_labels,
                    'counts': timeline.counts
                },
                '$setOnInsert': {
                    'video_id': timeline.video_id,
                    'created_at': timeline.created_at or datetime.utcnow()
                }
            },
            upsert=True
        )

        compensation_data = {
            'video_id': timeline.video_id,
            'previous_data': previous.to_dict() if previous else None,
            'was_insert': was_insert
        }

        if hasattr(g, 'saga_context'):
            g.saga_context.save_result(f'upsert_timeline_emotion_{timeline.video_id}', compensation_data)

        return compensation_data

    def increment_emotion(self, video_id: str, youtube_running_time: float, emotion: str):
        emotion_labels = ["neutral", "happy", "surprise", "sad", "angry"]
        if emotion not in emotion_labels:
            raise ValueError(f"Invalid emotion: {emotion}")

        # NOTE: youtube_running_time이 문자열로 올 수 있으므로 float으로 변환
        running_time_float = float(youtube_running_time)

        # NOTE: centisecond 단위로 변환 (20.29초 → "2029")
        time_key = str(int(running_time_float * 100))

        logger.debug(f"Timeline increment: video_id={video_id}, original_time={youtube_running_time}, time_key={time_key}, emotion={emotion}")

        # NOTE: counts.{time_key}.{emotion_name} 형태로 저장 (객체 구조)
        # NOTE: field_path에 점(.)이 포함되면 MongoDB가 중첩으로 해석하므로 주의
        field_path = f"counts.{time_key}.{emotion}"

        self.collection.update_one(
            {'video_id': video_id},
            {
                '$inc': {field_path: 1},
                '$setOnInsert': {
                    'video_id': video_id,
                    'emotion_labels': emotion_labels,
                    'created_at': datetime.utcnow()
                }
            },
            upsert=True
        )

        logger.debug(f"Timeline emotion incremented: video_id={video_id}, time={time_key}, emotion={emotion}")

    def delete_by_video_id(self, video_id: str) -> Dict[str, any]:
        from flask import g

        deleted_data = self.find_by_video_id(video_id)

        self.collection.delete_one({'video_id': video_id})

        compensation_data = {
            'video_id': video_id,
            'deleted_data': deleted_data.to_dict() if deleted_data else None
        }

        if hasattr(g, 'saga_context'):
            g.saga_context.save_result(f'delete_timeline_emotion_{video_id}', compensation_data)

        return compensation_data

    def compensate_upsert(self, compensation_data: Dict[str, any]):
        video_id = compensation_data['video_id']
        was_insert = compensation_data['was_insert']
        previous_data = compensation_data['previous_data']

        if was_insert:
            # #NOTE: 새로 삽입된 경우 → 삭제
            self.collection.delete_one({'video_id': video_id})
            logger.info(f"Deleted video_timeline_emotion_count: {video_id}")
        else:
            # #NOTE: 업데이트된 경우 → 이전 값으로 복원
            if previous_data:
                self.collection.replace_one(
                    {'video_id': video_id},
                    previous_data
                )
                logger.info(f"Restored video_timeline_emotion_count: {video_id}")

    def compensate_delete(self, compensation_data: Dict[str, any]):
        deleted_data = compensation_data['deleted_data']

        if deleted_data:
            # #NOTE: 삭제된 데이터 복원 (Saga Compensation)
            self.collection.insert_one(deleted_data)
            logger.info(f"Restored deleted video_timeline_emotion_count: {deleted_data['video_id']}")
