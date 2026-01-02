from typing import Dict, List, Optional
from datetime import datetime
from threading import Lock


class WatchingDataCache:

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
        return cls._instance

    def init_watching_data(
        self,
        video_view_log_id: str,
        user_id: str,
        video_id: str,
        duration: int = None
    ):

        with self._lock:
            if video_view_log_id not in self._cache:
                self._cache[video_view_log_id] = {
                    'user_id': user_id,
                    'video_id': video_id,
                    'duration': duration,
                    'frames': [],
                    'created_at': datetime.utcnow()
                }

    def add_frame_data(
        self,
        video_view_log_id: str,
        millisecond: int,
        emotion_percentages: Dict[str, float],
        most_emotion: str
    ):

        with self._lock:
            if video_view_log_id in self._cache:
                frame_data = {
                    'millisecond': millisecond,
                    'emotion_percentages': emotion_percentages,
                    'most_emotion': most_emotion
                }
                self._cache[video_view_log_id]['frames'].append(frame_data)

    def get_watching_data(self, video_view_log_id: str) -> Optional[Dict]:

        with self._lock:
            return self._cache.get(video_view_log_id)

    def remove_watching_data(self, video_view_log_id: str) -> Optional[Dict]:
        with self._lock:
            return self._cache.pop(video_view_log_id, None)

    def clear_all(self):
        with self._lock:
            self._cache.clear()

    def get_cache_size(self) -> int:
        with self._lock:
            return len(self._cache)
