import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from common.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class VideoRequest(db.Model):
    __tablename__ = 'video_request'

    # Primary Key
    video_request_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='영상 요청 ID (UUID)'
    )

    # Foreign Key
    user_id = Column(
        String(36),
        ForeignKey('user.user_id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment='요청한 사용자 ID (FK)'
    )

    # 요청 정보
    youtube_url = Column(String(50), nullable=False, comment='유튜브 영상 ID (예: dQw4w9WgXcQ)')
    youtube_full_url = Column(
        String(255),
        nullable=False,
        comment='유튜브 영상 전체 URL (예: https://www.youtube.com/watch?v=dQw4w9WgXcQ)'
    )

    # NOTE: docs/database-refactor.md의 레거시 설계엔 category 컬럼이 있었지만 실제 운영 DB엔
    #       한 번도 반영된 적 없음(schema drift) — 여기 매핑했다가 실제 쿼리가
    #       "Unknown column 'video_request.category'"로 깨지는 걸 실측으로 확인해 되돌림.
    #       실제 데이터 흐름을 보면 요청 생성 시점(home_service.create_user_video_recommend,
    #       VideoRecommendRequestSchema)에도 category를 안 받음 — 카테고리는 요청자가 아니라
    #       "승인하는 관리자가 승인 시점에 고르는 값"이 맞는 설계. approve_video_request()가
    #       요청 바디로 category를 받도록 변경(아래 참고).

    # 상태 관리
    status = Column(
        Enum('PENDING', 'ACCEPTED', 'REJECTED', name='request_status_enum'),
        default='PENDING',
        nullable=False,
        comment='처리 상태 (대기, 승인, 거절)'
    )

    # 관리자 코멘트
    admin_comment = Column(String(255), nullable=True, comment='관리자 처리 코멘트 (거절 사유 등)')

    # 타임스탬프
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='요청 일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='처리 일시'
    )

    # Relationship
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
