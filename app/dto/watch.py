from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class TimelinePointDto:
    x: int
    y: float

    def to_dict(self):
        return {
            'x': self.x,
            'y': self.y
        }


@dataclass
class TimelineDataDto:
    happy: List[TimelinePointDto]
    neutral: List[TimelinePointDto]
    surprise: List[TimelinePointDto]
    sad: List[TimelinePointDto]
    angry: List[TimelinePointDto]

    def to_dict(self):
        return {
            'happy': [p.to_dict() for p in self.happy],
            'neutral': [p.to_dict() for p in self.neutral],
            'surprise': [p.to_dict() for p in self.surprise],
            'sad': [p.to_dict() for p in self.sad],
            'angry': [p.to_dict() for p in self.angry]
        }


@dataclass
class VideoDetailDto:
    video_id: str
    youtube_url: str
    title: str
    channel_name: str
    category: str
    duration: int  # 초 단위
    view_count: int
    like_count: int
    comment_count: int
    user_is_liked: bool  # 현재 사용자가 좋아요 눌렀는지 여부
    timeline_data: TimelineDataDto  # 압축된 타임라인 데이터

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'channel_name': self.channel_name,
            'category': self.category,
            'duration': self.duration,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'user_is_liked': self.user_is_liked,
            'timeline_data': self.timeline_data.to_dict()
        }


@dataclass
class RecommendedVideoDto:
    video_id: str
    youtube_url: str
    title: str
    dominant_emotion: str
    dominant_emotion_per: float  # 0.0 ~ 100.0

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'dominant_emotion': self.dominant_emotion,
            'dominant_emotion_per': self.dominant_emotion_per
        }


@dataclass
class RecommendedVideoListDto:
    videos: List[RecommendedVideoDto]
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
class CommentDto:
    comment_id: str
    user_id: str
    user_name: str
    user_profile_image_id: int
    content: str
    is_modified: bool
    created_at: str  # ISO format
    is_mine: bool  # 현재 사용자의 댓글인지 여부

    def to_dict(self):
        return {
            'comment_id': self.comment_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'user_profile_image_id': self.user_profile_image_id,
            'content': self.content,
            'is_modified': self.is_modified,
            'created_at': self.created_at,
            'is_mine': self.is_mine
        }


@dataclass
class CommentListDto:
    comments: List[CommentDto]
    total: int

    def to_dict(self):
        return {
            'comments': [c.to_dict() for c in self.comments],
            'total': self.total
        }


@dataclass
class AddCommentResponseDto:
    comment_id: str
    message: str

    def to_dict(self):
        return {
            'comment_id': self.comment_id,
            'message': self.message
        }


@dataclass
class UpdateCommentResponseDto:
    message: str

    def to_dict(self):
        return {
            'message': self.message
        }


@dataclass
class DeleteCommentResponseDto:
    message: str

    def to_dict(self):
        return {
            'message': self.message
        }


@dataclass
class ToggleLikeResponseDto:
    is_liked: bool
    like_count: int
    message: str

    def to_dict(self):
        return {
            'is_liked': self.is_liked,
            'like_count': self.like_count,
            'message': self.message
        }
