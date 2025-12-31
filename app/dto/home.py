from dataclasses import dataclass
from typing import List
from typing import Optional

@dataclass
class BaseVideoDataDto:
    video_id: str
    youtube_url: str
    title: str
    dominant_emotion: Optional[str] = None
    dominant_emotion_per: Optional[float] = None

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'dominant_emotion': self.dominant_emotion,
            'dominant_emotion_per': self.dominant_emotion_per
        }

@dataclass
class AllVideoDataDto:
    videos: List[BaseVideoDataDto]
    total: int
    page: int
    size: int
    has_next: bool

    def to_dict(self):
        return {
            'videos': [video.to_dict() for video in self.videos],
            'total': self.total,
            'page': self.page,
            'size': self.size,
            'has_next': self.has_next
        }

@dataclass
class CategoryVideoDataDto:
    category_name: str
    videos: List[BaseVideoDataDto]

    def to_dict(self):
        return {
            'category_name': self.category_name,
            'videos': [video.to_dict() for video in self.videos]
        }


@dataclass
class CategoryVideoDataListDto:
    video_data: List[CategoryVideoDataDto]

    def to_dict(self):
        return {
            'video_data': [category.to_dict() for category in self.video_data]
        }