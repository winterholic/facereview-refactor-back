import unittest
from datetime import datetime
from unittest.mock import patch

from flask import Flask

from common.extensions import db
from common.utils.emotion_summary import (
    build_emotion_seconds_from_timeline,
    build_finalized_session_query,
)
from app.models.user_emotion_summary import UserEmotionSummary
from app.models.mongodb.youtube_watching_data import YoutubeWatchingData
from app.services.watching_data_service import WatchingDataService


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


class WatchingDataFinalizeRetryTest(unittest.TestCase):
    def test_save_preserves_existing_session_finalized_at(self):
        original_finalized_at = datetime(2026, 7, 19, 12, 30, 0)
        existing = YoutubeWatchingData(
            user_id='user-1',
            video_id='video-1',
            video_view_log_id='session-a',
            created_at=datetime(2026, 7, 19, 12, 0, 0),
            emotion_score_timeline={'0': [0, 100, 0, 0, 0]},
            most_emotion_timeline={'0': 'happy'},
            finalized_at=original_finalized_at,
        )

        class _Repo:
            finalized = None

            def find_by_video_view_log_id(self, video_view_log_id):
                return existing

            def finalize(self, watching_data):
                self.finalized = watching_data

        repo = _Repo()
        cached_data = {
            'user_id': 'user-1',
            'video_id': 'video-1',
            'duration': 100,
        }

        with patch('app.services.watching_data_service.YoutubeWatchingDataRepository', return_value=repo), \
             patch('app.services.watching_data_service.VideoDistributionRepository'), \
             patch.object(WatchingDataService, '_update_video_distribution'):
            WatchingDataService.save_watching_data(
                'session-a', cached_data=cached_data
            )

        self.assertEqual(repo.finalized.finalized_at, original_finalized_at)


if __name__ == '__main__':
    unittest.main()
