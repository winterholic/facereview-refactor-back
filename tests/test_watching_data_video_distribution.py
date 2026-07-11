import unittest
from dataclasses import dataclass, field
from typing import Dict

from app.services.watching_data_service import WatchingDataService


@dataclass
class _FakeEmotionPercentages:
    neutral: float = 0.0
    happy: float = 0.0
    surprise: float = 0.0
    sad: float = 0.0
    angry: float = 0.0


@dataclass
class _FakeWatchingData:
    emotion_percentages: _FakeEmotionPercentages
    completion_rate: float
    emotion_score_timeline: Dict[str, list] = field(default_factory=dict)


class _FakeWatchingRepo:
    def __init__(self, sessions):
        self._sessions = sessions

    def find_by_video_id(self, video_id, limit=100):
        return self._sessions


class _FakeDistRepo:
    def __init__(self):
        self.upserted = None

    def upsert(self, distribution):
        self.upserted = distribution


class UpdateVideoDistributionMinFramesTest(unittest.TestCase):
    def test_sparse_sessions_below_threshold_leave_dominant_emotion_none(self):
        #NOTE: 세션 2개, 프레임 합계 4개 (30 미만) — 표본 부족이라 dominant_emotion 확정 금지
        sessions = [
            _FakeWatchingData(
                emotion_percentages=_FakeEmotionPercentages(neutral=100.0),
                completion_rate=0.1,
                emotion_score_timeline={'0': [100, 0, 0, 0, 0], '50': [100, 0, 0, 0, 0]}
            ),
            _FakeWatchingData(
                emotion_percentages=_FakeEmotionPercentages(neutral=100.0),
                completion_rate=0.1,
                emotion_score_timeline={'0': [100, 0, 0, 0, 0], '50': [100, 0, 0, 0, 0]}
            ),
        ]
        dist_repo = _FakeDistRepo()

        WatchingDataService._update_video_distribution(dist_repo, _FakeWatchingRepo(sessions), 'v1')

        self.assertIsNone(dist_repo.upserted.dominant_emotion)

    def test_enough_frames_sets_dominant_emotion(self):
        timeline = {str(i): [100, 0, 0, 0, 0] for i in range(30)}
        sessions = [
            _FakeWatchingData(
                emotion_percentages=_FakeEmotionPercentages(neutral=100.0),
                completion_rate=0.5,
                emotion_score_timeline=timeline
            ),
        ]
        dist_repo = _FakeDistRepo()

        WatchingDataService._update_video_distribution(dist_repo, _FakeWatchingRepo(sessions), 'v2')

        self.assertEqual(dist_repo.upserted.dominant_emotion, 'neutral')


if __name__ == '__main__':
    unittest.main()
