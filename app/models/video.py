import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Enum, TIMESTAMP
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import relationship
from common.extensions import db
from common.enum.youtube_genre import GenreEnum


def generate_uuid():
    return str(uuid.uuid4())


class Video(db.Model):
    __tablename__ = 'video'

    video_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='영상 고유 ID (UUID) - MongoDB 연결 키 겸용'
    )

    youtube_url = Column(String(50), nullable=False, unique=True, comment='유튜브 영상 ID (예: dQw4w9WgXcQ)')
    title = Column(String(255), nullable=False, comment='영상 제목')
    channel_name = Column(String(100), comment='채널명')

    category = Column(
        Enum(GenreEnum, values_callable=lambda x: [e.value for e in x], name='genre_enum'),
        nullable=False,
        comment='카테고리'
    )

    duration = Column(Integer, default=0, comment='영상 길이(초)')

    view_count = Column(BigInteger, default=0, comment='조회수')

    is_deleted = Column(TINYINT(1), default=0, comment='삭제 여부 (0:활성, 1:삭제)')

    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='등록일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='수정일시'
    )
    point_history = relationship(
        'UserPointHistory',
        back_populates='video',
        lazy='dynamic'
    )
    view_logs = relationship(
        'VideoViewLog',
        back_populates='video',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    comments = relationship(
        'Comment',
        back_populates='video',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    video_likes = relationship(
        'VideoLike',
        back_populates='video',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Video {self.title} ({self.youtube_url})>'

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'youtube_url': self.youtube_url,
            'title': self.title,
            'channel_name': self.channel_name,
            'category': self.category,
            'duration': self.duration,
            'view_count': self.view_count,
            'is_deleted': bool(self.is_deleted),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @property
    def like_count(self):
        return self.video_likes.count()

    @property
    def comment_count(self):
        return self.comments.filter_by(is_deleted=0).count()
