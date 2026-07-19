from datetime import datetime
from typing import Dict, Optional


EMOTIONS = ('neutral', 'happy', 'surprise', 'sad', 'angry')


def empty_emotion_seconds() -> Dict[str, int]:
    return {emotion: 0 for emotion in EMOTIONS}


def build_emotion_seconds_from_timeline(timeline: Dict) -> Dict[str, int]:
    emotion_seconds = empty_emotion_seconds()
    per_second_emotion = {}

    for time_key, emotion in (timeline or {}).items():
        if emotion not in emotion_seconds:
            continue
        try:
            second = int(float(time_key) // 100)
        except (TypeError, ValueError):
            continue
        per_second_emotion[second] = emotion

    for emotion in per_second_emotion.values():
        emotion_seconds[emotion] += 1

    return emotion_seconds


def build_finalized_session_query(
    user_id: str,
    checkpoint_at: Optional[datetime] = None,
    checkpoint_session_id: Optional[str] = None,
) -> Dict:
    query = {'user_id': user_id}
    if checkpoint_at is None:
        return query

    query['$or'] = [
        {'finalized_at': {'$gt': checkpoint_at}},
        {
            'finalized_at': checkpoint_at,
            'video_view_log_id': {'$gt': checkpoint_session_id or ''},
        },
    ]
    return query
