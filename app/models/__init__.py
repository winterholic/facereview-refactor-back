from common.extensions import db

from app.models.user import User
from app.models.user_favorite_genre import UserFavoriteGenre
from app.models.user_point_history import UserPointHistory
from app.models.video import Video
from app.models.video_view_log import VideoViewLog
from app.models.video_request import VideoRequest
from app.models.video_like import VideoLike
from app.models.video_bookmark import VideoBookmark
from app.models.comment import Comment
from app.models.user_emotion_dna import UserEmotionDna
from app.models.user_emotion_summary import UserEmotionSummary

from app.models.mongodb import (
    VideoDistribution,
    YoutubeWatchingData,
    VideoTimelineEmotionCount
)

__all__ = [
    'db',

    'User',
    'UserFavoriteGenre',
    'UserPointHistory',
    'Video',
    'VideoViewLog',
    'VideoRequest',
    'VideoLike',
    'VideoBookmark',
    'Comment',
    'UserEmotionDna',
    'UserEmotionSummary',

    'VideoDistribution',
    'YoutubeWatchingData',
    'VideoTimelineEmotionCount'
]
