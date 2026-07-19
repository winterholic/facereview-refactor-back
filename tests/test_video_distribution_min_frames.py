import unittest

from app.models.mongodb.video_distribution import VideoDistributionRepository, MIN_RELIABLE_FRAMES


class _FakeCollection:
    def __init__(self, doc):
        self._doc = doc
        self.last_set = None
        self.find_calls = 0

    def create_index(self, *args, **kwargs):
        return None

    def find_one(self, *args, **kwargs):
        self.find_calls += 1
        return self._doc

    def update_one(self, _filter, update, **kwargs):
        self.last_set = update.get('$set', {})
        self._doc.update(self.last_set)


class _FakeDb:
    def __init__(self, doc):
        self.collection = _FakeCollection(doc)

    def __getitem__(self, name):
        return self.collection


class VideoDistributionMinFramesTest(unittest.TestCase):
    def test_increment_recalculates_distribution_once(self):
        database = _FakeDb({
            'video_id': 'v0',
            'total_frames': 1,
            'emotion_counts': {'neutral': 1},
            'category': 'drama',
            'duration': 60,
        })
        repo = VideoDistributionRepository(database)

        repo.increment_emotion('v0', 'neutral', 'drama', 60)

        self.assertEqual(database.collection.find_calls, 1)

    def test_below_threshold_dominant_emotion_stays_none(self):
        doc = {
            'video_id': 'v1',
            'total_frames': MIN_RELIABLE_FRAMES - 1,
            'emotion_counts': {'neutral': MIN_RELIABLE_FRAMES - 1},
            'category': 'drama',
            'duration': 60,
        }
        repo = VideoDistributionRepository(_FakeDb(doc))

        result = repo._recalculate_scores('v1')

        self.assertIsNone(result.dominant_emotion)
        # NOTE: emotion_averages는 표본 부족과 무관하게 계속 계산·저장(향후 표본이 쌓이면 자연 반영)
        self.assertEqual(result.emotion_averages.neutral, 1.0)

    def test_at_threshold_dominant_emotion_is_set(self):
        doc = {
            'video_id': 'v2',
            'total_frames': MIN_RELIABLE_FRAMES,
            'emotion_counts': {'neutral': MIN_RELIABLE_FRAMES},
            'category': 'drama',
            'duration': 60,
        }
        repo = VideoDistributionRepository(_FakeDb(doc))

        result = repo._recalculate_scores('v2')

        self.assertEqual(result.dominant_emotion, 'neutral')


if __name__ == '__main__':
    unittest.main()
