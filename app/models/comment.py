import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, Index
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import relationship
from common.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Comment(db.Model):
    __tablename__ = 'comment'

    # Primary Key
    comment_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='댓글 ID (UUID)'
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
        comment='작성자 ID (FK)'
    )

    # 댓글 내용
    content = Column(Text, nullable=False, comment='댓글 내용')

    # 상태 정보
    is_modified = Column(TINYINT(1), default=0, comment='수정 여부 (0:원본, 1:수정됨)')
    is_deleted = Column(TINYINT(1), default=0, comment='삭제 여부 (0:활성, 1:삭제됨 - 관리자 확인용)')

    # 타임스탬프
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='작성일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='수정일시'
    )

    # Relationships
    video = relationship('Video', back_populates='comments')
    user = relationship('User', back_populates='comments')

    # Index (영상별 댓글 조회 최적화)
    __table_args__ = (
        Index('idx_video_comments', 'video_id', 'is_deleted', 'created_at'),
    )

    def __repr__(self):
        return f'<Comment comment_id={self.comment_id} video_id={self.video_id}>'

    def to_dict(self, include_user=False):
        result = {
            'comment_id': self.comment_id,
            'video_id': self.video_id,
            'user_id': self.user_id,
            'content': self.content,
            'is_modified': bool(self.is_modified),
            'is_deleted': bool(self.is_deleted),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_user and self.user:
            result['user'] = {
                'name': self.user.name,
                'profile_image_id': self.user.profile_image_id
            }

        return result
