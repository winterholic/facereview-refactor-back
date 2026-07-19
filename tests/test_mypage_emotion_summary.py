import unittest

from app.services.mypage_service import (
    _build_emotion_summary_from_docs,
    _estimate_watch_seconds_from_summary,
)


class EmotionSummaryTest(unittest.TestCase):
    def test_counts_each_emotion_second_once_from_most_emotion_timeline(self):
        docs = [
            {
                'most_emotion_timeline': {
                    '0': 'happy',
                    '50': 'sad',
                    '120': 'sad',
                    '190': 'happy',
                    '240': 'neutral',
                }
            }
        ]

        result = _build_emotion_summary_from_docs(docs)

        self.assertEqual(result['emotion_seconds']['happy'], 1)
        self.assertEqual(result['emotion_seconds']['sad'], 1)
        self.assertEqual(result['emotion_seconds']['neutral'], 1)
        self.assertEqual(result['emotion_seconds']['surprise'], 0)
        self.assertEqual(result['emotion_seconds']['angry'], 0)
        self.assertEqual(result['emotion_percentages']['happy'], 33.3)

    def test_falls_back_to_dominant_percentages_when_timeline_is_missing(self):
        docs = [
            {
                'duration': 100,
                'completion_rate': 0.5,
                'emotion_percentages': {'happy': 0.6, 'sad': 0.4},
            }
        ]

        result = _build_emotion_summary_from_docs(docs)

        self.assertEqual(result['emotion_seconds']['happy'], 30)
        self.assertEqual(result['emotion_seconds']['sad'], 20)
        self.assertEqual(result['emotion_percentages']['happy'], 60.0)

    def test_sums_precomputed_session_emotion_seconds(self):
        docs = [
            {
                'emotion_seconds': {
                    'neutral': 10, 'happy': 5, 'surprise': 0,
                    'sad': 0, 'angry': 0,
                }
            },
            {
                'emotion_seconds': {
                    'neutral': 2, 'happy': 0, 'surprise': 3,
                    'sad': 0, 'angry': 0,
                }
            },
        ]

        result = _build_emotion_summary_from_docs(docs)

        self.assertEqual(result['emotion_seconds']['neutral'], 12)
        self.assertEqual(result['emotion_seconds']['happy'], 5)
        self.assertEqual(result['emotion_seconds']['surprise'], 3)
        self.assertEqual(result['emotion_percentages']['neutral'], 60.0)


class WatchSecondsEstimateTest(unittest.TestCase):
    def test_timeline_length_uses_two_samples_per_second(self):
        self.assertEqual(
            _estimate_watch_seconds_from_summary({'timeline_len': 60}),
            30.0,
        )

    def test_frame_count_uses_two_samples_per_second(self):
        self.assertEqual(
            _estimate_watch_seconds_from_summary({'frame_count': 60}),
            30.0,
        )


if __name__ == '__main__':
    unittest.main()
