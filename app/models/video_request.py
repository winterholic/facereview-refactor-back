import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from common.extensions import db
from common.enum.youtube_genre import GenreEnum


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

    # NOTE: DB(docs/MARIA_CREATE_QUERY.txt)엔 처음부터 NOT NULL 컬럼으로 존재했으나 이 모델에는
    #       매핑이 누락돼 있었음 — admin_service.get_video_requests()가 결과행에서 category에
    #       접근할 때마다 AttributeError로 500(요청 1건 이상이면 항상 발생, 0건일 때만 안 터져서
    #       "목록엔 하나도 안 보임"으로 관측됨). String으로 매핑(Enum 타입 아님) — DB enum 값 집합이
    #       video.category(GenreEnum)와 달라(예: 'fear' vs GenreEnum의 'horror', exercise/vlog 없음)
    #       SQLAlchemy Enum으로 매핑하면 값 검증에서 되레 깨짐. 확인 필요: 두 enum을 통일할지 여부.
    category = Column(String(20), nullable=False, comment='신청 카테고리')

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
