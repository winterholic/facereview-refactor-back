import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from common.extensions import db
from common.enum.youtube_genre import GenreEnum


def generate_uuid():
    return str(uuid.uuid4())


class UserFavoriteGenre(db.Model):
    __tablename__ = 'user_favorite_genre'

    # Primary Key
    user_favorite_genre_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment='선호 장르 ID (UUID)'
    )

    # Foreign Key
    user_id = Column(
        String(36),
        ForeignKey('user.user_id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment='사용자 ID (FK)'
    )

    # 장르
    genre = Column(
        Enum(GenreEnum, values_callable=lambda x: [e.value for e in x], name='genre_enum'),
        nullable=False,
        comment='선호 장르'
    )

    # 타임스탬프
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, comment='생성일시')
    updated_at = Column(
        TIMESTAMP,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment='수정일시'
    )

    # Relationship
    user = relationship('User', back_populates='favorite_genres')

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'genre', name='uk_user_genre'),
    )

    def __repr__(self):
        return f'<UserFavoriteGenre user_id={self.user_id} genre={self.genre}>'

    def to_dict(self):
        return {
            'user_favorite_genre_id': self.user_favorite_genre_id,
            'user_id': self.user_id,
            'genre': self.genre,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
