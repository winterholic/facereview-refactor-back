import unittest
from datetime import datetime

from flask import Flask

from app.models.mongodb.youtube_watching_data import (
    EmotionPercentages,
    YoutubeWatchingData,
    YoutubeWatchingDataRepository,
)


class _FakeCursor:
    def __init__(self):
        self.sorted_by = None
        self.limited_to = None

    def sort(self, *args):
        self.sorted_by = args
        return self

    def limit(self, limit):
        self.limited_to = limit
        return self

    def __iter__(self):
        return iter([])


class _FakeCollection:
    def __init__(self):
        self.find_args = None
        self.cursor = _FakeCursor()
        self.update_args = None
        self.created_indexes = []

    def find(self, *args):
        self.find_args = args
        return self.cursor

    def update_one(self, *args, **kwargs):
        self.update_args = (args, kwargs)

        class _Result:
            upserted_id = None

        return _Result()

    def create_index(self, keys, **kwargs):
        self.created_indexes.append((keys, kwargs))


class _FakeDb:
    def __init__(self):
        self.collection = _FakeCollection()

    def __getitem__(self, name):
        return self.collection


class YoutubeWatchingDataRepositoryTest(unittest.TestCase):
    def test_ensure_indexes_adds_incremental_summary_checkpoint_index(self):
        db = _FakeDb()

        YoutubeWatchingDataRepository.ensure_indexes(db)

        self.assertIn(
            ([('user_id', 1), ('finalized_at', 1), ('video_view_log_id', 1)], {}),
            db.collection.created_indexes,
        )

    def test_find_recent_summaries_by_user_id_excludes_raw_timelines(self):
        db = _FakeDb()
        repo = YoutubeWatchingDataRepository(db)

        repo.find_recent_summaries_by_user_id('user-1', limit=7)

        query, projection = db.collection.find_args
        self.assertEqual(query, {'user_id': 'user-1'})
        self.assertEqual(projection['emotion_score_timeline'], 0)
        self.assertEqual(projection['most_emotion_timeline'], 0)
        self.assertEqual(db.collection.cursor.limited_to, 7)

    def test_find_finalized_emotion_summaries_excludes_raw_timelines(self):
        db = _FakeDb()
        repo = YoutubeWatchingDataRepository(db)
        checkpoint = datetime(2026, 7, 19, 12, 30, 0)

        repo.find_finalized_emotion_summaries_since(
            'user-1', checkpoint, 'session-a'
        )

        query, projection = db.collection.find_args
        self.assertEqual(query['user_id'], 'user-1')
        self.assertEqual(query['$or'][0], {'finalized_at': {'$gt': checkpoint}})
        self.assertEqual(projection['emotion_score_timeline'], 0)
        self.assertEqual(projection['most_emotion_timeline'], 0)
        self.assertEqual(
            db.collection.cursor.sorted_by,
            ([('finalized_at', 1), ('video_view_log_id', 1)],),
        )

    def test_finalize_persists_precomputed_emotion_seconds(self):
        app = Flask(__name__)
        db = _FakeDb()
        repo = YoutubeWatchingDataRepository(db)
        watching_data = YoutubeWatchingData(
            user_id='user-1',
            video_id='video-1',
            video_view_log_id='session-a',
            created_at=datetime(2026, 7, 19, 12, 0, 0),
            emotion_percentages=EmotionPercentages(happy=0.5, sad=0.5),
            most_emotion_timeline={
                '0': 'happy', '50': 'sad', '120': 'sad',
            },
        )

        with app.test_request_context('/'):
            repo.finalize(watching_data)

        update_doc = db.collection.update_args[0][1]['$set']
        self.assertEqual(update_doc['emotion_seconds']['sad'], 2)
        self.assertEqual(update_doc['emotion_seconds']['happy'], 0)
        self.assertIsInstance(update_doc['finalized_at'], datetime)

    def test_finalize_retry_preserves_original_finalized_at(self):
        app = Flask(__name__)
        db = _FakeDb()
        repo = YoutubeWatchingDataRepository(db)
        original_finalized_at = datetime(2026, 7, 19, 12, 30, 0)
        watching_data = YoutubeWatchingData(
            user_id='user-1',
            video_id='video-1',
            video_view_log_id='session-a',
            created_at=datetime(2026, 7, 19, 12, 0, 0),
            most_emotion_timeline={'0': 'happy'},
            finalized_at=original_finalized_at,
        )

        with app.test_request_context('/'):
            repo.finalize(watching_data)

        update_doc = db.collection.update_args[0][1]['$set']
        self.assertEqual(update_doc['finalized_at'], original_finalized_at)


if __name__ == '__main__':
    unittest.main()
