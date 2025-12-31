import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from common.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class UserPointHistory(db.Model):
    __tablename__ = 'user_point_history'

    # Primary Key
    user_point_history_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='포인트 이력 ID (UUID)'
    )

    # Foreign Keys
    user_id = Column(
        String(36),
        ForeignKey('user.user_id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment='사용자 ID (FK)'
    )
    video_id = Column(
        String(36),
        ForeignKey('video.video_id', ondelete='SET NULL', onupdate='CASCADE'),
        nullable=True,
        comment='관련 영상 ID (FK)'
    )

    # 포인트 정보
    amount = Column(Integer, nullable=False, comment='변동 포인트 (양수:획득, 음수:사용)')
    watch_time = Column(Integer, default=0, comment='인정된 시청 시간(초)')
    description = Column(String(255), comment='내역 설명')

    # 타임스탬프
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='생성일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='수정일시'
    )

    # Relationships
    user = relationship('User', back_populates='point_history')
    video = relationship('Video', back_populates='point_history')

    def __repr__(self):
        return f'<UserPointHistory user_id={self.user_id} amount={self.amount}>'

    def to_dict(self):
        return {
            'user_point_history_id': self.user_point_history_id,
            'user_id': self.user_id,
            'video_id': self.video_id,
            'amount': self.amount,
            'watch_time': self.watch_time,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
