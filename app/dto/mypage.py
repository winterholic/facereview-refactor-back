from dataclasses import dataclass
from typing import List, Dict


@dataclass
class PasswordResetDto:
    reset_token: str
    message: str


@dataclass
class TimelineEmotionPointDto:
    x: int  # 시간 인덱스
    y: float  # 감정 비율 (0.0 ~ 100.0)

    def to_dict(self):
        return {
            'x': self.x,
            'y': self.y
        }


@dataclass
class VideoTimelineDto:
    id: str  # 감정 이름
    data: List[TimelineEmotionPointDto]

    def to_dict(self):
        return {
            'id': self.id,
            'data': [p.to_dict() for p in self.data]
        }


# ==================== 최근 본 영상 ====================

@dataclass
class RecentVideoDto:
    video_id: str
    youtube_url: str
    title: str
    dominant_emotion: str  # 가장 많이 느낀 감정
    dominant_emotion_per: float  # 비율 (0.0 ~ 100.0)
    watched_at: str  # ISO format
    timeline_data: List[VideoTimelineDto]  # 타임라인 감정 데이터

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


@dataclass
class EmotionSummaryDto:
    emotion_percentages: Dict[str, float]  # 각 감정 비율 (0.0 ~ 100.0)
    emotion_seconds: Dict[str, int]  # 각 감정을 느낀 총 초

    def to_dict(self):
        return {
            'emotion_percentages': self.emotion_percentages,
            'emotion_seconds': self.emotion_seconds
        }



@dataclass
class CategoryEmotionItemDto:
    emotion: str
    percentage: float  # 0.0 ~ 100.0

    def to_dict(self):
        return {
            'emotion': self.emotion,
            'percentage': self.percentage
        }


@dataclass
class CategoryEmotionDto:
    category: str
    top_emotions: List[CategoryEmotionItemDto]  # 상위 2개

    def to_dict(self):
        return {
            'category': self.category,
            'top_emotions': [e.to_dict() for e in self.top_emotions]
        }


@dataclass
class CategoryEmotionListDto:
    categories: List[CategoryEmotionDto]

    def to_dict(self):
        return {
            'categories': [c.to_dict() for c in self.categories]
        }


@dataclass
class EmotionTrendPointDto:
    label: str  # 주차/월/연도 레이블
    neutral: float
    happy: float
    surprise: float
    sad: float
    angry: float

    def to_dict(self):
        return {
            'label': self.label,
            'neutral': self.neutral,
            'happy': self.happy,
            'surprise': self.surprise,
            'sad': self.sad,
            'angry': self.angry
        }


@dataclass
class EmotionTrendDto:
    period: str  # 'weekly', 'monthly', 'yearly'
    data: List[EmotionTrendPointDto]

    def to_dict(self):
        return {
            'period': self.period,
            'data': [d.to_dict() for d in self.data]
        }


@dataclass
class EmotionVideoDto:
    emotion: str
    video_id: str
    youtube_url: str
    title: str
    emotion_percentage: float  # 해당 감정 비율 (0.0 ~ 100.0)

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
    percentage: float  # 0.0 ~ 100.0

    def to_dict(self):
        return {
            'category': self.category,
            'dominant_emotion': self.dominant_emotion,
            'percentage': self.percentage
        }


@dataclass
class HighlightDto:
    emotion_videos: List[EmotionVideoDto]  # 각 감정별 가장 많이 느낀 영상
    category_emotions: List[CategoryEmotionHighlightDto]  # 각 카테고리별 가장 많이 느낀 감정
    most_watched_category: str  # 가장 많이 시청한 카테고리
    most_felt_emotion: str  # 가장 많이 느낀 감정

    def to_dict(self):
        return {
            'emotion_videos': [v.to_dict() for v in self.emotion_videos],
            'category_emotions': [c.to_dict() for c in self.category_emotions],
            'most_watched_category': self.most_watched_category,
            'most_felt_emotion': self.most_felt_emotion
        }
