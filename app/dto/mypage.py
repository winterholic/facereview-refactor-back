from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class PasswordResetDto:
    reset_token: str
    message: str


@dataclass
class TimelineEmotionPointDto:
    x: int
    y: float

    def to_dict(self):
        return {'x': self.x, 'y': self.y}


@dataclass
class VideoTimelineDto:
    id: str
    data: List[TimelineEmotionPointDto]

    def to_dict(self):
        return {'id': self.id, 'data': [p.to_dict() for p in self.data]}


# ==================== 1.1 최근 시청 ====================

@dataclass
class RecentVideoDto:
    video_id: str
    youtube_url: str
    title: str
    dominant_emotion: str
    dominant_emotion_per: float
    watched_at: str
    timeline_data: List[VideoTimelineDto]

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'dominant_emotion': self.dominant_emotion,
            'dominant_emotion_per': self.dominant_emotion_per,
            'watched_at': self.watched_at,
            'timeline_data': [t.to_dict() for t in self.timeline_data]
        }


@dataclass
class RecentVideoListDto:
    videos: List[RecentVideoDto]
    total: int
    page: int
    size: int
    has_next: bool

    def to_dict(self):
        return {
            'videos': [v.to_dict() for v in self.videos],
            'total': self.total,
            'page': self.page,
            'size': self.size,
            'has_next': self.has_next
        }


# ==================== 1.2 감정 요약 ====================

@dataclass
class EmotionSummaryDto:
    emotion_percentages: Dict[str, float]
    emotion_seconds: Dict[str, int]

    def to_dict(self):
        return {
            'emotion_percentages': self.emotion_percentages,
            'emotion_seconds': self.emotion_seconds
        }


# ==================== 1.3 하이라이트 ====================

@dataclass
class EmotionVideoDto:
    emotion: str
    video_id: str
    youtube_url: str
    title: str
    emotion_percentage: float

    def to_dict(self):
        return {
            'emotion': self.emotion,
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'emotion_percentage': self.emotion_percentage
        }


@dataclass
class CategoryEmotionHighlightDto:
    category: str
    dominant_emotion: str
    percentage: float

    def to_dict(self):
        return {
            'category': self.category,
            'dominant_emotion': self.dominant_emotion,
            'percentage': self.percentage
        }


@dataclass
class HighlightDto:
    emotion_videos: List[EmotionVideoDto]
    category_emotions: List[CategoryEmotionHighlightDto]
    most_watched_category: str
    most_felt_emotion: str

    def to_dict(self):
        return {
            'emotion_videos': [v.to_dict() for v in self.emotion_videos],
            'category_emotions': [c.to_dict() for c in self.category_emotions],
            'most_watched_category': self.most_watched_category,
            'most_felt_emotion': self.most_felt_emotion
        }


# ==================== 2.1 감정 캘린더 ====================

@dataclass
class CalendarDayDto:
    date: str
    dominant_emotion: str
    intensity: float
    watch_count: int
    total_watch_time: int

    def to_dict(self):
        return {
            'date': self.date,
            'dominant_emotion': self.dominant_emotion,
            'intensity': self.intensity,
            'watch_count': self.watch_count,
            'total_watch_time': self.total_watch_time
        }


@dataclass
class EmotionCalendarDto:
    year: int
    month: Optional[int]
    data: List[CalendarDayDto]

    def to_dict(self):
        return {
            'year': self.year,
            'month': self.month,
            'data': [d.to_dict() for d in self.data]
        }


# ==================== 2.2 베스트 모먼트 ====================

@dataclass
class MomentDto:
    video_id: str
    video_title: str
    youtube_url: str
    timestamp_seconds: float
    emotion: str
    emotion_percentage: float
    thumbnail_url: str
    watched_at: str

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'video_title': self.video_title,
            'youtube_url': self.youtube_url,
            'timestamp_seconds': self.timestamp_seconds,
            'emotion': self.emotion,
            'emotion_percentage': self.emotion_percentage,
            'thumbnail_url': self.thumbnail_url,
            'watched_at': self.watched_at
        }


# ==================== 2.3 감정 DNA ====================

@dataclass
class DnaTraitDto:
    trait: str
    score: int

    def to_dict(self):
        return {'trait': self.trait, 'score': self.score}
