from datetime import datetime
from sqlalchemy import Column, String, Integer, TIMESTAMP, JSON

from common.extensions import db


class UserEmotionDna(db.Model):
    __tablename__ = 'user_emotion_dna'

    user_id = Column(String(36), primary_key=True)
    dna_type = Column(String(50), nullable=False)
    dna_data = Column(JSON, nullable=False)
    based_on_videos = Column(Integer, nullable=False)
    generated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    expires_at = Column(TIMESTAMP, nullable=False)
