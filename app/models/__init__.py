"""
Models package
SQLAlchemy ORM 모델 및 MongoDB 스키마

MariaDB SQLAlchemy Models (one model per file):
- User: 사용자 정보
- UserFavoriteGenre: 사용자 선호 장르
- UserPointHistory: 사용자 포인트 이력
- Video: 영상 정보
- VideoViewLog: 영상 시청 기록
- VideoRequest: 영상 요청
- VideoLike: 영상 좋아요
- VideoBookmark: 영상 북마크
- Comment: 댓글

MongoDB Collections:
- VideoDistribution: 영상별 감정 분포 통계
- VideoDistributionHistory: 영상 통계 히스토리
- YoutubeWatchingData: 사용자 시청 데이터 (감정 분석 포함)
- VideoTimelineEmotionCount: 타임라인별 감정 개수
"""

from common.extensions import db

# SQLAlchemy Models (MariaDB) - 스프링 Entity처럼 각 모델이 개별 파일
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

# MongoDB Models
from app.models.mongodb import (
    VideoDistribution,
    YoutubeWatchingData,
    VideoTimelineEmotionCount
)

__all__ = [
    # Database instance
    'db',

    # SQLAlchemy Models
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

    # MongoDB Models
    'VideoDistribution',
    'YoutubeWatchingData',
    'VideoTimelineEmotionCount'
]
