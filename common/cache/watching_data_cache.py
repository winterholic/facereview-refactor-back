from typing import Dict, Optional
from datetime import datetime, timedelta
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
                #NOTE: TTL = duration * 1.5 (영상 길이의 1.5배), fallback 3시간
                ttl_seconds = int(duration * 1.5) if duration else 10800
                expiry_time = datetime.utcnow() + timedelta(seconds=ttl_seconds)
                self._cache[video_view_log_id] = {
                    'user_id': user_id,
                    'video_id': video_id,
                    'duration': duration,
                    'created_at': datetime.utcnow(),
                    'expiry_time': expiry_time
                }

    def get_watching_data(self, video_view_log_id: str) -> Optional[Dict]:
        data = self._cache.get(video_view_log_id)
        if data is None:
            return None
        #NOTE: lazy expiry — 접근 시 만료 여부 확인
        if datetime.utcnow() > data['expiry_time']:
            with self._lock:
                self._cache.pop(video_view_log_id, None)
            return None
        return data

    def remove_watching_data(self, video_view_log_id: str) -> Optional[Dict]:
        with self._lock:
            return self._cache.pop(video_view_log_id, None)

    def clear_all(self):
        with self._lock:
            self._cache.clear()

    def get_cache_size(self) -> int:
        #NOTE: 읽기 전용이므로 락 불필요
        return len(self._cache)
