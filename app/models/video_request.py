import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from common.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class VideoRequest(db.Model):
    __tablename__ = 'video_request'

    video_request_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='영상 요청 ID (UUID)'
    )

    user_id = Column(
        String(36),
        ForeignKey('user.user_id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment='요청한 사용자 ID (FK)'
    )

    youtube_url = Column(String(50), nullable=False, comment='유튜브 영상 ID (예: dQw4w9WgXcQ)')
    youtube_full_url = Column(
        String(255),
        nullable=False,
        comment='유튜브 영상 전체 URL (예: https://www.youtube.com/watch?v=dQw4w9WgXcQ)'
    )

    #NOTE: 운영 DB에는 category가 없으며 관리자가 요청 승인 시 영상 category를 결정한다.
    #      실제 스키마 마이그레이션 전에는 이 모델에 category를 추가하지 않는다.

    status = Column(
        Enum('PENDING', 'ACCEPTED', 'REJECTED', name='request_status_enum'),
        default='PENDING',
        nullable=False,
        comment='처리 상태 (대기, 승인, 거절)'
    )

    admin_comment = Column(String(255), nullable=True, comment='관리자 처리 코멘트 (거절 사유 등)')

    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='요청 일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='처리 일시'
    )

    user = relationship('User', back_populates='video_requests')

    def __repr__(self):
        return f'<VideoRequest {self.youtube_url} status={self.status}>'

    def to_dict(self):
        return {
            'video_request_id': self.video_request_id,
            'user_id': self.user_id,
            'youtube_url': self.youtube_url,
            'youtube_full_url': self.youtube_full_url,
            'status': self.status,
            'admin_comment': self.admin_comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
