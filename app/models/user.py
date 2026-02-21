import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Enum, TIMESTAMP
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import relationship
from common.extensions import db
from app.models.user_point_history import UserPointHistory


def generate_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = 'user'

    # Primary Key
    user_id = Column(String(36), primary_key=True, default=generate_uuid, comment='사용자 고유 ID (UUID)')

    # 기본 정보
    email = Column(String(255), nullable=False, unique=True, comment='이메일 (로그인 ID)')
    password = Column(String(255), nullable=False, comment='암호화된 비밀번호')
    name = Column(String(50), nullable=False, comment='사용자 이름')

    # 상태 및 권한
    role = Column(
        Enum('GENERAL', 'ADMIN', name='user_role_enum'),
        default='GENERAL',
        nullable=False,
        comment='사용자 권한'
    )
    profile_image_id = Column(Integer, default=0, comment='프로필 이미지 ID (클라이언트 리소스 매핑용)')
    is_tutorial_done = Column(TINYINT(1), default=0, comment='튜토리얼 완료 여부 (0:미완료, 1:완료)')
    is_verify_email_done = Column(TINYINT(1), default=0, comment='이메일 인증 완료 여부 (0:미완료, 1:완료)')
    is_deleted = Column(TINYINT(1), default=0, comment='탈퇴 여부 (0:활성, 1:탈퇴)')

    # 타임스탬프
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='생성일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='수정일시 (자동 갱신)'
    )

    # Relationships
    favorite_genres = relationship(
        'UserFavoriteGenre',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    point_history = relationship(
        'UserPointHistory',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    view_logs = relationship(
        'VideoViewLog',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    video_requests = relationship(
        'VideoRequest',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    comments = relationship(
        'Comment',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    video_likes = relationship(
        'VideoLike',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    video_bookmarks = relationship(
        'VideoBookmark',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'profile_image_id': self.profile_image_id,
            'is_tutorial_done': bool(self.is_tutorial_done),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @property
    def total_points(self):
        return db.session.query(
            db.func.sum(UserPointHistory.amount)
        ).filter(
            UserPointHistory.user_id == self.user_id
        ).scalar() or 0

    def complete_tutorial(self):
        if self.is_tutorial_done:
            return

        self.is_tutorial_done = True