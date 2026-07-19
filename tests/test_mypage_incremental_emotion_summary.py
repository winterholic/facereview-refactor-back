import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import app.services.mypage_service as mypage_service


class _Query:
    def __init__(self, value):
        self.value = value

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self.value


class _UserModel:
    query = _Query(object())


class _Summary:
    def __init__(self):
        self.user_id = 'user-1'
        self.neutral_seconds = 10
        self.happy_seconds = 5
        self.surprise_seconds = 0
        self.sad_seconds = 0
        self.angry_seconds = 0
        self.last_finalized_at = datetime(2026, 7, 19, 12, 0, 0)
        self.last_session_id = 'session-a'
        self.lock_version = 3

    def emotion_seconds_dict(self):
        return {
            'neutral': self.neutral_seconds,
            'happy': self.happy_seconds,
            'surprise': self.surprise_seconds,
            'sad': self.sad_seconds,
            'angry': self.angry_seconds,
        }


class _SummaryModel:
    summary = _Summary()
    query = _Query(summary)
    applied = None

    @classmethod
    def apply_delta(cls, *args, **kwargs):
        cls.applied = (args, kwargs)
        return True


class _Repo:
    requested = None

    def __init__(self, db):
        pass

    def find_finalized_emotion_summaries_since(
        self, user_id, checkpoint_at, checkpoint_session_id
    ):
        type(self).requested = (user_id, checkpoint_at, checkpoint_session_id)
        return [{
            'video_view_log_id': 'session-b',
            'finalized_at': checkpoint_at + timedelta(minutes=1),
            'emotion_seconds': {
                'neutral': 2, 'happy': 3, 'surprise': 1,
                'sad': 0, 'angry': 0,
            },
        }]


class IncrementalEmotionSummaryServiceTest(unittest.TestCase):
    def test_adds_only_sessions_after_saved_checkpoint(self):
        with patch.object(mypage_service, 'User', _UserModel), \
             patch.object(mypage_service, 'UserEmotionSummary', _SummaryModel, create=True), \
             patch.object(mypage_service, 'YoutubeWatchingDataRepository', _Repo):
            result = mypage_service.MypageService.get_emotion_summary.__wrapped__('user-1')

        self.assertEqual(
            _Repo.requested,
            ('user-1', _SummaryModel.summary.last_finalized_at, 'session-a'),
        )
        self.assertEqual(result['emotion_seconds']['neutral'], 12)
        self.assertEqual(result['emotion_seconds']['happy'], 8)
        self.assertEqual(result['emotion_percentages']['happy'], 38.1)
        self.assertIsNotNone(_SummaryModel.applied)


if __name__ == '__main__':
    unittest.main()
