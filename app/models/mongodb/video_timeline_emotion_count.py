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

    def increment_emotion_at_time(self, millisecond: int, emotion: str):
        ms_key = str(millisecond)

        if ms_key not in self.counts:
            self.counts[ms_key] = [0, 0, 0, 0, 0]

        try:
            emotion_index = self.emotion_labels.index(emotion)
            self.counts[ms_key][emotion_index] += 1
        except ValueError:
            raise ValueError(f"Invalid emotion: {emotion}")

    def get_dominant_emotion_at_time(self, millisecond: int) -> Optional[str]:
        ms_key = str(millisecond)

        if ms_key not in self.counts:
            return None

        counts = self.counts[ms_key]
        max_count = max(counts)

        if max_count == 0:
            return None

        max_index = counts.index(max_count)
        return self.emotion_labels[max_index]

    def get_emotion_percentages_at_time(self, millisecond: int) -> Optional[Dict[str, float]]:
        ms_key = str(millisecond)

        if ms_key not in self.counts:
            return None

        counts = self.counts[ms_key]
        total = sum(counts)

        if total == 0:
            return None

        return {
            label: round(count / total, 3)
            for label, count in zip(self.emotion_labels, counts)
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

    def increment_emotion(self, video_id: str, millisecond: int, emotion: str):
        emotion_labels = ["neutral", "happy", "surprise", "sad", "angry"]
        try:
            emotion_index = emotion_labels.index(emotion)
        except ValueError:
            raise ValueError(f"Invalid emotion: {emotion}")

        ms_key = str(millisecond)
        field_path = f"counts.{ms_key}.{emotion_index}"

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
