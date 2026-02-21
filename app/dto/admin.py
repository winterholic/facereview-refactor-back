from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MessageResponseDto:
    message: str

    def to_dict(self):
        return {'message': self.message}


@dataclass
class ApproveVideoResponseDto:
    video_id: str
    message: str

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'message': self.message
        }


@dataclass
class AdminUserDto:
    user_id: str
    email: str
    name: str
    role: str
    profile_image_id: int
    is_tutorial_done: bool
    is_verify_email_done: bool
    is_deleted: bool
    created_at: str
    total_watch_count: int
    total_comment_count: int

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'profile_image_id': self.profile_image_id,
            'is_tutorial_done': self.is_tutorial_done,
            'is_verify_email_done': self.is_verify_email_done,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at,
            'total_watch_count': self.total_watch_count,
            'total_comment_count': self.total_comment_count
        }


@dataclass
class AdminUserListDto:
    users: List[AdminUserDto]
    total: int
    page: int
    size: int
    has_next: bool

    def to_dict(self):
        return {
            'users': [u.to_dict() for u in self.users],
            'total': self.total,
            'page': self.page,
            'size': self.size,
            'has_next': self.has_next
        }


@dataclass
class VideoRequestDto:
    video_request_id: str
    user_id: str
    user_name: str
    youtube_url: str
    youtube_full_url: str
    category: str
    status: str
    admin_comment: Optional[str]
    created_at: str
    updated_at: str

    def to_dict(self):
        return {
            'video_request_id': self.video_request_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'youtube_url': self.youtube_url,
            'youtube_full_url': self.youtube_full_url,
            'category': self.category,
            'status': self.status,
            'admin_comment': self.admin_comment,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


@dataclass
class VideoRequestListDto:
    requests: List[VideoRequestDto]
    total: int
    page: int
    size: int
    has_next: bool

    def to_dict(self):
        return {
            'requests': [r.to_dict() for r in self.requests],
            'total': self.total,
            'page': self.page,
            'size': self.size,
            'has_next': self.has_next
        }


@dataclass
class AdminVideoDto:
    video_id: str
    youtube_url: str
    title: str
    channel_name: str
    category: str
    duration: int
    view_count: int
    like_count: int
    comment_count: int
    created_at: str
    is_deleted: bool

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
            'created_at': self.created_at,
            'is_deleted': self.is_deleted
        }


@dataclass
class AdminVideoListDto:
    videos: List[AdminVideoDto]
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
class AdminCommentDto:
    comment_id: str
    video_id: str
    video_title: str
    user_id: str
    user_name: str
    content: str
    is_modified: bool
    is_deleted: bool
    created_at: str

    def to_dict(self):
        return {
            'comment_id': self.comment_id,
            'video_id': self.video_id,
            'video_title': self.video_title,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'content': self.content,
            'is_modified': self.is_modified,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at
        }


@dataclass
class AdminCommentListDto:
    comments: List[AdminCommentDto]
    total: int
    page: int
    size: int
    has_next: bool

    def to_dict(self):
        return {
            'comments': [c.to_dict() for c in self.comments],
            'total': self.total,
            'page': self.page,
            'size': self.size,
            'has_next': self.has_next
        }
