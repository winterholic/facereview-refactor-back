import unittest
from datetime import datetime

from flask import Flask

from common.extensions import db
from common.utils.emotion_summary import (
    build_emotion_seconds_from_timeline,
    build_finalized_session_query,
)
from app.models.user_emotion_summary import UserEmotionSummary


class EmotionSummaryAggregationTest(unittest.TestCase):
    def test_builds_one_dominant_emotion_per_video_second(self):
        result = build_emotion_seconds_from_timeline({
            '0': 'happy',
            '50': 'sad',
            '120': 'sad',
            '190': 'happy',
            '240': 'neutral',
        })

        self.assertEqual(result, {
            'neutral': 1,
            'happy': 1,
            'surprise': 0,
            'sad': 1,
            'angry': 0,
        })

    def test_checkpoint_query_excludes_already_processed_sessions(self):
        checkpoint = datetime(2026, 7, 19, 12, 30, 0)

        query = build_finalized_session_query('user-1', checkpoint, 'session-b')

        self.assertEqual(query, {
            'user_id': 'user-1',
            '$or': [
                {'finalized_at': {'$gt': checkpoint}},
                {
                    'finalized_at': checkpoint,
                    'video_view_log_id': {'$gt': 'session-b'},
                },
            ],
        })


class UserEmotionSummaryOptimisticLockTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        UserEmotionSummary.__table__.create(db.engine)
        db.session.add(UserEmotionSummary(user_id='user-1'))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_stale_version_does_not_apply_delta_twice(self):
        checkpoint = datetime(2026, 7, 19, 12, 30, 0)
        delta = {
            'neutral': 10,
            'happy': 5,
            'surprise': 2,
            'sad': 1,
            'angry': 0,
        }

        first = UserEmotionSummary.apply_delta(
            'user-1', expected_version=0, emotion_seconds=delta,
            checkpoint_at=checkpoint, checkpoint_session_id='session-a'
        )
        second = UserEmotionSummary.apply_delta(
            'user-1', expected_version=0, emotion_seconds=delta,
            checkpoint_at=checkpoint, checkpoint_session_id='session-a'
        )
        db.session.commit()

        summary = db.session.get(UserEmotionSummary, 'user-1')
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(summary.happy_seconds, 5)
        self.assertEqual(summary.lock_version, 1)


if __name__ == '__main__':
    unittest.main()
