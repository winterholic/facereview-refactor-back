import unittest

from app.models.mongodb.youtube_watching_data import YoutubeWatchingDataRepository


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

    def find(self, *args):
        self.find_args = args
        return self.cursor


class _FakeDb:
    def __init__(self):
        self.collection = _FakeCollection()

    def __getitem__(self, name):
        return self.collection


class YoutubeWatchingDataRepositoryTest(unittest.TestCase):
    def test_find_recent_summaries_by_user_id_excludes_raw_timelines(self):
        db = _FakeDb()
        repo = YoutubeWatchingDataRepository(db)

        repo.find_recent_summaries_by_user_id('user-1', limit=7)

        query, projection = db.collection.find_args
        self.assertEqual(query, {'user_id': 'user-1'})
        self.assertEqual(projection['emotion_score_timeline'], 0)
        self.assertEqual(projection['most_emotion_timeline'], 0)
        self.assertEqual(db.collection.cursor.limited_to, 7)


if __name__ == '__main__':
    unittest.main()
