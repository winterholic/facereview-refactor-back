import uuid
from datetime import datetime
from sqlalchemy import Column, String, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from common.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class VideoBookmark(db.Model):
    __tablename__ = 'video_bookmark'

    # Primary Key
    video_bookmark_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='북마크 ID (UUID)'
    )

    # Foreign Keys
    video_id = Column(
        String(36),
        ForeignKey('video.video_id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment='영상 ID (FK)'
    )
    user_id = Column(
        String(36),
        ForeignKey('user.user_id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment='사용자 ID (FK)'
    )

    # 타임스탬프
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='북마크 등록 시간')

    # Relationships
    video = relationship('Video', back_populates='video_bookmarks')
    user = relationship('User', back_populates='video_bookmarks')

    # Unique constraint (한 유저당 한 영상에 한 번만 북마크)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'video_id', name='uk_bookmark_user_video'),
    )

    def __repr__(self):
        return f'<VideoBookmark video_id={self.video_id} user_id={self.user_id}>'

    def to_dict(self):
        return {
            'video_bookmark_id': self.video_bookmark_id,
            'video_id': self.video_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
