import uuid
from datetime import datetime
from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, Index
from sqlalchemy.orm import relationship
from common.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class VideoViewLog(db.Model):
    __tablename__ = 'video_view_log'

    # Primary Key
    video_view_log_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='시청 기록 ID (UUID)'
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
        nullable=True,
        comment='사용자 ID (FK, 비로그인 시 NULL)'
    )

    # 비로그인 사용자 식별
    guest_token = Column(String(255), nullable=True, comment='비로그인 사용자 식별 토큰 (브라우저/세션 ID)')

    # 타임스탬프
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='시청 일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='수정일시'
    )

    # Relationships
    video = relationship('Video', back_populates='view_logs')
    user = relationship('User', back_populates='view_logs')

    # Indexes
    __table_args__ = (
        Index('idx_user_history', 'user_id', 'created_at'),
        Index('idx_video_history', 'video_id', 'created_at'),
    )

    def __repr__(self):
        return f'<VideoViewLog video_id={self.video_id} user_id={self.user_id}>'

    def to_dict(self):
        return {
            'video_view_log_id': self.video_view_log_id,
            'video_id': self.video_id,
            'user_id': self.user_id,
            'guest_token': self.guest_token,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
