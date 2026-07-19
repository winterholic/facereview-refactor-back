from datetime import datetime
from typing import Dict

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String

from common.extensions import db


class UserEmotionSummary(db.Model):
    __tablename__ = 'user_emotion_summary'

    user_id = Column(
        String(36),
        ForeignKey('user.user_id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    )
    neutral_seconds = Column(BigInteger, nullable=False, default=0)
    happy_seconds = Column(BigInteger, nullable=False, default=0)
    surprise_seconds = Column(BigInteger, nullable=False, default=0)
    sad_seconds = Column(BigInteger, nullable=False, default=0)
    angry_seconds = Column(BigInteger, nullable=False, default=0)
    last_finalized_at = Column(DateTime, nullable=True)
    last_session_id = Column(String(64), nullable=True)
    lock_version = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @classmethod
    def apply_delta(
        cls,
        user_id: str,
        expected_version: int,
        emotion_seconds: Dict[str, int],
        checkpoint_at: datetime,
        checkpoint_session_id: str,
    ) -> bool:
        values = {
            cls.neutral_seconds: cls.neutral_seconds + int(emotion_seconds.get('neutral', 0)),
            cls.happy_seconds: cls.happy_seconds + int(emotion_seconds.get('happy', 0)),
            cls.surprise_seconds: cls.surprise_seconds + int(emotion_seconds.get('surprise', 0)),
            cls.sad_seconds: cls.sad_seconds + int(emotion_seconds.get('sad', 0)),
            cls.angry_seconds: cls.angry_seconds + int(emotion_seconds.get('angry', 0)),
            cls.last_finalized_at: checkpoint_at,
            cls.last_session_id: checkpoint_session_id,
            cls.lock_version: cls.lock_version + 1,
            cls.updated_at: datetime.utcnow(),
        }
        updated = cls.query.filter_by(
            user_id=user_id,
            lock_version=expected_version,
        ).update(values, synchronize_session=False)
        db.session.flush()
        return updated == 1

    def emotion_seconds_dict(self) -> Dict[str, int]:
        return {
            'neutral': int(self.neutral_seconds),
            'happy': int(self.happy_seconds),
            'surprise': int(self.surprise_seconds),
            'sad': int(self.sad_seconds),
            'angry': int(self.angry_seconds),
        }
