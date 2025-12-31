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
    total_watch_count: int  # 총 시청 횟수
    total_comment_count: int  # 총 댓글 수

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
class AdminUserDetailDto:
    user_id: str
    email: str
    name: str
    role: str
    profile_image_id: int
    is_tutorial_done: bool
    is_verify_email_done: bool
    is_deleted: bool
    created_at: str
    favorite_genres: List[str]
    total_watch_count: int
    total_comment_count: int
    total_like_count: int
    recent_activity: str  # 최근 활동 일시

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
            'favorite_genres': self.favorite_genres,
            'total_watch_count': self.total_watch_count,
            'total_comment_count': self.total_comment_count,
            'total_like_count': self.total_like_count,
            'recent_activity': self.recent_activity
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
class VideoStatisticsDto:
    video_id: str
    youtube_url: str
    title: str
    view_count: int
    unique_viewer_count: int  # 고유 시청자 수
    like_count: int
    comment_count: int
    average_completion_rate: float  # 평균 시청 완료율
    dominant_emotion: str
    emotion_distribution: dict  # 감정 분포

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'view_count': self.view_count,
            'unique_viewer_count': self.unique_viewer_count,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'average_completion_rate': self.average_completion_rate,
            'dominant_emotion': self.dominant_emotion,
            'emotion_distribution': self.emotion_distribution
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

@dataclass
class DashboardOverviewDto:
    total_users: int
    active_users: int  # 지난 30일 활동 유저
    total_videos: int
    total_views: int
    total_comments: int
    pending_requests: int  # 대기중인 영상 요청
    today_new_users: int
    today_new_views: int

    def to_dict(self):
        return {
            'total_users': self.total_users,
            'active_users': self.active_users,
            'total_videos': self.total_videos,
            'total_views': self.total_views,
            'total_comments': self.total_comments,
            'pending_requests': self.pending_requests,
            'today_new_users': self.today_new_users,
            'today_new_views': self.today_new_views
        }


@dataclass
class PopularVideoDto:
    rank: int
    video_id: str
    youtube_url: str
    title: str
    view_count: int
    like_count: int
    dominant_emotion: str

    def to_dict(self):
        return {
            'rank': self.rank,
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'dominant_emotion': self.dominant_emotion
        }


@dataclass
class PopularVideoListDto:
    videos: List[PopularVideoDto]

    def to_dict(self):
        return {
            'videos': [v.to_dict() for v in self.videos]
        }


@dataclass
class RecentActivityDto:
    activity_type: str  # 'signup', 'view', 'comment', 'like', 'request'
    user_name: str
    description: str
    created_at: str

    def to_dict(self):
        return {
            'activity_type': self.activity_type,
            'user_name': self.user_name,
            'description': self.description,
            'created_at': self.created_at
        }


@dataclass
class RecentActivityListDto:
    activities: List[RecentActivityDto]

    def to_dict(self):
        return {
            'activities': [a.to_dict() for a in self.activities]
        }
